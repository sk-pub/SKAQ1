from font_petme128_8x8 import font_petme128_8x8

# Framebuf format constats:
MVLSB     = 0  # Single bit displays (like SSD1306 OLED)


class MVLSBFormat:

    def setpixel(self, fb, x, y, color):
        index = (y >> 3) * fb.stride + x
        offset = y & 0x07
        fb.buf[index] = (fb.buf[index] & ~(0x01 << offset)) | ((color != 0) << offset)

    def getpixel(self, fb, x, y):
        index = (y >> 3) * fb.stride + x
        offset = y & 0x07
        return ((fb.buf[index] >> offset) & 0x01)

    def fill_rect(self, fb, x, y, width, height, color):
        while height > 0:
            index = (y >> 3) * fb.stride + x
            offset = y & 0x07
            for ww in range(width):
                fb.buf[index+ww] = (fb.buf[index+ww] & ~(0x01 << offset)) | ((color != 0) << offset)
            y += 1
            height -= 1

class FrameBuffer:

    def __init__(self, buf, width, height):
        self.buf = buf
        self.width = width
        self.height = height
        self.stride = width
        self.format = MVLSBFormat()

    def fill(self, color):
        self.format.fill_rect(self, 0, 0, self.width, self.height, color)

    def fill_rect(self, x, y, width, height, color):
        if width < 1 or height < 1 or (x+width) <= 0 or (y+height) <= 0 or y >= self.height or x >= self.width:
            return
        xend = min(self.width, x+width)
        yend = min(self.height, y+height)
        x = max(x, 0)
        y = max(y, 0)
        self.format.fill_rect(self, x, y, xend-x, yend-y, color)

    def pixel(self, x, y, color=None):
        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            return
        if color is None:
            return self.format.getpixel(self, x, y)
        else:
            self.format.setpixel(self, x, y, color)
    def text(self, str, x0, y0, col):
        for c in str:
            # get char and make sure its in range of font
            chr = ord(c)
            if (chr < 32 or chr > 127):
                chr = 127;

            # get char data
            chr_data = font_petme128_8x8[(chr - 32) * 8:(chr - 32) * 8 + 8]
            # loop over char data
            for j in range(7):
                x0 += 1
                if 0 <= x0 and x0 < self.width: # clip x
                    vline_data = chr_data[j] # each byte is a column of 8 pixels, LSB at top                    
                    # scan over vertical column
                    y = y0
                    while vline_data:
                        if vline_data & 1: # only draw if pixel set
                            if 0 <= y and y < self.height: # clip y
                                self.pixel(x0, y, col)
                        
                        vline_data = vline_data >> 1
                        y += 1
