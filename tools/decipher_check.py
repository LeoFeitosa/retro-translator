"""Development: how well the deciphering reads a collection whose right table is known.
Usage: python -m tools.decipher_check FOUND.pkl [RIGHT.pkl]"""
import pickle
import sys
import time
from collections import Counter

from retro_translator.core.reading.decipher import box, decipher, words

found = pickle.load(open(sys.argv[1], "rb"))
right = pickle.load(open(sys.argv[2], "rb")) if len(sys.argv) > 2 else None
t0 = time.time()
m = box(decipher(found), found)
print(f"{len(m)} glyphs in {time.time() - t0:.0f}s")
if right:
    ws = words(found)
    usage = Counter(g for w in ws for g in w)
    ok = sum(n for g, n in usage.items() if g in right and right[g] == m.get(g))
    tot = sum(n for g, n in usage.items() if g in right)
    print(f"accuracy per occurrence: {ok / tot:.1%}")
    for w in list(ws)[:15]:
        print("".join(m[g] for g in w), "|", "".join(right.get(g, "?") for g in w))
