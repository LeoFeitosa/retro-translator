"""Checks that translated text really shows up right on screen: plays the original and the translated ROM with the
same buttons, reads the screen text of both with the game's font table and reports every changed line that has a
cell which is not a known letter (a wrong glyph or a scenery tile in the middle of a word) or wrong upper/lower case.
Saves those frames to output/conferir/.
Usage: python -m tools.check ROM [translated ROM] [--memory]"""
import json
import os
import random
import re
import subprocess
import sys

import numpy as np

UNKNOWN = "□"


def save_(rom, out_, translated=None):
    """Child process: screen text lines (with grid position) and frames every few seconds."""
    from retro_translator.core.rewriting import rom_text
    from retro_translator.core.reading import table as tb
    from retro_translator import consoles
    m, rnd, samples = consoles.for_rom(rom).Emulator(rom), random.Random(3), []
    original = bytes(consoles.for_rom(rom).read_rom(rom))
    for q in range(1500):
        if translated and q == rom_text.AFTER_GAME // 20:
            m.write_rom(open(translated, "rb").read(), original)
        b = rnd.choice(["A", "B", "START", "A", "B", "UP", "DOWN", "LEFT", "RIGHT", None, None])
        m.run_frames(4, [b] if b else [])
        m.run_frames(16)
        if q % 5 == 0:
            lines = [(p, y, x, ["" if c is None else c for c in tr]) for p, y, x, tr in tb.excerpt_pos(m)]
            grids = m.planes()  # whole rows with text: garbage splits a run and would not show up in it
            rows_ = {f"{p},{y}": [tb.glyph(m.pattern(int(e))) for e in grids[p][y][:64]]
                        for p, y in {(p, y) for p, y, _, _ in lines}}
            frame_ = np.zeros((240, 320, 3), np.uint8)  # 256- and 320-pixel modes in the same array
            frame_[:m.frame.shape[0], :m.frame.shape[1]] = m.frame
            samples.append(((lines, rows_), frame_))
    np.save(out_, np.array([a[1] for a in samples]))
    json.dump([a[0] for a in samples], open(out_ + ".json", "w"))


def blank(key_):
    """Blank cell (no ink), so not garbage."""
    from retro_translator.core.reading import table as tb
    return key_ in ("", tb.EMPTY) or not key_.lstrip("#").strip("0")


def line_problem(text, old_):
    """Why a translated line looks wrong on screen, or None: a cell that is not a known letter, a lowercase letter
    where the original line was all uppercase, or case mixed inside a word ("pARA", "jOGO")."""
    if UNKNOWN in text.strip():
        return "ILEGIVEL"
    old_letters = [c for c in old_ if c.isalpha()]
    if len(old_letters) > 1 and all(c.isupper() for c in old_letters) and any(c.islower() for c in text):
        return "CASE (original all uppercase)"
    if any(re.search(r"[a-z][A-Z]|^[a-z][A-Z]{2}", w) for w in re.findall(r"[A-Za-z]+", text)):
        return "MIXED CASE"
    return None


def main(rom, translated, memory):
    from retro_translator.core.reading import evaluate
    from retro_translator.core.reading import decipher
    from PIL import Image
    name_ = os.path.splitext(os.path.basename(rom))[0]
    found, indices = evaluate.collection(rom)
    table = decipher.read_font(found, indices, exclude=name_)
    folder = os.path.join("output", "check")
    os.makedirs(folder, exist_ok=True)
    paths = [os.path.join(folder, name_ + s) for s in (".orig.npy", ".trad.npy")]
    procs = [subprocess.Popen([sys.executable, __file__, "--record", rom, paths[0]]),
             subprocess.Popen([sys.executable, __file__, "--record", rom if memory else translated, paths[1]]
                              + ([translated] if memory else []))]
    for p in procs:
        p.wait()
    fo, ft = np.load(paths[0]), np.load(paths[1])
    lo, lt = (json.load(open(a + ".json")) for a in paths)
    read_ = lambda tr: "".join(" " if not c else table.get(c, UNKNOWN) for c in tr)
    bad, seen_, swapped = 0, set(), set()
    for i, ((a, _), (b, rows_)) in enumerate(zip(lo, lt)):
        before = {(p, y, x): tr for p, y, x, tr in a}
        for p, y, x, tr in a:  # where the original had text, the translated row must have letters or blanks
            fil = rows_.get(f"{p},{y}")
            if fil is None or [c for c in fil[x:x + len(tr)]] == tr:
                continue
            text = "".join(" " if not c or c not in table and (blank(c) or c == o) else table.get(c, UNKNOWN)
                            for c, o in zip(fil[x:x + len(tr)], tr))  # unchanged cells do not count
            if UNKNOWN in text and text not in seen_:
                seen_.add(text)
                bad += 1
                print("ILEGIVEL", repr(read_(tr)), "->", repr(text), flush=True)
                Image.fromarray(np.hstack([fo[i], ft[i]])).save(os.path.join(folder, f"{name_}_{bad:02d}.png"))
        for p, y, x, tr in b:
            old_ = before.get((p, y, x))
            if old_ == tr:
                continue  # unchanged line
            text = read_(tr)
            swapped.add(text)
            problem = line_problem(text, read_(old_) if old_ else "")
            if problem and text not in seen_:
                seen_.add(text)
                bad += 1
                print(problem, repr(read_(old_) if old_ else ""), "->", repr(text), flush=True)
                Image.fromarray(np.hstack([fo[i], ft[i]])).save(os.path.join(folder, f"{name_}_{bad:02d}.png"))
    print(f"{name_}: {len(swapped)} lines swapped, {bad} with problems")


if __name__ == "__main__":
    if sys.argv[1] == "--record":
        save_(*sys.argv[2:5])
    else:
        rom = sys.argv[1]
        name_ = os.path.splitext(os.path.basename(rom))[0]
        trans = next((a for a in sys.argv[2:] if not a.startswith("--")), os.path.join("output", f"{name_}.pt.bin"))
        main(rom, trans, "--memory" in sys.argv)
