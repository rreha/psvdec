import sys
import os
import struct
import base64
import keyflate

FAKE_AID = 0x0123456789ABCDEF

def make_zrif(fp, output_file=None):
    try:
        with open(fp, 'rb') as f:
            data = bytearray(f.read())

        if len(data) != 512:
            print(f"Error: {fp} is not a valid license (must be 512 bytes).")
            return

        current_aid = struct.unpack_from('<Q', data, 0x08)[0]
        if current_aid != 0:
            print(f"-> Anonymizing Account ID in {os.path.basename(fp)}...")
            struct.pack_into('<Q', data, 0x08, FAKE_AID)

        content_id = keyflate.get_content_id(data)

        compressed_bytes = keyflate.deflate_key(data)
        
        if compressed_bytes:
            zrif_string = base64.b64encode(compressed_bytes).decode('utf-8')
            clean_zrif = zrif_string.rstrip('=')
            print(f"\n-> Generated zRIF for {content_id}:")
            print(f"    {clean_zrif}")
            
            if output_file:
                with open(output_file, 'w', encoding='utf-8') as out_f:
                    out_f.write(clean_zrif)
                print(f"-> Saved zRIF string to: {output_file}")
        else:
            print(f"Error: Compression failed for {fp}")

    except Exception as e:
        print(f"Error processing file {fp}: {e}")

def make_rif(zrif_str, output_file=None):
    try:
        pad_len = 4 - (len(zrif_str) % 4)
        if pad_len != 4:
            zrif_str += '=' * pad_len
            
        compressed_bytes = base64.b64decode(zrif_str)
        
        raw_data = keyflate.inflate_key(compressed_bytes)
        
        if not raw_data:
            print("Error: Invalid zRIF string (could not decompress).")
            return

        content_id = keyflate.get_content_id(raw_data)
        if not content_id:
            content_id = "unknown_license"

        filename = output_file if output_file else f"{content_id}_work.bin"

        with open(filename, 'wb') as f:
            f.write(raw_data)
            
        print(f"\n-> Created license file: {filename}")
        print(f"    Size: {len(raw_data)} bytes")
        print(f"    Content ID: {content_id}")

    except Exception as e:
        print(f"Error processing zRIF string: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("zzZrif - (z)RIF Converter")
        print("Usage:")
        print("  To make zRIF from RIF:   python zzzrif.py work.bin [output.txt]")
        print("  To make RIF from zRIF:   python zzzrif.py \"zRIFKey\" [output.bin]")
        sys.exit(1)

    input_arg = sys.argv[1]
    output_arg = sys.argv[2] if len(sys.argv) > 2 else None

    if os.path.exists(input_arg):
        make_zrif(input_arg, output_arg)
    else:
        clean_input = input_arg.strip('"').strip("'")
        make_rif(clean_input, output_arg)