from PIL import Image
import struct

img = Image.open("logo.bmp").convert("RGB")

with open("logo.bin", "wb") as f:
    for y in range(img.height):
        for x in range(img.width):
            r, g, b = img.getpixel((x, y))
            rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
            f.write(struct.pack(">H", rgb565))  # Big-endian
