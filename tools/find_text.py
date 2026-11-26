"""Development: plays a ROM, finds in it the lines read on screen (relative search) and lists the text found;
with --translate, translates the ROM and prints what was replaced and why the rest was not.
Usage: python -m tools.find_text ROM | python -m tools.find_text --translate ROM [language]"""
import os
import random
import sys
from collections import Counter

from retro_translator import consoles
from retro_translator.core import overlay
from retro_translator.core.reading import decipher, evaluate
from retro_translator.core.rewriting.rom_text import REASONS, codes, extract, lines_on_screen, search, translate


def main(rom):
    found, indices = evaluate.collection(rom)
    name_ = os.path.splitext(os.path.basename(rom))[0]
    table = decipher.read_font(found, indices, exclude=name_)
    console = consoles.for_rom(rom)
    data = console.read_rom(rom)
    md, rnd, seen, hits, total = console.Emulator(rom), random.Random(1), set(), 0, 0
    votes, spaces = Counter(), Counter()
    for _ in range(1800):
        button = rnd.choice(["A", "B", "START", "A", "B", "UP", "DOWN", "LEFT", "RIGHT", None, None])
        md.run_frames(4, [button] if button else [])
        md.run_frames(16)
        for text, ent in lines_on_screen(md, table):
            if text in seen:
                continue
            seen.add(text)
            r = search(data, ent)
            total += 1
            hits += bool(r)
            for p, width, base in r:
                votes[width, base] += 1
                spaces.update(int.from_bytes(data[p + i * width:p + (i + 1) * width], "big")
                               for i, t in enumerate(ent) if t is None)
            print(f"{text[:40]!r:44} {r[:3]}", flush=True)
    print(f"found in the ROM: {hits}/{total}")
    if not votes:
        return
    (width, base), _ = votes.most_common(1)[0]
    space = spaces.most_common(1)[0][0] if spaces else None
    sentences = extract(data, codes(table, indices, width, base, space), width)
    print(f"code: {width} byte(s), base {base}, space {space}; sentences in the ROM: {len(sentences)}")
    for p, t in [f for f in sentences if overlay.looks_english(f[1])][:40]:
        print(p, repr(t[:70]))


if __name__ == "__main__":
    if sys.argv[1] == "--translate":
        print(translate(sys.argv[2], *sys.argv[3:4]), dict(REASONS))
    else:
        main(sys.argv[1])
