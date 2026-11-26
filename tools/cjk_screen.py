"""Development check: plays a Japanese game and saves original | translated screens (cjk.patches) at a few
moments. Usage: python -m tools.cjk_screen ROM FONT.json OUT.png [language]"""
import json, random, sys
import numpy as np
from PIL import Image
from retro_translator import consoles
from retro_translator.core.reading import cjk
from retro_translator.core import overlay
from retro_translator.core.translating import translation
rom = sys.argv[1]; d = json.load(open(sys.argv[2])); translation.SOURCE = "ja"
LANG = sys.argv[4] if len(sys.argv) > 4 else "pt"
reader = cjk.Reader("ja", {bytes.fromhex(g): c for g, c in d["cjk"].items()}, bytes(consoles.for_rom(rom).read_rom(rom)))
font_ = overlay.Font({})
m = consoles.for_rom(rom).Emulator(rom); r = random.Random(2); imgs = []
for q in range(1801):
    b = r.choice(['A', 'B', 'START', 'START', 'DOWN', 'UP', None, None])
    m.run_frames(4, [b] if b else []); m.run_frames(16)
    if q % 10 == 0: reader.read_(m); reader.learn()
    if q in (400, 1000, 1500):
        list_ = cjk.blocks(m, reader)
        print(q, [b["text"] for b in list_])
        tr = lambda t: translation.translate_batch([t], LANG)[0]
        img = m.frame.copy()
        for y0, y1, x0, x1, px in cjk.patches(m, list_, tr, font_): img[y0:y1, x0:x1] = px
        imgs.append(np.hstack([m.frame, img]))
Image.fromarray(np.vstack(imgs)).save(sys.argv[3])
