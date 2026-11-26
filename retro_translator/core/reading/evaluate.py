"""Evaluation of one game: collects the text drawn on screen (cached in captures/), learns the table and measures
accuracy on text that was not used for learning. The bulk run over a ROM folder is tools/evaluate.py."""
import json
import os
import random
import re
import time

from retro_translator import DATA
from retro_translator.core.reading import table

MAX_READINGS = 80
SAMPLE = 8


def region_ok(name_):
    """Only games with western text for now; skips bad dumps, hacks and trainers."""
    if re.search(r"\[(b|h|t|a|o|f|p)\d*", name_):
        return False
    tags = re.findall(r"\(([^)]*)\)", name_)
    return bool(tags) and tags[0] != "J"


def collection(rom):
    """CPU-only collection, cached in captures/ so the GPU step does not emulate again."""
    import pickle
    path_ = os.path.join("captures", os.path.splitext(os.path.basename(rom))[0] + ".pkl")
    idx = path_[:-4] + ".idx.pkl"
    if os.path.exists(path_) and os.path.exists(idx):
        return pickle.load(open(path_, "rb")), pickle.load(open(idx, "rb"))
    indices = {}
    found = table.collect(rom, 10, indices)  # collection is CPU only (~15 s per 3 min of play): more screens, more text
    os.makedirs("captures", exist_ok=True)
    for value_, name_ in ((indices, idx), (found, path_)):
        pickle.dump(value_, open(name_ + ".tmp", "wb"))
        os.replace(name_ + ".tmp", name_)
    return found, indices


def evaluate(rom):
    read_items, empty_ones = set(), [0]
    read_original = table.read_

    def read_counting(excerpt):
        if len(read_items) >= MAX_READINGS:
            return ""
        read_items.add(excerpt)
        text = read_original(excerpt)
        empty_ones[0] += not text
        return text

    table.read_ = read_counting
    try:
        t0 = time.time()
        found, indices = collection(rom)
        tab, _ = table.learn(found, log=lambda *a: None)
    finally:
        table.read_ = read_original
    # the executable's CPU-only method (dictionary decipherment), measured against the vision AI table
    from retro_translator.core.reading import decipher
    from collections import Counter as _C
    t1 = time.time()
    game_name = os.path.splitext(os.path.basename(rom))[0]
    cpu = decipher.read_font(found, indices, exclude=game_name)
    usage = _C(g for w in decipher.words(found) for g in w if g in tab)
    cpu_accuracy = round(sum(n for g, n in usage.items() if cpu.get(g) == tab[g]) / sum(usage.values()), 2) if usage else None
    cpu_sec = round(time.time() - t1)
    os.makedirs(os.path.join(DATA, "tables"), exist_ok=True)
    name_ = os.path.splitext(os.path.basename(rom))[0]
    json.dump(tab, open(os.path.join(DATA, "tables", name_ + ".json"), "w", encoding="utf-8"), ensure_ascii=False)
    known = [tr for tr in found if tr not in read_items and all(c in tab for c in tr if c)]
    todos = [tr for tr in found]
    coverage = len([tr for tr in todos if all(c in tab for c in tr if c)]) / max(len(todos), 1)
    test = [tr for tr in known if sum(1 for c in tr if c) >= 5]
    random.Random(0).shuffle(test)
    hits, examples = 0, []
    for tr in test[:SAMPLE]:
        ref = " ".join(table.read_(tr).split())
        dec = " ".join(table.decode_(tr, tab).split())
        hits += ref == dec
        if ref != dec and len(examples) < 3:
            examples.append([dec, ref])
    n = min(len(test), SAMPLE)
    return {"excerpts": len(found), "glyphs": len(tab), "readings": len(read_items),
            "coverage": round(coverage, 2), "tested": n,
            "accuracy": round(hits / n, 2) if n else None, "errors": examples,
            "seconds": round(time.time() - t0),
            "cpu_accuracy": cpu_accuracy, "cpu_seconds": cpu_sec,
            "highs": sum(any(c and "/" in c for c in tr) for tr in found), "empty": empty_ones[0]}
