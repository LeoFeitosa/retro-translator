"""Learns the tile->letter table of a game by itself (development).

1. plays with random buttons and gathers the text runs that appear in the tile grids;
2. draws each run cleanly and asks a local vision model (Ollama) to read it;
3. aligns the reading with the tiles, word by word, and decides each letter by vote.

usage: python table.py ROM [minutes]
"""
import base64
import io
import json
import random
import time
import urllib.request
from collections import Counter, defaultdict

import numpy as np
from PIL import Image

from retro_translator import consoles

OLLAMA = "http://localhost:11434/api/generate"
VISION_MODEL = "qwen2.5vl:7b"
EMPTY = "0" * 16


_GLYPHS = {}


def glyph(px):
    """Tile key by shape (memoized: the screen repeats the same tiles, and that was almost all the cost)."""
    k = (px.shape, px.tobytes())
    if k not in _GLYPHS:
        if len(_GLYPHS) > 200000:
            _GLYPHS.clear()
        _GLYPHS[k] = _glyph(px)
    key_ = _GLYPHS[k]
    if key_ in _THICK_SEEN:
        THICK.add(key_)
    return key_


_THICK_SEEN = set()


def _glyph(px):
    """Tile key by shape: pixels different from the background colour (the most common).
    A '#' prefix marks a tile that does not look like a letter."""
    background = np.bincount(px.ravel()).argmax()
    m = px != background
    key_ = np.packbits(m).tobytes().hex()
    if m.any() and not looks_letter(px, m):
        # wide letter with more ink than background (M, W, R in a bold font): the background is the colour of a whole
        # single-colour border (the space between letters), not the most common one
        for edge in (px[-1], px[:, -1], px[0], px[:, 0]):
            if len(np.unique(edge)) == 1 and edge[0] != background and looks_letter(px, px != edge[0]):
                return np.packbits(px != edge[0]).tobytes().hex()
    if m.any() and not looks_letter(px, m) and _thick(px):
        key_ = np.packbits(px != 0).tobytes().hex()
        THICK.add(key_)
        _THICK_SEEN.add(key_)
        return key_
    return key_ if m.any() and looks_letter(px, m) else ("#" + key_ if m.any() else EMPTY)


THICK = set()  # keys from the bold font path (see _segment)


def _thick(px):
    """Bold font: the letter fills the whole tile, with shadow/gradient, over colour 0 (transparent)."""
    n = int((px != 0).sum())
    return (px == 0).any() and len(np.unique(px)) <= 4 and 3 <= n <= 60 * px.shape[0] // 8 and n < px.size


def mask(g):
    parts = [np.unpackbits(np.frombuffer(bytes.fromhex(p), np.uint8)).reshape(8, 8) for p in g.split("/")]
    return np.vstack(parts).astype(bool)


def looks_letter(px, m):
    """Font letter: up to 3 colours, 3 to 40 pixels, an empty column or row on the border
    (the space between letters) and no full row or column (that is a frame)."""
    if len(np.unique(px)) > 3 or not 3 <= m.sum() <= 5 * px.shape[0]:
        return False
    if m.all(0).any() or m.all(1).any():
        return False
    return not (m[:, 0].any() and m[:, -1].any()) or not (m[0].any() and m[-1].any())


def _patch(px_high, px_low):
    """The letter crosses the boundary between the two rows (8x16 font or text off the 8-pixel grid)."""
    fc = np.bincount(px_high.ravel()).argmax()
    fb = np.bincount(px_low.ravel()).argmax()
    return (px_high[-1] != fc).any() and (px_low[0] != fb).any()


def excerpt_pos(md, indices=None):
    """Candidate text runs: sequences of letter-like tiles on a grid row,
    separated by 2+ empty tiles. A single space becomes None. Two rows whose letters cross
    the boundary become a row of 8x16 cells (key "top/bottom").
    Returns (plane, row, start column, run)."""
    seen = []
    for plane, grid in md.planes().items():
        cache = {}

        def px(e):
            e = int(e)
            if e not in cache:
                cache[e] = md.pattern(e)
            return cache[e]

        lines = [[px(e) for e in line[:64]] for line in grid[:32]]
        y = 0
        while y < len(lines):
            cel = [glyph(p) for p in lines[y]]
            if y + 1 < len(lines):
                high = [_high(a, b) for a, b in zip(lines[y], lines[y + 1])]
                joined = sum(_letter(c) and _patch(a, b) for c, a, b in zip(high, lines[y], lines[y + 1]))
                up = sum(map(_letter, cel))
                low = sum(_letter(glyph(p)) for p in lines[y + 1])
                # only joins when the double row has more whole letters than each half alone
                if joined >= 2 and joined >= max(up, low):
                    _note(indices, high, grid[y])
                    _segment(high, plane, y, seen)
                    y += 2
                    continue
            _note(indices, cel, grid[y])
            _segment(cel, plane, y, seen)
            y += 1
    return seen


def _note(indices, cel, line):
    """Glyph position in video memory: the font is usually in ASCII order (see decipher.by_order)."""
    if indices is not None:
        for c, e in zip(cel, line):
            if _letter(c):
                indices.setdefault(c, Counter())[int(e) & 0x7FF] += 1


def _letter(c):
    return c != EMPTY and not c.startswith("#")


def _high(a, b):
    ca, cb = glyph(a), glyph(b)
    if ca == EMPTY and cb == EMPTY:
        return EMPTY
    key_ = f"{ca.lstrip('#')}/{cb.lstrip('#')}"
    pxs = np.vstack([a, b])
    return key_ if looks_letter(pxs, pxs != np.bincount(pxs.ravel()).argmax()) else "#" + key_


def _segment(cel, plane, y, seen):
    # a line uses one font only: the most present one wins, the other cuts the run (frame glued to the text)
    thick = sum(c in THICK for c in cel)
    normal = sum(_letter(c) and c not in THICK for c in cel)
    cel = [("#" + c) if _letter(c) and (c in THICK) == (normal >= thick) else c for c in cel]
    current, x0 = [], 0

    def closes():
        while current and current[-1] is None:
            current.pop()
        letters = [c for c in current if c is not None]
        if len(letters) >= 2 and len(set(letters)) >= 2:
            seen.append((plane, y, x0, tuple(current)))
        current.clear()

    for x, c in enumerate(cel + [EMPTY, EMPTY]):
        if c.startswith("#"):  # border, graphic: cuts the run
            closes()
        elif c == EMPTY:
            if current and current[-1] is None:
                closes()
            elif current:
                current.append(None)
        else:
            if not current:
                x0 = x
            current.append(c)


def excerpts(md):
    return [t for *_, t in excerpt_pos(md)]


def collect(rom, minutes, indices=None, short_runs=3):
    """One long game to go deep, plus a few one-minute games from power-on with other buttons: the long game may
    never open the title menus (Alien Storm: OPTIONS and SOUND TEST were missed), and they hold a lot of the text.
    Splitting the long game instead read less (Cadash 116 -> 91 words)."""
    from retro_translator.core import progress
    progress.expect(int((minutes + short_runs) * 60 * 60 / 20))
    found = _game_run(rom, minutes, indices, random.Random(1))
    for p in range(short_runs):
        found.update(_game_run(rom, 1, indices, random.Random(2 + p)))
    return found


def _game_run(rom, minutes, indices, rnd):
    from retro_translator.core import progress
    md = consoles.for_rom(rom).Emulator(rom)
    found = Counter()
    direction = None  # held for ~1 s to walk through the stage and reach dialogs (3 games: 47 -> 55 words)
    for q in range(int(minutes * 60 * 60 / 20)):
        button = rnd.choice(["A", "B", "Y", "START", "A", "B", "UP", "DOWN", "LEFT", "RIGHT", None, None])
        if rnd.random() < 0.08:
            direction = rnd.choice(["UP", "DOWN", "LEFT", "RIGHT", None])
        md.run_frames(4, [b for b in (button, direction) if b])
        md.run_frames(16, [direction] if direction else [])
        found.update(set(t for *_, t in excerpt_pos(md, indices)))
        progress.tick()
        if q % 3 == 0:
            progress.show(md.frame)
    return found


def draw(excerpt, scale_=4):
    alt = max(mask(c).shape[0] for c in excerpt if c)
    img = np.full((alt + 4, max(8 * len(excerpt) + 8, 40)), 255, np.uint8)
    for i, c in enumerate(excerpt):
        if c:
            m = mask(c)
            img[2:2 + m.shape[0], 4 + 8 * i:12 + 8 * i][m] = 0
    im = Image.fromarray(img).resize((img.shape[1] * scale_, img.shape[0] * scale_), Image.NEAREST)
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()


# there is only one GPU: other jobs have priority and two loads together have crashed the machine
FREE_MIB = 3000  # idle ~1.4 GB; other GPU jobs go above that


def gpu_busy():
    """Busy = video memory used by others besides what our Ollama holds.
    A resident job manager is always running, so looking at processes said busy forever."""
    import subprocess
    try:
        used = int(subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                                   capture_output=True, text=True).stdout.split()[0])
    except Exception:
        return True
    try:
        ours = sum(m.get("size_vram", 0) for m in json.load(urllib.request.urlopen(OLLAMA.replace("/api/generate", "/api/ps"), timeout=5))["models"]) // 2**20
    except Exception:
        ours = 0
    return used - ours > FREE_MIB


def read_(excerpt):
    while gpu_busy():  # other GPU jobs have priority: the game pauses and waits, keeping the collection
        time.sleep(30)
    body = json.dumps({
        "model": VISION_MODEL, "stream": False, "options": {"temperature": 0}, "keep_alive": "30s",
        "prompt": "Transcribe the text in this image exactly, character by character, keeping spaces. "
                  "Output only the text. If it is not text, output NONE.",
        "images": [draw(excerpt)],
    }).encode()
    req = urllib.request.Request(OLLAMA, body, {"Content-Type": "application/json"})
    try:
        text = json.load(urllib.request.urlopen(req, timeout=120))["response"].strip()
    except OSError as e:  # one bad run does not bring down the round
        print("reading error:", e)
        return ""
    return "" if text == "NONE" or "\n" in text else text


def align(excerpt, text):
    """(glyph, letter) pairs if the reading matches the tiles and is consistent; otherwise an empty list."""
    pairs_ = _align(excerpt, text)
    forward, back = defaultdict(set), defaultdict(set)
    for g, l in pairs_:
        forward[g].add(l)
        back[l].add(g)
    # same glyph with two letters, or same letter with two glyphs in the same run: made-up reading
    if any(len(x) > 1 for x in forward.values()) or any(len(x) > 1 for x in back.values()):
        return []
    return pairs_


def _align(excerpt, text):
    words_t, current = [], []
    for c in excerpt:
        if c is None:
            if current:
                words_t.append(current)
            current = []
        else:
            current.append(c)
    if current:
        words_t.append(current)
    words_l = text.split()
    if len(words_t) == len(words_l) and all(len(a) == len(b) for a, b in zip(words_t, words_l)):
        return [p for a, b in zip(words_t, words_l) for p in zip(a, b)]
    tiles = [c for c in excerpt if c]
    letters = text.replace(" ", "")
    return list(zip(tiles, letters)) if len(tiles) == len(letters) else []


def learn(found, log=print):
    votes = defaultdict(Counter)
    suspects = set()  # glyphs from runs the AI said are not text
    # what looks most like a sentence first: more words, more letters, seen more often
    order = sorted(found.items(), key=lambda kv: (-min(_words(kv[0]), 3),
                                                     -sum(1 for c in kv[0] if c), -kv[1]))
    for excerpt, _ in order:
        glyphs = {c for c in excerpt if c}
        if all(votes[g] and votes[g].most_common(1)[0][1] >= 2 for g in glyphs):
            continue
        new_ = glyphs - set(g for g in votes if votes[g])
        if new_ and len(new_ & suspects) >= 0.5 * len(new_):
            continue
        text = read_(excerpt)
        pairs_ = align(excerpt, text)
        if not text:
            suspects |= glyphs
        log(f"{'ok ' if pairs_ else 'xx '} {text}")
        for g, l in pairs_:
            votes[g][l] += 1
    votes = {g: v for g, v in votes.items() if v}
    return letter_or_digit(fix_case({g: v.most_common(1)[0][0] for g, v in votes.items()}), found), votes


LOOKALIKES = {"0": "O", "1": "I", "5": "S"}


def letter_or_digit(table, found):
    """Many games use the same glyph for 0 and O (Air Diver: "MISSI0N", "0PTI0N"). If the glyph read as a
    digit sits next to letters more than to digits, it becomes the letter."""
    for g, l in list(table.items()):
        if l not in LOOKALIKES:
            continue
        letters = numbers = 0
        for excerpt in found:
            for i, c in enumerate(excerpt):
                if c == g:
                    for v in (excerpt[i - 1] if i else None, excerpt[i + 1] if i + 1 < len(excerpt) else None):
                        t = table.get(v, "")
                        letters += t.isalpha()
                        numbers += t.isdigit()
        if letters > numbers:
            table[g] = LOOKALIKES[l]
    return table


assert letter_or_digit({"o": "0", "m": "M", "n": "1"}, [("m", "o", "m"), ("n", "n")]) == {"o": "O", "m": "M", "n": "1"}


def _words(excerpt):
    return sum(1 for i, c in enumerate(excerpt) if c and (i == 0 or excerpt[i - 1] is None))


def _top(g):
    return int(np.argmax(mask(g).any(1)))


def fix_case(table):
    """c/C, o/O, s/S, v/V, w/W, x/X, z/Z have the same shape: decided by height,
    compared with unambiguous upper and lower case letters."""
    doubt = set("cosuvwxzCOSUVWXZ")
    tall = Counter(_top(g) for g, l in table.items() if l in "ABDEFHKLMNRT")
    low = Counter(_top(g) for g, l in table.items() if l in "aemnr")
    if not tall or not low:
        return table
    t_high, t_low = tall.most_common(1)[0][0], low.most_common(1)[0][0]
    if t_high == t_low:
        return table
    for g, l in table.items():
        if l in doubt:
            top = _top(g)
            if top == t_high:
                table[g] = l.upper()
            elif top == t_low:
                table[g] = l.lower()
    return table


def decode_(excerpt, table):
    return "".join(" " if c is None else table.get(c, "?") for c in excerpt)
