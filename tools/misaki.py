"""Development: converts the Misaki 8x8 Japanese font (free license, Num Kadoma) into kanji/misaki8.hex.gz (code
point:16 hex digits, one byte per row), the reference shape for 8x8 kana and kanji in cjk.py.
Usage: python -m tools.misaki misaki_gothic.bdf misaki_gothic_2nd.bdf"""
import gzip
import sys


def main(paths):
    out_ = []
    for path_ in paths:
        code, lines = None, None
        for l in open(path_, encoding="latin-1"):
            l = l.strip()
            if l.startswith("ENCODING"):
                code = int(l.split()[1])
            elif l.startswith("FONT_ASCENT"):
                top = int(l.split()[1])
            elif l.startswith("DWIDTH"):
                advance = int(l.split()[1])
            elif l.startswith("BBX"):
                width, alt, dx, low = map(int, l.split()[1:])
            elif l == "BITMAP":
                lines = []
            elif l == "ENDCHAR":
                if code and code > 0x2FFF and advance == 8:  # full-width characters only
                    grid = [0] * 8  # glyph box placed in the 8x8 cell by the font baseline
                    for i, r in enumerate(lines):
                        grid[top - low - alt + i] = int(r[:2], 16) >> dx
                    out_.append("%04X:%s" % (code, "".join("%02X" % v for v in grid)))
                lines = None
            elif lines is not None:
                lines.append(l)
    with gzip.open("kanji/misaki8.hex.gz", "wt") as f:
        f.write("\n".join(out_) + "\n")
    print(len(out_), "glyphs")


if __name__ == "__main__":
    main(sys.argv[1:])
