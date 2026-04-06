import wave, struct, math, os

filename = 'test.wav'
sample_rate = 8000
duration = 2       # 2 giây
frequency = 440    # Hz (La 440)

samples = []
for i in range(sample_rate * duration):
    val = int(127 * math.sin(2 * math.pi * frequency * i / sample_rate))
    samples.append(struct.pack('B', val + 128))  # unsigned 8-bit

with wave.open(filename, 'w') as f:
    f.setnchannels(1)      # mono
    f.setsampwidth(1)      # 8-bit
    f.setframerate(sample_rate)
    f.writeframes(b''.join(samples))

size = os.path.getsize(filename)
print(f'Created: {filename}')
print(f'Size: {size} bytes ({size/1024:.1f} KB)')
print(f'Duration: {duration}s, {sample_rate}Hz, mono, 8-bit')
