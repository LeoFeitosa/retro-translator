"""Development check: plays a Japanese game, reads its 16x16 text and prints each line read by the ROM font order
(cjk.font_in_rom; "·" = not placed) next to the shape-only reading. Usage: python -m tools.cjk_rom ROM"""
import random, sys
import numpy as np
from retro_translator import consoles
from retro_translator.core.reading import cjk
rom = sys.argv[1]; data = bytes(consoles.for_rom(rom).read_rom(rom))
m = consoles.for_rom(rom).Emulator(rom); r = random.Random(2); glyphs = {}; seen = []
chars, shapes, prior, pairs = cjk.references("ja")
for q in range(3000):
    b = r.choice(['A', 'B', 'START', 'START', 'DOWN', 'UP', None, None])
    m.run_frames(4, [b] if b else []); m.run_frames(16)
    if q % 10: continue
    g = m.planes()
    for plane, y, x, n, t in cjk.read_(m):
        line = []
        for k in range(n):
            ents = [[int(g[plane][y + i][x + 2 * k + j]) for j in (0, 1)] for i in (0, 1)]
            ink = cjk._cell([[m.pattern(e) for e in rr] for rr in ents])
            if ink is None: continue
            packed = np.packbits(ink.astype(np.uint8), axis=1).tobytes()
            s = shapes @ cjk._blur(ink).ravel(); top = np.argsort(-s)[:8]
            glyphs[packed] = [(float(s[i]), chars[i]) for i in top]
            line.append(packed)
        seen.append(line)
map_ = cjk.font_in_rom(data, glyphs)
print(len(glyphs), "glyphs,", len(map_), "by font order")
for line in {tuple(l) for l in seen if len(l) >= 3}:
    print("".join(map_.get(p, "·") for p in line), "|", "".join(glyphs[p][0][1] for p in line))
base = min(p for g, p in ((g, data.find(g)) for g in map_) if p > 0xbf000)
for g, c in glyphs.items():
    p = data.find(g)
    if g not in map_ and p >= 0:
        print(hex(p), (p - base) // 32 if p >= base else "-", c[0])
for g, c in map_.items():
    if c in "ぇぉ":
        print("DEBUG", c, hex(data.find(g)), glyphs[g][:3])
