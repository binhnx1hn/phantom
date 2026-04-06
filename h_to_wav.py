"""
h_to_wav.py - Convert C header file (test_wav.h) back to WAV file
=================================================================
Usage:
  python h_to_wav.py                          # dung mac dinh: esp32_client/src/test_wav.h -> output.wav
  python h_to_wav.py --input esp32_client/src/test_wav.h --output recovered.wav
"""
import re
import os
import argparse

def h_to_wav(input_h: str, output_wav: str):
    print(f"Reading: {input_h}")
    content = open(input_h, "r").read()

    # Lay phan du lieu trong { ... }
    match = re.search(r'TEST_WAV_DATA\[\]\s*=\s*\{(.*?)\}', content, re.DOTALL)
    if not match:
        print("ERROR: Khong tim thay TEST_WAV_DATA[] trong file!")
        return False

    hex_block = match.group(1)

    # Extract tat ca hex values (0xNN)
    hex_values = re.findall(r'0x([0-9A-Fa-f]{2})', hex_block)
    if not hex_values:
        print("ERROR: Khong tim thay du lieu hex!")
        return False

    data = bytes(int(h, 16) for h in hex_values)
    print(f"Extracted: {len(data)} bytes")

    # Kiem tra WAV header: phai bat dau bang RIFF
    if data[:4] != b'RIFF':
        print(f"WARNING: Khong phai WAV header chuan! Got: {data[:4]}")
    else:
        # Doc WAV info
        import struct
        channels   = struct.unpack_from('<H', data, 22)[0]
        sample_rate= struct.unpack_from('<I', data, 24)[0]
        bits       = struct.unpack_from('<H', data, 34)[0]
        print(f"WAV info: {channels}ch, {sample_rate}Hz, {bits}-bit, {len(data)} bytes")

    os.makedirs(os.path.dirname(output_wav) if os.path.dirname(output_wav) else ".", exist_ok=True)
    open(output_wav, "wb").write(data)
    print(f"Written : {output_wav}  ({len(data):,} bytes)")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert test_wav.h back to WAV file")
    parser.add_argument("--input",  default="esp32_client/src/test_wav.h", help="input .h file")
    parser.add_argument("--output", default="recovered.wav",               help="output .wav file")
    args = parser.parse_args()

    ok = h_to_wav(args.input, args.output)
    if ok:
        print("\nDone! Mo file nay de nghe:")
        print(f"  {os.path.abspath(args.output)}")
