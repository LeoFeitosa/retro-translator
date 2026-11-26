"""The consoles the program translates. Each one is an isolated package that provides the same names (NAME,
EXTENSIONS, Emulator, read_rom, write_rom, TEXT_START, data_end, checksum, HEADER_SUM, header_sum_valid,
set_header_sum, fix_checksum); the shared code only uses those. A new console: a new package here, added to
CONSOLES (docs/ARCHITECTURE.md)."""
import os

from retro_translator.consoles import megadrive

CONSOLES = [megadrive]


def for_rom(path):
    """The console of a game file, by its extension."""
    ext = os.path.splitext(path)[1].lower()
    for console in CONSOLES:
        if ext in console.EXTENSIONS:
            return console
    raise ValueError(f"no console reads {ext} files")


def extensions():
    """Every game file extension the program opens (for the file dialog)."""
    return [e for console in CONSOLES for e in console.EXTENSIONS]
