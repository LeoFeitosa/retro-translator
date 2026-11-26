"""Development: converts the Shinonome 16-dot JIS X 0208 font (public domain) into kanji/shinonome16.hex.gz, in the
Unifont .hex layout (code point:64 hex digits), as a second reference shape for cjk.py.
Usage: python -m tools.shinonome shinonome-0.9.11-src/16/kanjic/font_src.bit"""
import gzip
import sys


def main(path_):
    out_, code, lines = [], None, None
    for l in open(path_, encoding="latin-1"):
        l = l.rstrip("\n")
        if l.startswith("ENCODING"):
            code = int(l.split()[1])
        elif l.startswith("BITMAP"):
            lines = []
        elif l.startswith("ENDCHAR"):
            try:
                ch = bytes([(code >> 8) | 0x80, (code & 0xFF) | 0x80]).decode("euc_jp")
            except UnicodeDecodeError:
                ch = None
            if ch and len(lines) == 16:
                out_.append("%04X:%s" % (ord(ch), "".join("%04X" % int(r.replace(".", "0").replace("@", "1"), 2)
                                                           for r in lines)))
            lines = None
        elif lines is not None:
            lines.append(l[:16])
    with gzip.open("kanji/shinonome16.hex.gz", "wt") as f:
        f.write("\n".join(out_) + "\n")
    print(len(out_), "glyphs")


if __name__ == "__main__":
    main(sys.argv[1])
