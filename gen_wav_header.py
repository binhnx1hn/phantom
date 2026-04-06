"""gen_wav_header.py - Convert WAV file to C header for embedding in ESP32 firmware"""
import os, sys

src = "test.wav"
dst = "esp32_client/src/test_wav.h"

os.makedirs(os.path.dirname(dst), exist_ok=True)

data = open(src, "rb").read()
print(f"Read {src}: {len(data)} bytes ({len(data)/1024:.1f} KB)")

lines = [
    "#pragma once",
    "#include <stdint.h>",
    f"// {src} embedded - {len(data)} bytes ({len(data)/1024:.1f} KB)",
    f"static const uint32_t TEST_WAV_SIZE = {len(data)};",
    "static const uint8_t TEST_WAV_DATA[] = {",
]
row = []
for i, b in enumerate(data):
    row.append(f"0x{b:02X}")
    if len(row) == 16:
        lines.append("  " + ", ".join(row) + ",")
        row = []
if row:
    lines.append("  " + ", ".join(row))
lines.append("};")

with open(dst, "w") as f:
    f.write("\n".join(lines) + "\n")

print(f"Written: {dst}  ({os.path.getsize(dst):,} bytes)")
