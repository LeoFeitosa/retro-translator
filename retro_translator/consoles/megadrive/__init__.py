"""Sega Mega Drive / Genesis. Everything specific to this console lives in this package; the shared code (core/)
reaches it only through the names below, which every console package provides (docs/ARCHITECTURE.md)."""
from retro_translator.consoles.megadrive.emulator import MegaDrive as Emulator
from retro_translator.consoles.megadrive.rom import (EXTENSIONS, HEADER_SUM, TEXT_START, checksum, data_end,
                                                    fix_checksum, header_sum_valid, read_rom, set_header_sum,
                                                    write_rom)

NAME = "Mega Drive"

__all__ = ["NAME", "EXTENSIONS", "Emulator", "read_rom", "write_rom", "TEXT_START", "data_end", "checksum",
           "HEADER_SUM", "header_sum_valid", "set_header_sum", "fix_checksum"]
