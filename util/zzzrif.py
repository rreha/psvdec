import sys
import os
import struct
import base64
import keyflate

FAKE_AID = 0x0123456789ABCDEF

def make_zrif(fp, output_file=None, silent=False):
    out = lambda *a, **k: None if silent else print(*a, **k)

    try:
        with open(fp, 'rb') as f:
            data = bytearray(f.read())

        if len(data) != 512:
            out(f"Error: {fp} is not a valid license (must be 512 bytes).")
            return

        current_aid = struct.unpack_from('<Q', data, 0x08)[0]
        if current_aid != 0:
            out(f"-> Anonymizing Account ID in {os.path.basename(fp)}...")
            struct.pack_into('<Q', data, 0x08, FAKE_AID)

        content_id = keyflate.get_content_id(data)

        compressed_bytes = keyflate.deflate_key(data)
        
        if compressed_bytes:
            zrif_string = base64.b64encode(compressed_bytes).decode('utf-8')
            clean_zrif = zrif_string.rstrip('=')
            out(f"\n-> Generated zRIF for {content_id}:")
            out(f"    {clean_zrif}")
            
            if output_file:
                with open(output_file, 'w', encoding='utf-8') as out_f:
                    out_f.write(clean_zrif)
                out(f"-> Saved zRIF string to: {output_file}")
        else:
            out(f"Error: Compression failed for {fp}")

    except Exception as e:
        out(f"Error processing file {fp}: {e}")

def make_rif(zrif_str, output_file=None, silent=False):
    out = lambda *a, **k: None if silent else print(*a, **k)
    
    try:
        pad_len = 4 - (len(zrif_str) % 4)
        if pad_len != 4:
            zrif_str += '=' * pad_len
            
        compressed_bytes = base64.b64decode(zrif_str)
        
        raw_data = keyflate.inflate_key(compressed_bytes)
        
        if not raw_data:
            out("Error: Invalid zRIF string (could not decompress).")
            return

        content_id = keyflate.get_content_id(raw_data)
        if not content_id:
            content_id = "unknown_license"

        filename = output_file if output_file else f"{content_id}_work.bin"

        with open(filename, 'wb') as f:
            f.write(raw_data)
            
        out(f"\n-> Created license file: {filename}")
        out(f"    Size: {len(raw_data)} bytes")
        out(f"    Content ID: {content_id}")

    except Exception as e:
        print(f"Error processing zRIF string: {e}")

def main(cmd_args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--inputfile", help="input file name", type=str)
    parser.add_argument("-o", "--outputfile", help="output file name", type=str)
    parser.add_argument("-k", "--keyriffile", help="NoNpdrm RIF file name", type=str)
    args=parser.parse_args(cmd_args)
    
    with open(args.inputfile, "rb") as inf:
        with open(args.outputfile, "wb") as outf:
            if args.keyriffile:
                with open(args.keyriffile, "rb") as rif:
                    lic = SceRIF(rif.read(SceRIF.Size))
                    self2elf(inf, outf, lic.klicense, silent=True) 
            else:
                self2elf(inf, outf, 0, silent=True)

if __name__ == "__main__":
    main()