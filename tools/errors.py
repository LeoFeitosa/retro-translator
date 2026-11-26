"""Shows the glyphs the CPU got wrong in a game: right letter (AI table), read letter, VRAM position and use."""
import json, pickle, sys
from collections import Counter
from retro_translator.core.reading import decipher
j = sys.argv[1]
a = pickle.load(open(f"captures/{j}.pkl", "rb")); ix = pickle.load(open(f"captures/{j}.idx.pkl", "rb"))
tab = json.load(open(f"tables/{j}.json"))
m0 = decipher.decipher(a, prior=decipher.library(exclude=j))
m = decipher.by_order(decipher.box(decipher.sequence(m0, a, ix), a), ix)
usage = Counter(g for w in decipher.words(a) for g in w)
for g in sorted(tab, key=lambda g: ix[g].most_common(1)[0][0] if g in ix else -1):
    print(repr(tab[g]), repr(m.get(g)), repr(m0.get(g)), ix[g].most_common(1)[0][0] if g in ix else None, usage[g], "" if m.get(g) == tab[g] else "<<")
ws = decipher.words(a)
print([" ".join("".join(m.get(g, "?") for g in w) for w in [k]) for k, _ in ws.most_common(25)])
u = Counter(g for w in ws for g in w if g in tab)
print("accuracy", round(sum(n for g, n in u.items() if m.get(g) == tab[g]) / sum(u.values()), 3))
