"""Groups the on-screen text runs into blocks, translates them and redraws the translated block
on the emulator image using the game's own font (accents built on top of the base letter)."""
import functools
import json
import os
import unicodedata
from retro_translator.core.translating import translation

import numpy as np

from retro_translator.core.reading.table import decode_, mask, excerpt_pos
from retro_translator import DATA



_DIC = {}


def looks_english(text):
    """A block with real words (a logo read as letters is not text; a lone name is not translated)."""
    import re
    from retro_translator.core.translating import translation
    if translation.SOURCE not in _DIC:  # words of the game's own language
        from retro_translator.core.reading import decipher
        _DIC[translation.SOURCE] = decipher.Dictionary(translation.SOURCE)
    dic = _DIC[translation.SOURCE]
    ps = re.findall(r"[^\W\d_]+", text.lower())  # "1PLAYER" counts as "player"
    # a lowercase letter followed by an uppercase one inside a word is machine code read as letters ("NuM": 68000 RTS)
    swapped = {w.lower() for w in re.findall(r"[A-Za-z]+", text) if re.search(r"[a-z][A-Z]", w)}
    real = [p for p in ps if (len(p) >= 2 or p in "ai") and p not in swapped and dic(p) > -3]
    loose = sum(len(p) == 1 for p in ps)
    # logo garbage read as letters: "RICH A A", "UP WIG A", "A DJ" (single letters and acronyms count against)
    return any(len(p) >= 3 for p in real) and len(real) >= 0.7 * len(ps) and loose <= len(ps) / 3


@functools.lru_cache(maxsize=4096)
def _icon(line, known):
    """`line` with its one unread cell as NUL: the rest is real words and no letter the table lacks makes words there."""
    from retro_translator.core.rewriting.rom_text import real_words
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"  # the cases the font has: a game with no lowercase draws none
    missing = {c for c in alphabet + alphabet.lower() if c.isupper() == any(k.isupper() for k in known) or
               c.islower() == any(k.islower() for k in known)} - set(known)
    return real_words(line.replace("\0", "").strip()) and not any(real_words(line.replace("\0", m)) for m in missing)


def blocks(md, table):
    """Groups left-aligned runs on nearby lines (dialog box, menu)."""
    list_ = []
    alt, width = md.frame.shape[:2]
    for plane, y, x, tr in sorted(excerpt_pos(md), key=lambda t: (t[0], t[2], t[1])):
        dx, dy = md.scroll(plane, y * 8)
        if (y * 8 - dy) % 1024 >= alt or (x * 8 + dx) % 512 >= width:
            continue  # off screen (font sheet kept in the plane, text already scrolled out)
        letters = [c for c in tr if c]
        unread = [k for k, c in enumerate(tr) if c and c not in table]
        if letters and len(unread) == 1 and unread[0] in (tr.index(letters[0]), len(tr) - 1 - tr[::-1].index(letters[-1])):
            k = unread[0]  # one cell at the edge ("①NEW GAME"): an icon or cursor when no missing letter makes a word there
            rest = tr[k + 1:] if k == tr.index(letters[0]) else tr[:k]
            if _icon(decode_(tr, {**table, tr[k]: "\0"}).strip(), frozenset(v for v in table.values() if v)):
                x, tr, letters, unread = (x + k + 1 if rest is not tr[:k] else x), rest, [c for c in rest if c], []
        if not letters or unread:
            continue  # a cell it cannot read may be a letter: translated, the line would come out with a wrong one
        text = decode_(tr, table).strip()
        for b in list_:
            if b["plane"] == plane and abs(b["x"] - x) <= 1 and 0 < y - b["lines"][-1][0] <= 2:
                b["lines"].append((y, text, tr))
                break
        else:
            list_.append({"plane": plane, "x": x, "lines": [(y, text, tr)]})
    return [b for b in list_ if looks_english(" ".join(t for _, t, _ in b["lines"]))]


def is_list(block):
    """Menu/list: short independent lines; otherwise prose that continues from one line to the next."""
    return all(len(t) <= 12 for _, t, _ in block["lines"])


class Overlay:
    def __init__(self, language, cache_file):
        self.language, self.file = language, cache_file
        self.cache = json.load(open(cache_file, encoding="utf-8")) if os.path.exists(cache_file) else {}
        self.context = []

    def __call__(self, text, limit=None):
        if text in self.cache:
            return self.cache[text]
        self.translate_many([text])
        return self.cache[text]

    def missing_(self, texts):
        return [t for t in texts if t not in self.cache]

    def translate_many(self, texts):
        """A single Apertium pass for all of them (may run in a thread: the game does not wait)."""
        new_ = self.missing_(dict.fromkeys(texts))
        if new_:
            self.cache.update(zip(new_, translation.translate_batch(new_, self.language)))  # no AI
            tmp = self.file + ".tmp"
            json.dump(self.cache, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            os.replace(tmp, self.file)


# ---------- font ----------

ACCENT = {  # (row, column) offsets relative to the centre, row 0 = right above the letter
    "́": [(-2, 1), (-1, 0)],                    # acute
    "̀": [(-2, -1), (-1, 0)],                   # grave
    "̂": [(-2, 0), (-1, -1), (-1, 1)],          # circumflex
    "̃": [(-2, -1), (-2, 0), (-2, 2), (-1, -2), (-1, 1)],  # tilde
    "̈": [(-1, -1), (-1, 1)],                   # diaeresis
}


def _mask(g):
    return mask(g.lstrip("#"))


def with_accent(m, marks):
    """The letter glyph with the accents (NFD marks) on top; makes room by removing a repeated row."""
    m = m.copy()
    cols = np.where(m.any(0))[0]
    center = int(round(cols.mean())) if len(cols) else 3
    if "̧" in marks:  # cedilla: raises the letter if needed and adds the tail below
        if m[-1].any() and not m[0].any():
            m = np.roll(m, -1, 0)
        m[-1, center] = True
        m[-1, center - 1] = True
    for mark in marks:
        if mark not in ACCENT:
            continue
        top = int(np.argmax(m.any(1)))
        while top < 2:  # no room for the accent: lowers the letter if possible, otherwise removes a repeated row
            if not m[-1].any():
                m = np.roll(m, 1, 0)
            else:
                lines = np.flatnonzero(m.any(1))
                rep = [i for i in lines[:-1] if (m[i] == m[i + 1]).all()]
                i = rep[len(rep) // 2] if rep else lines[len(lines) // 2]
                m = np.vstack([np.zeros((1, 8), bool), np.delete(m, i, 0)])
            top = int(np.argmax(m.any(1)))
        for dl, dc in ACCENT[mark]:
            lin, col = top + dl, center + dc
            if 0 <= lin < 8 and 0 <= col < 8:
                m[lin, col] = True
    return m


class Font:
    def __init__(self, table):
        self.glyphs = {}
        for g, letter in table.items():
            m = _mask(g)
            # ponytail: only the 8x8 font is redrawn; the 8x16 one is read but not redrawn yet
            if m.shape[0] == 8 and not (m.all(0).any() or m.all(1).any()):  # a full row/column is a frame
                self.glyphs.setdefault(letter, []).append(m)
        # several glyphs read as the same letter (a stray one, like "^" read as "A"): the one closest to how that
        # letter usually looks in other games
        for letter, ms in self.glyphs.items():
            ref = _spare().get(letter) if len(ms) > 1 else None
            if ref is not None and ref.shape == (8, 8):
                ms.sort(key=lambda m: -(m == ref).sum())
            self.glyphs[letter] = ms[0]
        self.own = set(self.glyphs)  # letters of the game's own font (drawn ones are cached in glyphs too)

    def __getitem__(self, ch):
        if ch == " ":
            return np.zeros((8, 8), bool)
        if ch in self.glyphs:
            return self.glyphs[ch]
        decomp = unicodedata.normalize("NFD", ch)
        base, marks = decomp[0], decomp[1:]
        m = self._base(base)
        if m is None:
            return self.glyphs.get("?", np.zeros((8, 8), bool))
        m = with_accent(m, marks)
        self.glyphs[ch] = m
        return m

    def _base(self, ch):
        for c in (ch, ch.swapcase()):
            if c in self.own:
                return self.glyphs[c]
        for c in (ch, ch.swapcase()):  # the game did not show the letter: its most common glyph in other games
            if c in _spare():
                return _spare()[c]
        return None


_SPARE = {}


def _spare():
    if not _SPARE:
        import glob
        from collections import Counter
        votes = {}
        for path_ in glob.glob(os.path.join(DATA, "tables", "*.json")):
            for g, l in json.load(open(path_, encoding="utf-8")).items():
                if len(l) == 1 and "/" not in g:
                    votes.setdefault(l, Counter())[g.lstrip("#")] += 1
        # a badly deciphered game votes for a wrong drawing ("Y" read as "z"): among the most voted drawings of a
        # letter, the one shaped most like that letter in GNU Unifont (8x16, halved to 8 rows)
        from retro_translator.core.reading import cjk
        ref = _unifont_latin()
        for l, c in votes.items():
            cands = [g for g, _ in c.most_common(6)]
            _SPARE[l] = mask(cands[0])
            if l in ref:
                r = cjk._blur(ref[l]).ravel()
                shape = lambda g: float(cjk._blur(mask(g).astype(np.float32)).ravel() @ r)
                cands.sort(key=lambda g: -(shape(g) + 0.02 * np.log(c[g])))
                # no game drew it recognisably: Unifont's own drawing
                _SPARE[l] = mask(cands[0]) if shape(cands[0]) >= 0.4 else ref[l] > 0
    return _SPARE


def _narrow(m, width_):
    """(narrowed glyph, whether a stroke had to be cut)."""
    m, cut = m.copy(), False
    while m.shape[1] > width_:
        cols = [c for c in (0, m.shape[1] - 1) if not m[:, c].any()]
        if not cols:
            same = [c for c in range(1, m.shape[1]) if (m[:, c] == m[:, c - 1]).all()]
            cols = sorted(same, key=lambda c: abs(c - m.shape[1] / 2))[:1]
            if not cols:
                cols, cut = [m.shape[1] // 2], True
        m = np.delete(m, cols[0], 1)
    return m, cut


def _unifont_latin():
    """{letter: 8x8 drawing} of the printable ASCII characters in GNU Unifont, halved from 16 rows."""
    import gzip
    out = {}
    with gzip.open(os.path.join(DATA, "kanji", "unifont.hex.gz"), "rt") as f:
        for line in f:
            c, h = line.strip().split(":")
            if 0x21 <= int(c, 16) <= 0x7E and len(h) == 32:
                rows = np.array([[int(h[i * 2:i * 2 + 2], 16) >> (7 - j) & 1 for j in range(8)] for i in range(16)])
                out[chr(int(c, 16))] = np.maximum(rows[2:16:2], rows[3:16:2])[:, :].astype(np.float32)[:7]
    return {k: np.vstack([v, np.zeros((1, 8), np.float32)]) for k, v in out.items()}


def squeeze(m, width_):
    """The glyph narrowed to `width_` columns keeping its shape: empty edge columns go first, then a column equal to
    its neighbour (the second column of a 2-pixel stroke), the one nearest the middle; one blank column is kept so
    letters do not touch."""
    n, _ = _narrow(m, width_)
    if width_ < m.shape[1] and n[:, 0].any() and n[:, -1].any():
        g, cut = _narrow(m, width_ - 1)
        if not cut:  # wide letters (m, w) keep their strokes and touch instead
            n = np.pad(g, ((0, 0), (0, 1)))
    return n


def wrap_(text, width_):
    lines, current = [], ""
    for p in text.split():
        if current and len(current) + 1 + len(p) > width_:
            lines.append(current)
            current = p
        else:
            current = f"{current} {p}" if current else p
    return lines + ([current] if current else [])


def free_width(md, block):
    """How many cells the box has from x, up to the frame or the screen edge."""
    grid = md.planes()[block["plane"]]
    screen = 40 if md.reg[12] & 1 else 32
    y = block["lines"][0][0]
    x = block["x"]
    while x < min(screen, grid.shape[1]):
        from retro_translator.core.reading.table import glyph
        if glyph(md.pattern(int(grid[y, x]))).startswith("#"):
            break
        x += 1
    return x - block["x"]


def draw_block(md, frame_, block, lines_pt, font_, clean=None):
    """Erases the block's original text and writes the translated lines in its place."""
    ys = [y for y, _, _ in block["lines"]]
    width_ = free_width(md, block)
    # does it fit? otherwise squeeze the font (7 and then 6 px per letter)
    for advance in (8, 7, 6):
        fits = width_ * 8 // advance
        if all(len(l) <= fits for l in lines_pt) and len(lines_pt) <= len(ys) + 0:
            break
    dx, dy = md.scroll(block["plane"], ys[0] * 8)
    alt, width_px = frame_.shape[:2]
    x0 = (block["x"] * 8 + dx) % 512
    # colours: background = most common in the text area; letter = most common where the glyph has pixels
    y0 = (ys[0] * 8 - dy) % 1024
    area = frame_[y0:y0 + 8, x0:x0 + 8 * len(block["lines"][0][2])]
    if area.size == 0:
        return
    colors, n = np.unique(area.reshape(-1, 3), axis=0, return_counts=True)
    order = np.argsort(-n)
    background = colors[order[0]]
    letter = colors[order[1]] if len(order) > 1 else 255 - background
    # letter colour = the most common in the pixels of the original letters themselves (the background may move)
    cells_ = [(area[:, 8 * k:8 * k + 8], mask(c.lstrip("#"))[:8]) for k, c in enumerate(block["lines"][0][2])
               if c and area[:, 8 * k:8 * k + 8].shape[:2] == (8, 8)]
    if cells_:
        c, k = np.unique(np.vstack([a[m] for a, m in cells_]), axis=0, return_counts=True)
        letter = c[np.argmax(k)]
    # per pixel row: fonts with a vertical gradient keep it (one colour smeared the gradient)
    row_color = np.array([letter] * 8)
    for r in range(8):
        fil = [a[r][m[r]] for a, m in cells_ if m[r].any()]
        if fil:
            c, k = np.unique(np.vstack(fil), axis=0, return_counts=True)
            row_color[r] = c[np.argmax(k)]
    for y, _, _ in block["lines"]:
        py = (y * 8 - dy) % 1024
        if clean is not None:
            frame_[py:py + 8, x0:x0 + width_ * 8] = clean[py:py + 8, x0:x0 + width_ * 8]
        else:
            frame_[py:py + 8, x0:x0 + width_ * 8] = background
    for i, text in enumerate(lines_pt[:len(ys)]):
        py = (ys[i] * 8 - dy) % 1024  # on the original line (line spacing may vary)
        for j, ch in enumerate(text):
            px = x0 + j * advance
            m = font_[ch]
            if advance < 8:
                m = squeeze(m, advance)
            if py + 8 <= alt and px + m.shape[1] <= width_px:
                frame_[py:py + 8, px:px + m.shape[1]][m] = np.broadcast_to(row_color[:, None], m.shape + (3,))[m]


def clean_background(md, list_):
    """Frame with the blocks' text erased in video memory itself: each letter becomes the line's space tile,
    and the emulator draws what is behind it (box, wood, sky). The state is restored afterwards."""
    state = md.save()
    planes = md.planes()
    for b in list_:
        grid = planes[b["plane"]]
        values_, tally = np.unique(grid, return_counts=True)
        blank = values_[np.argmax(tally)]  # no space in the whole block: the most common tile of the plane
        for y, _, tr in b["lines"]:  # a line without a space uses the space of another line of the block (the box background)
            k = next((k for k, c in enumerate(tr) if c is None), None)
            if k is not None:
                blank = grid[y % grid.shape[0]][(b["x"] + k) % grid.shape[1]]
                break
        for y, _, tr in b["lines"]:
            line = grid[y % grid.shape[0]]
            spaces = [line[(b["x"] + k) % grid.shape[1]] for k, c in enumerate(tr) if c is None] or [blank]
            for k in range(len(tr)):
                line[(b["x"] + k) % grid.shape[1]] = spaces[0]
    md.run_frames(1)
    clean = md.frame.copy()
    md.load(state)
    return clean


def add_accents(md, table, font_, accents):
    """Patches (y0, y1, x0, x1, pixels) that add accents to letters the game drew without them (the ROM font
    has no accents). accents: unaccented word -> accented word, from this game's translations. 8x8 font only."""
    import re
    if not accents:
        return []
    out_ = []
    alt, width = md.frame.shape[:2]
    for plane, y, x, tr in excerpt_pos(md):
        text = "".join(" " if c is None else table.get(c, "?") for c in tr)
        dx, dy = md.scroll(plane, y * 8)
        sy = (y * 8 - dy) % 1024
        if sy + 8 > alt:
            continue
        for m in re.finditer(r"[A-Za-z]+", text):
            new = accents.get(m.group().upper())
            if not new or len(new) != len(m.group()):
                continue
            for i, (a, b) in enumerate(zip(m.group(), new)):
                if a.upper() == b:
                    continue
                g = tr[m.start() + i]
                sx = ((x + m.start() + i) * 8 + dx) % 512
                if "/" in g or sx + 8 > width:
                    continue
                cel = md.frame[sy:sy + 8, sx:sx + 8]
                old_ = _mask(g)
                if old_.shape != (8, 8) or not old_.any() or old_.all():
                    continue
                color = np.unique(cel[old_].reshape(-1, 3), axis=0, return_counts=True)
                background = np.unique(cel[~old_].reshape(-1, 3), axis=0, return_counts=True)
                if len(background[0]) != 1:
                    continue  # patterned background: painting a flat background would spoil the frame
                color, background = color[0][color[1].argmax()], background[0][0]
                marks = unicodedata.normalize("NFD", b)[1:]  # accent on the on-screen glyph itself (the table's case may be wrong)
                px = np.where(with_accent(old_, marks)[..., None], color, background).astype(np.uint8)
                out_.append((sy, sy + 8, sx, sx + 8, px))
    return out_


def requests(list_):
    """Texts the translator will need for these blocks (menu: line by line; prose: the whole block)."""
    return [t for b in list_ for t in ([t for _, t, _ in b["lines"]] if is_list(b)
                                       else [" ".join(t for _, t, _ in b["lines"])])]


def translate_frame(md, table, overlay, font_, list_=None):
    frame_ = md.frame.copy()
    list_ = blocks(md, table) if list_ is None else list_
    if not list_:
        return frame_
    clean = clean_background(md, list_)
    if os.environ.get("DEBUG"):
        from PIL import Image
        Image.fromarray(clean).save("output/clean.png")
    for b in list_:
        width = free_width(md, b)
        cap = len(b["lines"]) * width * 8 // 6
        if is_list(b):
            lines_pt = [overlay(t, width * 8 // 6) for _, t, _ in b["lines"]]
        else:
            text = " ".join(t for _, t, _ in b["lines"])
            pt = overlay(text, cap)
            lines_pt = wrap_(pt, width)
            for advance in (7, 6):
                if len(lines_pt) <= len(b["lines"]):
                    break
                lines_pt = wrap_(pt, width * 8 // advance)
        draw_block(md, frame_, b, lines_pt, font_, clean)
    return frame_


def patches(md, table, overlay, font_, list_):
    """Pieces of the translated screen (y0, y1, x0, x1, pixels) pasted on top of every frame while the text does not change."""
    original = md.frame.copy()
    frame_ = translate_frame(md, table, overlay, font_, list_)
    changes = (frame_ != original).any(2)
    lines = np.where(changes.any(1))[0]
    if not len(lines):
        return []
    out_ = []
    for b in list_:  # one rectangle per block, only over its text area (the rest of the screen may be animated)
        dx, dy = md.scroll(b["plane"], b["lines"][0][0] * 8)
        y0 = (b["lines"][0][0] * 8 - dy) % 1024
        y1 = min(frame_.shape[0], (b["lines"][-1][0] * 8 - dy) % 1024 + 8)
        x0 = (b["x"] * 8 + dx) % 512
        x1 = min(frame_.shape[1], x0 + free_width(md, b) * 8)
        if changes[y0:y1, x0:x1].any():
            out_.append((y0, y1, x0, x1, frame_[y0:y1, x0:x1].copy()))
    return out_
