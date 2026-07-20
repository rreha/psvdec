import sys
import os
import struct
import argparse
from binascii import hexlify, unhexlify
from Crypto.Cipher import AES
from Crypto.Util import Counter
import keyflate

PKG_VITA_2  = unhexlify("E31A70C9CE1DD72BF3C0622963F2ECCB")
PKG_VITA_3  = unhexlify("423ACA3A2BD5649F9686ABAD6FD8801F")
PKG_VITA_4  = unhexlify("AF07FD59652527BAF13389668B17D9EA")

MAGIC_PKG = 0x7F504B47
MAGIC_EXT = 0x7F657874
FAKE_AID = 0x0123456789ABCDEF

def unpack_header(data):
    fmt = ">IHHIIIIQQQ48s16s16s64s"
    if len(data) < 0xC0: return None
    unpacked = struct.unpack(fmt, data[:0xC0])
    return {
        'magic': unpacked[0], 'revision': unpacked[1], 'type': unpacked[2],
        'info_offset': unpacked[3], 'info_count': unpacked[4], 'header_size': unpacked[5],
        'item_count': unpacked[6], 'total_size': unpacked[7], 'data_offset': unpacked[8],
        'data_size': unpacked[9], 'content_id': unpacked[10].decode('utf-8').strip('\x00'),
        'digest': unpacked[11], 'pkg_data_iv': unpacked[12], 'signatures': unpacked[13]
    }

def unpack_ext_header(data):
    fmt = ">IIIIIIQIIIIQQ"
    if len(data) < 64: return None
    unpacked = struct.unpack(fmt, data[:64])
    return {
        'magic': unpacked[0], 'data_type': unpacked[5], 'data_type2': unpacked[8],
        'pkg_data_size': unpacked[6]
    }

def pack_license(content_id_str):
    data = bytearray(512)
    struct.pack_into(">HHHH", data, 0, 1, 1, 1, 2)
    struct.pack_into(">Q", data, 0x08, FAKE_AID)
    cid_bytes = content_id_str.encode('utf-8')
    data[0x10:0x10+len(cid_bytes)] = cid_bytes
    return data

def parse_sfo(data):
    if len(data) < 20 or data[:4] != b'\x00PSF':
        return {}
    
    key_ofs, data_ofs, count = struct.unpack("<III", data[8:20])
    
    sfo_dict = {}
    for i in range(count):
        entry_ofs = 20 + (i * 16)
        k_ofs, fmt, length, max_len, d_ofs = struct.unpack("<HHIII", data[entry_ofs:entry_ofs+16])
        
        key_start = key_ofs + k_ofs
        key_end = data.find(b'\x00', key_start)
        if key_end == -1: key_end = len(data)
        key = data[key_start:key_end].decode('utf-8', errors='ignore')
        
        val_start = data_ofs + d_ofs
        val_data = data[val_start:val_start+length]
        
        if fmt in (0x0004, 0x0204):
            val = val_data.decode('utf-8', errors='ignore').rstrip('\x00')
        elif fmt == 0x0404:
            val = struct.unpack("<I", val_data)[0]
        else:
            val = val_data
            
        sfo_dict[key] = val
        
    return sfo_dict

class NoPKG:
    def __init__(self, path):
        self.path = path
        self.stream = open(path, 'rb')
        self.header = None
        self.ext_header = None
        self.ctr_key = None
        self.base_iv_int = 0
        self.metadata = {'index_table_offset': 0, 'index_table_size': 0, 'content_type': 0}

        self._parse_headers()
        self._setup_crypto()

    def _parse_headers(self):
        self.stream.seek(0)
        self.header = unpack_header(self.stream.read(0xC0))
        if not self.header or self.header['magic'] != MAGIC_PKG:
            raise ValueError("Invalid PKG file.")
        
        if self.header['header_size'] > 0xC0:
            self.ext_header = unpack_ext_header(self.stream.read(64))

    def _setup_crypto(self):
        if not self.ext_header: raise ValueError("No extended header.")
        key_type = self.ext_header['data_type2'] & 7
        
        if key_type == 2: aes_key = PKG_VITA_2
        elif key_type == 3: aes_key = PKG_VITA_3
        elif key_type == 4: aes_key = PKG_VITA_4
        else: raise ValueError(f"Unsupported Key Type: {key_type}")

        cipher_ecb = AES.new(aes_key, AES.MODE_ECB)
        self.ctr_key = cipher_ecb.encrypt(self.header['pkg_data_iv'])
        self.base_iv_int = int.from_bytes(self.header['pkg_data_iv'], 'big')

    def read_metadata(self):
        info_len = self.header['data_offset'] - self.header['info_offset']
        self.stream.seek(self.header['info_offset'])
        buf = self.stream.read(info_len)
        ptr = 0
        count = self.header['info_count']
        while count > 0 and ptr < len(buf):
            m_type, m_size = struct.unpack(">II", buf[ptr:ptr+8])
            ptr += 8
            val_bytes = buf[ptr:ptr+m_size]
            if m_type == 0x2: self.metadata['content_type'] = struct.unpack(">I", val_bytes[:4])[0]
            elif m_type == 0xD:
                self.metadata['index_table_offset'] = struct.unpack(">I", val_bytes[:4])[0]
                self.metadata['index_table_size'] = struct.unpack(">I", val_bytes[4:8])[0]
            ptr += m_size
            count -= 1

    def read_decrypted(self, offset, size):
        data_start = self.header['data_offset']
        data_end = data_start + self.header['data_size']
        
        if offset < data_start or offset >= data_end:
            self.stream.seek(offset)
            return self.stream.read(size)
            
        rel_offset = offset - data_start
        block_index = rel_offset // 16
        block_offset = rel_offset % 16
        
        counter_val = self.base_iv_int + block_index
        ctr = Counter.new(128, initial_value=counter_val)
        cipher = AES.new(self.ctr_key, AES.MODE_CTR, counter=ctr)
        
        aligned_len = size + block_offset
        if aligned_len % 16 != 0: aligned_len += 16 - (aligned_len % 16)
            
        self.stream.seek(data_start + (block_index * 16))
        dec_data = cipher.decrypt(self.stream.read(aligned_len))
        return dec_data[block_offset:block_offset+size]

    def close(self):
        self.stream.close()

def handle_license(encoded_key, target_cid):
    if len(encoded_key) == 64 and all(c in '0123456789abcdefABCDEF' for c in encoded_key):
        rif = pack_license(target_cid)
        rif[0x50:0x60] = unhexlify(encoded_key)
        return rif
    rif = keyflate.inflate_key(encoded_key)
    if rif:
        cid = rif[0x10:0x40].decode('utf-8').strip('\x00')
        if cid != target_cid:
            print(f"Warning: License Content ID {cid} mismatch package {target_cid}")
    return rif

def main():
    parser = argparse.ArgumentParser(description="NoPKG - PS Vita PKG Extractor")
    parser.add_argument("input", help="Input PKG file")
    parser.add_argument("type", choices=['ux', 'id'], help="Extraction structure: 'id' (/TitleID) or 'ux' (/[app/addcont/patch/...]/TitleID)")
    parser.add_argument("output_dir", nargs='?', default=".", help="Output directory")
    parser.add_argument("--license", help="zRIF string or klicensee")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print detailed progress during extraction")
    
    args = parser.parse_args()
    
    vprint = print if args.verbose else lambda *a, **k: None

    if not os.path.exists(args.input):
        print(f"Error: {args.input} not found.")
        return 1

    vprint(f"Opening {args.input}...")
    pkg = NoPKG(args.input)
    pkg.read_metadata()
    
    cid = pkg.header['content_id']
    is_dlc = (pkg.metadata['content_type'] == 0x16)
    title_id = cid[7:16]

    idx_offset = pkg.header['data_offset'] + pkg.metadata['index_table_offset']
    index_table = pkg.read_decrypted(idx_offset, pkg.metadata['index_table_size'])
    
    num_items = pkg.header['item_count']
    rec_size = 32
    
    is_patch = False
    sfo_data = None
    
    temp_ptr = 0
    for _ in range(num_items):
        if temp_ptr + rec_size > len(index_table): break
        r_name_off, r_name_sz, r_dat_off, r_dat_sz, _, _ = struct.unpack(">IIQQII", index_table[temp_ptr:temp_ptr+rec_size])
        
        rel_name_off = r_name_off - pkg.metadata['index_table_offset']
        fname = index_table[rel_name_off : rel_name_off + r_name_sz].decode('utf-8')
        
        if fname == "sce_sys/changeinfo/changeinfo.xml" and not is_dlc:
            is_patch = True
            
        if fname == "sce_sys/param.sfo":
            abs_dat_off = pkg.header['data_offset'] + r_dat_off
            sfo_buf = bytearray()
            left = r_dat_sz
            curr = abs_dat_off
            while left > 0:
                req = min(left, 65536)
                sfo_buf.extend(pkg.read_decrypted(curr, req))
                curr += req
                left -= req
            sfo_data = bytes(sfo_buf)
            
        temp_ptr += rec_size

    app_title = "Unknown Title"
    app_ver = "Unknown"
    if sfo_data:
        sfo_dict = parse_sfo(sfo_data)
        app_title = sfo_dict.get("TITLE", app_title)
        app_ver = sfo_dict.get("APP_VER", app_ver)

    if args.type == 'id':
        final_out_dir = os.path.join(args.output_dir, title_id)
    else:
        if is_dlc:
            dlc_id = cid[20:]
            final_out_dir = os.path.join(args.output_dir, "addcont", title_id, dlc_id)
        elif is_patch:
            final_out_dir = os.path.join(args.output_dir, "patch", title_id)
        else:
            final_out_dir = os.path.join(args.output_dir, "app", title_id)

    os.makedirs(final_out_dir, exist_ok=True)
    
    print(f"Title:   {app_title}")
    print(f"Version: {app_ver}")
    print(f"Target:  {final_out_dir}")

    head_len = pkg.header['data_offset'] + pkg.metadata['index_table_size']
    pkg.stream.seek(0)
    
    pkg_dir = os.path.join(final_out_dir, "sce_sys", "package")
    os.makedirs(pkg_dir, exist_ok=True)
    
    vprint("Writing head.bin...")
    with open(os.path.join(pkg_dir, "head.bin"), 'wb') as f:
        f.write(pkg.stream.read(head_len))

    ptr = 0
    print(f"\nUnpacking {num_items} items...")
    for _ in range(num_items):
        if ptr + rec_size > len(index_table): break
        
        r_name_off, r_name_sz, r_dat_off, r_dat_sz, r_flags, _ = struct.unpack(">IIQQII", index_table[ptr:ptr+rec_size])
        
        rel_name_off = r_name_off - pkg.metadata['index_table_offset']
        fname = index_table[rel_name_off : rel_name_off + r_name_sz].decode('utf-8')
        
        file_path = os.path.join(final_out_dir, fname)
        
        item_type = r_flags & 0xFF
        if item_type in [4, 18]:
            vprint(f" > [directory]  {fname}")
            os.makedirs(file_path, exist_ok=True)
        else:
            vprint(f" > [file] {fname}")
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            with open(file_path, 'wb') as f_out:
                abs_dat_off = pkg.header['data_offset'] + r_dat_off
                left = r_dat_sz
                curr = abs_dat_off
                while left > 0:
                    req = min(left, 65536)
                    f_out.write(pkg.read_decrypted(curr, req))
                    curr += req
                    left -= req
        
        ptr += rec_size

    tail_offset = pkg.header['data_offset'] + pkg.header['data_size']
    tail_len = pkg.header['total_size'] - tail_offset
    if tail_len > 0:
        vprint("Writing tail.bin...")
        pkg.stream.seek(tail_offset)
        with open(os.path.join(pkg_dir, "tail.bin"), 'wb') as f:
            f.write(pkg.stream.read(tail_len))

    if args.license:
        rif_bytes = handle_license(args.license, cid)
        if rif_bytes:
            vprint("Writing work.bin license...")
            with open(os.path.join(pkg_dir, "work.bin"), 'wb') as f:
                f.write(rif_bytes)
            print("Generated work.bin")

    pkg.close()
    print("\nDone.")

if __name__ == "__main__":
    main()