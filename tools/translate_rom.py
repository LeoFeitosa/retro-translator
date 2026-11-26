"""Core of the program, 100% without AI: learns the ROM font (decipher), plays and saves translated before|after frames.
Usage: python -m tools.translate_rom ROM [language] [frames]"""
import os
import random
import sys

import numpy as np
from PIL import Image

from retro_translator.core.reading import evaluate
from retro_translator.core.reading import decipher
from retro_translator.core import overlay
from retro_translator import consoles


def main(rom, language="pt", frames=12):
    found, indices = evaluate.collection(rom)
    name_ = os.path.splitext(os.path.basename(rom))[0]
    table = decipher.read_font(found, indices, exclude=name_)
    font_ = overlay.Font(table)
    trans = overlay.Overlay(language, os.path.join("output", f"{name_}.{language}.cache.json"))
    md, rnd, seen, n, previous = consoles.for_rom(rom).Emulator(rom), random.Random(1), set(), 0, None
    os.makedirs("output", exist_ok=True)
    for q in range(10 * 60 * 3):
        button = rnd.choice(["A", "B", "START", "A", "B", "UP", "DOWN", "LEFT", "RIGHT", None, None])
        md.run_frames(4, [button] if button else [])
        md.run_frames(16)
        texts = tuple(t for b in overlay.blocks(md, table) for _, t, _ in b["lines"])
        stable, previous = texts == previous, texts  # scrolling or typed-out text changes between samples
        if not texts or not stable or texts in seen:
            continue
        seen.add(texts)
        before = md.frame.copy()
        after = overlay.translate_frame(md, table, trans, font_)
        Image.fromarray(np.hstack([before, after])).save(os.path.join("output", f"{name_}_{n:02d}.png"))
        print(n, " | ".join(texts)[:120], flush=True)
        n += 1
        if n >= frames:
            break


if __name__ == "__main__":
    main(sys.argv[1], *(sys.argv[2:3]), *(int(x) for x in sys.argv[3:4]))
