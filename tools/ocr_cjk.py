"""Experiment: reads Japanese/Chinese 16x16 text on screen by shape (blurred correlation with Unifont glyphs) plus
character frequency. Madou Monogatari dialog: "ばくも少し / のんじゃあっと。" for "ぼくも少し / のんじゃおっと。".
Usage: python -m tools.ocr_cjk ROM"""
import collections, gzip, os, random, sys
import numpy as np
from PIL import Image, ImageFilter
def gaussian_filter(a, r):
    im = Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r))
    return np.asarray(im, float) / 255
from wordfreq import top_n_list
from retro_translator import DATA, consoles
freq, pairs = collections.Counter(), collections.Counter()
for i, w in enumerate(top_n_list("ja", 50000)):
    for ch in w: freq[ch] += 1 / (i + 50)
    for a2, b2 in zip(w, w[1:]): pairs[a2, b2] += 1 / (i + 50)
uni = {}
for l in gzip.open(os.path.join(DATA, "kanji", "unifont.hex.gz"), "rt"):
    c, h = l.strip().split(":"); ch = chr(int(c, 16))
    if not (0x3040 <= ord(ch) <= 0x30ff or freq[ch] > 0 or ch in "。、…！？「」"):
        continue
    w = len(h) // 16 * 4
    b = np.array([[int(h[i*w//4:(i+1)*w//4], 16) >> (w-1-j) & 1 for j in range(w)] for i in range(16)], float)
    if w == 8: b = np.pad(b, ((0, 0), (4, 4)))
    uni[ch] = b
chars = list(uni)
def prep(a):
    a = gaussian_filter(a.astype(float), 1.2); a = a - a.mean(); return a.ravel() / (np.linalg.norm(a) + 1e-9)
ref = np.array([prep(uni[c]) for c in chars])
prior = np.array([np.log(freq[c] + 1e-4) for c in chars])
print(len(chars))
m = consoles.for_rom(sys.argv[1]).Emulator(sys.argv[1]); r = random.Random(2)
for q in range(401):
    b = r.choice(['A', 'B', 'START', 'START', 'DOWN', 'UP', None, None])
    m.run_frames(4, [b] if b else []); m.run_frames(16)
ink = m.frame.astype(int).sum(2) > 600
def candidates(y, x, k=8):
    cel = ink[y:y+16, x:x+16]
    if cel.sum() < 6: return [(0.0, " ")]
    best = {}
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            s = ref @ prep(np.roll(np.roll(cel, dy, 0), dx, 1)) + 0.02 * prior
            for j in np.argsort(-s)[:k]:
                best[chars[j]] = max(best.get(chars[j], -9), s[j])
    return sorted(((v, c) for c, v in best.items()), reverse=True)[:k]


def line(y, xs, weight=0.03):
    """Best sequence: shape score of each cell plus how often each pair of characters follows in words."""
    beam = [(0.0, "")]
    for x in xs:
        new = []
        for s0, t in beam:
            for s1, c in candidates(y, x):
                b = np.log(pairs[t[-1], c] + 1e-6) if t and t[-1] != " " and c != " " else np.log(1e-3)
                new.append((s0 + s1 + weight * b, t + c))
        beam = sorted(new, reverse=True)[:30]
    return beam[0][1]


print(" | ".join(line(y, range(16, 144, 16)) for y in (136, 152, 168)))
