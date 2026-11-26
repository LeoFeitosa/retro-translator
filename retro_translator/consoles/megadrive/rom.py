"""The Mega Drive ROM file: its formats (.bin linear, .smd interleaved), where text may be rewritten and how the
game checks itself (the header sum)."""
import numpy as np

EXTENSIONS = (".bin", ".md", ".gen", ".smd")
TEXT_START = 0x200  # the header ends here: without "SEGA" at 0x100 the console hangs, so nothing before is rewritten
HEADER_SUM = range(0x18E, 0x190)  # the 16-bit sum of the ROM after the header, written in the header


def read_rom(path):
    """ROM bytes in linear order (.smd has a 512-byte header and interleaved 16 KB blocks)."""
    data = open(path, "rb").read()
    if path.lower().endswith(".smd") and len(data) % 16384 == 512:
        data, out_ = data[512:], bytearray()
        for i in range(0, len(data), 16384):
            b = data[i:i + 16384]
            even, odd = b[8192:], b[:8192]
            out_ += bytes(x for pair in zip(even, odd) for x in pair)
        data = bytes(out_)
    return data


def write_rom(original_path, data, path):
    """Writes linear ROM bytes in the format of the original file: a .smd gets its 512-byte header back and its
    16 KB blocks interleaved again, so the translated game is the same kind of file that came in."""
    raw = open(original_path, "rb").read()
    if original_path.lower().endswith(".smd") and len(raw) % 16384 == 512:
        out_ = bytearray(raw[:512])
        for i in range(0, len(data), 16384):
            b = data[i:i + 16384]
            out_ += b[1::2] + b[0::2]
        data = bytes(out_)
    open(path, "wb").write(data)


def data_end(rom):
    """Where the ROM data ends, from the header (even), within the file."""
    end = min(int.from_bytes(rom[0x1A4:0x1A8], "big") + 1, len(rom))
    return end - end % 2


def checksum(rom):
    """The sum the header keeps: 16-bit words from the end of the header to the end of the data."""
    end = min(int.from_bytes(rom[0x1A4:0x1A8], "big") + 1, len(rom))
    return int(np.frombuffer(bytes(rom[TEXT_START:end - end % 2]), ">u2").sum()) & 0xFFFF


def set_header_sum(rom):
    rom[HEADER_SUM.start:HEADER_SUM.stop] = checksum(rom).to_bytes(2, "big")


def header_sum_valid(rom):
    return int.from_bytes(rom[HEADER_SUM.start:HEADER_SUM.stop], "big") == checksum(rom)


def fix_checksum(rom, original):
    """Games verify the ROM sum on power-up and hang if it changes (including [c] dumps, whose check compares
    with another value). Keeps the sum equal to the original by adjusting a word of the trailing padding (FF/00 after
    the last data); without padding, recomputes the header sum if the original matched."""
    end = min(int.from_bytes(original[0x1A4:0x1A8], "big") + 1, len(rom))
    end -= end % 2
    p = end - 2
    while p > TEXT_START and original[p:p + 2] in (b"\xff\xff", b"\x00\x00"):
        p -= 2
    if end - p >= 8:  # there is padding
        delta = (checksum(original) - checksum(rom)) & 0xFFFF
        w = end - 4
        rom[w:w + 2] = ((int.from_bytes(rom[w:w + 2], "big") + delta) & 0xFFFF).to_bytes(2, "big")
    elif header_sum_valid(original):
        set_header_sum(rom)
