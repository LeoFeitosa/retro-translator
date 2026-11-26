"""Debugging: plays like traduzir_rom until a text run contains TEXT and shows the tile right after it (where the line broke).
Usage: python -m tools.tile ROM TEXT"""
import os, random, sys
import numpy as np
from retro_translator.core.reading import evaluate
from retro_translator.core.reading import decipher
from retro_translator.core.reading import table
from retro_translator import consoles
rom, target_ = sys.argv[1], sys.argv[2]
found, indices = evaluate.collection(rom)
map_ = decipher.read_font(found, indices, exclude=os.path.splitext(os.path.basename(rom))[0])
md, rnd = consoles.for_rom(rom).Emulator(rom), random.Random(1)
for q in range(10 * 60 * 3):
    b = rnd.choice(["A", "B", "START", "A", "B", "UP", "DOWN", "LEFT", "RIGHT", None, None])
    md.run_frames(4, [b] if b else []); md.run_frames(16)
    for plane, y, x, tr in table.excerpt_pos(md):
        if target_ in table.decode_(tr, map_):
            e = int(md.planes()[plane][y][x + len(tr)])
            px = md.pattern(e)
            print(table.decode_(tr, map_), plane, y, x, "colors", np.unique(px), "glyph", table.glyph(px))
            print("\n".join("".join("%x" % v for v in l) for l in px))
            sys.exit()
