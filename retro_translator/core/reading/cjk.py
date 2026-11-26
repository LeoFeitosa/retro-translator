"""Reads Japanese and Chinese text on screen. These games draw each character with 2x2 tiles (16x16) or one tile
(8x8, with the voicing mark often in the tile above): the cells are put together from the tile grids, ink is told from background by colour, and each cell is
matched by shape against GNU Unifont, Shinonome and Misaki (both blurred, so a game's own lettering style still matches), then each line
is read as the most likely sequence of characters (character pairs seen in words of the language). No AI."""
import collections
import gzip
import os
import re
import unicodedata

import numpy as np
from retro_translator import DATA

RANGES = {"ja": [(0x3041, 0x30FF)], "zh": []}  # kana; kanji/hanzi come from the frequency list of the language
MARKS = "。、！？…「」・ー"
SAFE = 0.6  # shape score above which a glyph is not overruled by the font order of a weakly supported list
CLEAR_SHAPE = 0.7  # mean shape score of a line with no glyph placed by the font order that is still text
MARGIN = 0.12  # a character this close to the best shape may be the right one; the language then picks
STRONG = 6  # anchors that make a list's place certain: its order then beats shapes (similar kana: ぁ/ぉ)
_REF = {}


def _blur(a, r=1):
    """Box blur, enough to compare shapes of different lettering styles."""
    a = np.pad(a.astype(np.float32), r, mode="edge")
    for axis_ in (0, 1):
        a = sum(np.roll(a, k, axis_) for k in range(-r, r + 1)) / (2 * r + 1)
    a = a[r:-r, r:-r]
    a = a - a.mean()
    return a / (np.linalg.norm(a) + 1e-9)


def references(language, size_=16):
    """(characters, blurred tam x tam shapes, log-frequency prior, character-pair frequencies) of the language."""
    if (language, size_) in _REF:
        return _REF[language, size_]
    from wordfreq import top_n_list
    freq, pairs = collections.Counter(), collections.Counter()
    for i, w in enumerate(top_n_list(language, 50000)):
        for ch in w:
            freq[ch] += 1 / (i + 50)
        for a, b in zip(w, w[1:]):
            pairs[a, b] += 1 / (i + 50)
    for group in ("0123456789", "！？…・"):  # numbers and "！？": wordfreq has no pairs of them
        for a in group:
            for b in group:
                pairs[a, b] += 0.01
    chars, shapes = [], []
    # two drawing styles of each 16x16 character (one at 8x8), each also in bold
    for font_ in ("unifont.hex.gz", "shinonome16.hex.gz") if size_ == 16 else ("misaki8.hex.gz",):
        with gzip.open(os.path.join(DATA, "kanji", font_), "rt") as f:
            for line in f:
                c, h = line.strip().split(":")
                ch = chr(int(c, 16))
                cjk = 0x3041 <= ord(ch) <= 0x30FF or 0x4E00 <= ord(ch) <= 0x9FFF
                if "０" <= ch <= "９":
                    ch = chr(ord(ch) - 0xFEE0)  # scores and prices: written as plain digits
                elif not (cjk and freq[ch] > 0 or ch in MARKS or any(a <= ord(ch) <= b for a, b in RANGES[language])):
                    continue
                w = len(h) // size_ * 4
                b = np.array([[int(h[i * w // 4:(i + 1) * w // 4], 16) >> (w - 1 - j) & 1 for j in range(w)]
                              for i in range(size_)], np.float32)
                if w < size_:
                    b = np.pad(b, ((0, 0), ((size_ - w) // 2, (size_ - w) // 2)))
                for style in (b, np.maximum(b, np.roll(b, 1, 1))):  # also bold: game fonts often draw 2-pixel strokes
                    chars.append(ch)
                    shapes.append(_blur(style).ravel())
    for a in set(chars) - set("0123456789"):  # after a word a sentence ends ("だ！"), a number seldom starts
        for b in "！？。、…" + ("ー" if "ぁ" <= a <= "ヶ" else ""):
            pairs[a, b] += 0.001
    # a digit alone is as rare in game text as a punctuation mark (which wordfreq does not count): "？" is not "7"
    prior = np.array([np.log((0 if c.isdigit() else freq[c]) + 1e-4) for c in chars], np.float32)
    _REF[language, size_] = (chars, np.array(shapes), prior, pairs)
    return _REF[language, size_]


def _scores(shapes, ink):
    """Score of each reference shape: the best over 1-pixel shifts of the cell."""
    return np.max([shapes @ _blur(np.roll(np.roll(ink, dy, 0), dx, 1)).ravel()
                   for dy in (-1, 0, 1) for dx in (-1, 0, 1)], axis=0)


def _top(s, chars, k):
    """The k best characters (each once: two fonts draw each character)."""
    out_, seen = [], set()
    for i in np.argsort(-s):
        if chars[i] not in seen:
            seen.add(chars[i])
            out_.append(i)
            if len(out_) == k:
                break
    return out_


def _body(g):
    """An 8x8 drawing big enough to be a character (dots and strokes of scenery look like small kana)."""
    t = np.unpackbits(np.frombuffer(g, np.uint8)).reshape(8, 8)
    ys, xs = np.nonzero(t)
    return len(ys) >= 8 and np.ptp(ys) >= 3 and np.ptp(xs) >= 3


def _mark(ink):
    """"゛" or "゜" if an 8x8 cell holds only a small voicing mark (゜ is a ring: background enclosed by ink)."""
    if ink is None or not 2 <= ink.sum() <= 12:
        return None
    t = np.pad(ink, 1)
    hole = ~t[1:-1, 1:-1] & t[:-2, 1:-1] & t[2:, 1:-1] & t[1:-1, :-2] & t[1:-1, 2:]
    return "\u309a" if hole.any() else "\u3099"


def _cell(blocks):
    """16x16 ink mask from 2x2 tiles of colour indices (or 8x8 from one tile): the background is the most common
    colour of the cell edge (a dense kanji has more ink than background inside)."""
    px = np.vstack([np.hstack(b) for b in blocks])
    if len(np.unique(px)) > 3:
        return None  # scenery: text is ink on a background (plus a shadow at most)
    edge = np.concatenate([px[0], px[-1], px[:, 0], px[:, -1]])
    colors, n = np.unique(edge, return_counts=True)
    return px != colors[n.argmax()]


class Reader:
    """Reads the text lines of a game, in 16x16 cells (2x2 tiles) and 8x8 ones (one tile). map_: {1-bit drawing:
    character} known from the font order (16x16: in the ROM, font_in_rom; 8x8: the tile numbers in video memory);
    other cells are matched by shape, never as a character the font already has elsewhere."""

    def __init__(self, language="ja", map_=None, data=None, minimum=0.45, k=40):
        self.ref = {t: references(language, t) for t in (16, 8)}
        self.pairs = self.ref[16][3]
        self.map_, self.minimum, self.k, self.cache = dict(map_ or {}), minimum, k, {}
        self.data, self.seen_shapes, self.new_, self.scores = data, {}, 0, {}  # data: ROM, to keep learning while playing
        self.tiles = {}  # 8x8 drawing -> its tile number (the font order of an 8x8 font)
        self._taken()

    def _taken(self):
        used_ = set(self.map_.values())
        self.outside = {t: np.array([c in used_ for c in r[0]]) for t, r in self.ref.items()}
        self.cache = {}

    def _s(self, packed, ink):
        if packed not in self.scores:
            self.scores[packed] = _scores(self.ref[len(ink)][1], ink)
        return self.scores[packed]

    def _shape(self, packed, ink):
        """Shape candidates alone (what the font order is voted with)."""
        if packed not in self.seen_shapes:
            s, chars = self._s(packed, ink), self.ref[len(ink)][0]
            top = _top(s, chars, 8)
            self.seen_shapes[packed] = [(float(s[i]), chars[i]) for i in top] if s[top[0]] >= self.minimum else None
            self.new_ += self.seen_shapes[packed] is not None
        return self.seen_shapes[packed]

    def font_map(self):
        """{drawing: character} placed by the font order from the glyphs seen so far."""
        seen = {g: c for g, c in self.seen_shapes.items() if c}
        g16 = {g: c for g, c in seen.items() if len(g) == 32}
        g8 = {g: c for g, c in seen.items() if len(g) == 8 and g in self.tiles and _body(g)}
        new = font_in_rom(self.data, g16) if self.data else {}
        eight = _order({g: 32 * self.tiles[g] for g in g8}, g8)
        # short lists (small kana) match scenery dots easily: they count only next to the main syllabary
        if sum("SMALL" not in unicodedata.name(c, "SMALL") for c in eight.values()) >= 2 * STRONG:
            new.update(eight)
        return new

    def learn(self):
        """Places the glyphs seen so far by the font order (new screens bring new characters). True if the map
        grew."""
        if self.new_ < 5:
            return False
        self.new_ = 0
        new = self.font_map()
        if len(new) <= len(self.map_):
            return False
        self.map_.update(new)
        self._taken()
        return True

    def candidates(self, ink):
        """[(score, character)] for an ink mask, or None if it does not look like a character."""
        packed = np.packbits(ink.astype(np.uint8), axis=1).tobytes()
        if packed in self.map_:
            return [(2.0, self.map_[packed])]
        if self._shape(packed, ink) is None:
            return None
        if packed not in self.cache:
            s = self._s(packed, ink).copy()
            chars, prior = self.ref[len(ink)][0], self.ref[len(ink)][2]
            s[self.outside[len(ink)]] = -9
            top = [i for i in _top(s, chars, self.k) if s[i] >= s.max() - MARGIN]
            self.cache[packed] = [(float(s[i] + 0.02 * prior[i]), chars[i]) for i in top]
        return self.cache[packed]

    def read_(self, md):
        """Text lines on screen: [(plane, row, column, number of cells, text, [ink masks], score)]. A line is 2+
        cells in a row that read as characters: 16x16 (at either column parity) or 8x8 (those need a glyph placed
        by the font order: any small drawing looks like some kana)."""
        lines = []
        for plane, grid in md.planes().items():
            cache = {}

            def px(e):
                if e not in cache:
                    cache[e] = md.pattern(e)
                return cache[e]

            alt, width = min(len(grid), 32), min(len(grid[0]), 64)
            for step in (2, 1):
                for y in range(alt - step + 1):
                    for parity in range(step):
                        current, blank = [], 0
                        for x in range(parity, width - step + 1, step):
                            ents = [[int(grid[y + i][x + j]) for j in range(step)] for i in range(step)]
                            cand, ink = None, None
                            if not all(e & 0x7FF == 0 for r in ents for e in r):
                                ink = _cell([[px(e) for e in r] for r in ents])
                                if ink is not None and 0.02 < ink.mean() < 0.6:  # "ー" has little ink
                                    cand = self.candidates(ink)
                                    if cand and step == 1:
                                        self.tiles[np.packbits(ink.astype(np.uint8), axis=1).tobytes()] = \
                                            ents[0][0] & 0x7FF
                                        if y:  # 8x8 fonts draw the voicing mark in the row above
                                            m = _mark(_cell([[px(int(grid[y - 1][x]))]]))
                                            if m:
                                                cand = [(sc, unicodedata.normalize("NFC", c + m)) for sc, c in cand]
                            if cand:
                                if blank == 1 and current:  # one blank cell: a space between phrases
                                    current.append((x - step, [(0.0, " ")], np.zeros_like(ink)))
                                current.append((x, cand, ink))
                                blank = 0
                            elif ink is not None and not ink.any() or all(e & 0x7FF == 0 for r in ents for e in r):
                                blank += 1
                                if blank > 1:
                                    if len(current) >= 2:
                                        lines.append((plane, y, current))
                                    current = []
                            else:
                                if len(current) >= 2:
                                    lines.append((plane, y, current))
                                current, blank = [], 0
                        if len(current) >= 2:
                            lines.append((plane, y, current))
        out_ = []
        for plane, y, cells in lines:
            if len(cells[0][2]) == 8 and not any(c[0][0] == 2.0 for _, c, _ in cells):
                continue
            text, score = _best([(x, c) for x, c, _ in cells], self.pairs)
            out_.append((score / sum(c[0][1] != " " for _, c, _ in cells), plane, y, cells[0][0], len(cells), text,
                          [t for _, _, t in cells]))
        # a line read at both column parities or one row off: keep the one with the best mean score
        out_.sort(key=lambda l: -l[0])
        taken, final = set(), []
        for score, plane, y, x, n, text, inks in out_:
            step = len(inks[0]) // 8
            area = {(plane, yy, xx) for yy in range(y, y + step) for xx in range(x, x + step * n)}
            if area & taken:
                continue
            taken |= area
            final.append((plane, y, x, n, text, inks, score))
        return sorted(final, key=lambda l: (l[0], l[1], l[2]))


def read_(md, language="ja"):
    return [l[:5] for l in Reader(language).read_(md)]


def _best(cells, pairs, weight=0.03):
    beam = [(0.0, "")]
    for _, cand in cells:
        new = []
        for s0, t in beam:
            for s1, c in cand:
                b = np.log(pairs[t[-1], c] + 1e-6) if t else 0.0
                new.append((s0 + s1 + weight * b, t + c))
        beam = sorted(new, reverse=True)[:30]
    return beam[0][1], beam[0][0]


def _sequences():
    """Orders a game font may store kana in (each list on its own; a table may hold several one after another)."""
    import unicodedata
    seqs, parts = [], {}
    for base in (0x3041, 0x30A1):  # hiragana, katakana
        todos = [chr(c) for c in range(base, base + 0x56) if chr(c) not in "ゔゕゖ"]  # rare in games
        smalls = [c for c in todos if "SMALL" in unicodedata.name(c, "")]
        voiced = [c for c in todos if len(unicodedata.normalize("NFD", c)) > 1]
        plain = [c for c in todos if c not in smalls and c not in voiced]
        without_wi = [c for c in plain if unicodedata.name(c, "").split()[-1] not in ("WI", "WE")]
        without_wo = [c for c in without_wi if unicodedata.name(c, "").split()[-1] != "WO"]  # "...ろわん", を elsewhere
        dakuten = [c for c in voiced if unicodedata.normalize("NFD", c)[1] == "゙"]
        handaku = [c for c in voiced if unicodedata.normalize("NFD", c)[1] == "゚"]
        small_base = [c for c in smalls if unicodedata.name(c).split()[-1] in ("A", "I", "U", "E", "O")]
        small_y = [c for c in smalls if unicodedata.name(c).split()[-1] in ("YA", "YU", "YO")]
        small_tu = [c for c in smalls if unicodedata.name(c).split()[-1] == "TU"]
        small = small_base + small_y + small_tu
        seqs += [todos, plain, without_wi, without_wo, voiced, dakuten + handaku, dakuten, handaku, small,
                 small_base + small_tu + small_y, smalls]
        parts[base] = (without_wi, small, dakuten + handaku)
    (h, hp, hs), (k, kp, ks) = parts[0x3041], parts[0x30A1]
    # lists stored one after the other: hiragana then katakana, plain then small, voiced of both
    seqs += [h + hp + k + kp, hp + k + kp, h + hp + k, hs + ks, ["。", "、"] + h + hp + k + kp, ["。"] + h + hp + k + kp]
    return [s for s in seqs if len(s) >= 5]


def _sign(candidates, letter):
    """The shape is clearly a punctuation mark (「」…) and `letter` is not, or the other way round."""
    score, top = candidates[0]
    return score >= SAFE + 0.15 and (top in MARKS) != (letter in MARKS)


def font_in_rom(data, glyphs, minimum=3):
    """{glyph bytes: character} for glyphs found in the ROM as 16x16 1-bit drawings (32 bytes each), from the order
    of the table they sit in: a few glyphs recognised by shape fix where a kana list starts in the table, and every
    glyph of that list then gets its exact character. glyphs: {32-byte drawing: [(score, character)] candidates}."""
    pos = {}
    for g in glyphs:
        p = data.find(g)
        if p >= 0:
            pos[g] = p
    return _order(pos, glyphs, minimum)


def _order(pos, glyphs, minimum=3):
    """Font order: pos {glyph: place, 32 per glyph} -> {glyph: character} (see font_in_rom)."""
    votes = collections.Counter()  # (sequence, table start in bytes) -> anchors that agree
    for si, seq in enumerate(_sequences()):
        place = {c: j for j, c in enumerate(seq)}
        for g, p in pos.items():
            for _, c in glyphs[g]:
                if c in place:
                    votes[si, p - 32 * place[c]] += 1
    seqs, final, taken, ends = _sequences(), {}, set(), []
    for (si, start), n in votes.most_common():
        if n < minimum:
            break
        seq = seqs[si]
        band = range(start, start + 32 * len(seq), 32)
        new_ = {g: seq[(p - start) // 32] for g, p in pos.items() if p in band and (p - start) % 32 == 0}
        if any(g in taken for g in new_):
            continue  # a list already placed there with more support
        against = [g for g, c in new_.items() if c not in {x for _, x in glyphs[g]}]
        if len(against) > len(new_) / 2:
            continue  # the shapes mostly disagree: a wrong start
        for g in list(new_):
            if g in against and n < STRONG and glyphs[g][0][0] >= SAFE or _sign(glyphs[g], new_[g]):
                del new_[g]  # this glyph is clearly something else (the list may have a gap here)
        final.update(new_)
        taken |= set(new_)
        ends.append(start + 32 * len(seq))
    # the next list often starts right where one ends (hiragana, then small kana, then katakana): a single glyph
    # recognised there is enough, as long as none clearly disagrees
    while ends:
        end = ends.pop()
        best = None
        for seq in seqs:
            for slack in range(3):
                start = end + 32 * slack
                new_ = {g: seq[(p - start) // 32] for g, p in pos.items()
                         if start <= p < start + 32 * len(seq) and (p - start) % 32 == 0 and g not in taken}
                matches = sum(c in {x for _, x in glyphs[g]} for g, c in new_.items())
                against = sum(c not in {x for _, x in glyphs[g]} and glyphs[g][0][0] >= SAFE for g, c in new_.items())
                if matches and against <= matches and (best is None or matches > best[0]):
                    best = (matches, new_, start + 32 * len(seq))
        if best:
            best = (best[0], {g: c for g, c in best[1].items() if not _sign(glyphs[g], c)}, best[2])
            final.update(best[1])
            taken |= set(best[1])
            ends.append(best[2])
    return final


def learn(rom, language="ja", minutes=10, short_runs=3):
    """{drawing: character} for this game, plus how many glyphs were seen: plays it like the Latin collection (one
    long game and a few short ones from power-on) and places the glyphs found in the ROM by the font order."""
    import random
    from retro_translator import consoles
    from retro_translator.core import progress
    reader = Reader(language)
    progress.expect(int((minutes + short_runs) * 60 * 60 / 20))
    for p, mins in enumerate([minutes] + [1] * short_runs):
        md, rnd = consoles.for_rom(rom).Emulator(rom), random.Random(1 + p)
        for q in range(int(mins * 60 * 60 / 20)):
            b = rnd.choice(["A", "B", "Y", "START", "A", "B", "UP", "DOWN", "LEFT", "RIGHT", None, None])
            md.run_frames(4, [b] if b else [])
            md.run_frames(16)
            if q % 10 == 0:
                reader.read_(md)
            progress.tick()
            if q % 3 == 0:
                progress.show(md.frame)
    reader.data = bytes(consoles.for_rom(rom).read_rom(rom))
    return reader.font_map(), sum(1 for c in reader.seen_shapes.values() if c)


_KANA = dict(zip(
    "アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲンガギグゲゴザジズゼゾダヂヅデド"
    "バビブベボパピプペポヴ",
    "a i u e o ka ki ku ke ko sa shi su se so ta chi tsu te to na ni nu ne no ha hi fu he ho ma mi mu me mo ya yu yo "
    "ra ri ru re ro wa o n ga gi gu ge go za ji zu ze zo da ji zu de do ba bi bu be bo pa pi pu pe po vu".split()))


def romaji(text):
    """Kana written in Latin letters (Hepburn), for names: a name is not translated ("オババ" -> "Obaba")."""
    out_, double = "", False
    for ch in text:
        ch = chr(ord(ch) + 0x60) if "ぁ" <= ch <= "ゖ" else ch  # hiragana -> katakana
        if ch in "ャュョ" and out_:
            out_ = out_[:-1] + ("" if out_[-2:-1] in ("h", "j") else "y") + "auo"["ャュョ".index(ch)]
        elif ch in "ァィゥェォ" and out_:
            out_ = out_[:-1] + "aiueo"["ァィゥェォ".index(ch)]
        elif ch == "ッ":
            double = True
        elif ch in _KANA:
            r = _KANA[ch]
            out_ += (r[0] if double and r[0] not in "aiueon" else "") + r
            double = False
        elif ch not in "ー・":
            out_ += ch
    return out_[:1].upper() + out_[1:]


def blocks(md, reader):
    """Text boxes: lines of one plane at the same column, one below the other. With a font order known, a line
    needs a cell that is a drawing of that font (scenery also looks like kanji to the shape matching), or must sit
    right below such a line inside the same box (menu items written in kanji: "日記1"). A box with no sentence
    punctuation in any line is a list of items: each line is translated on its own. A line right above one that
    opens a quote (「) is the speaker's name: an item of its own, written in Latin letters, not translated."""
    read = reader.read_(md)
    kept, doubtful = [], []
    for plane, y, x, n, text, inks, score in read:
        line = (plane, y, x, n, text, len(inks[0]) // 8)
        fixed = reader.map_ and sum(np.packbits(t.astype(np.uint8), axis=1).tobytes() in reader.map_ for t in inks)
        if not reader.map_ or fixed or (n >= 3 and len(set(text)) > 1 and score >= CLEAR_SHAPE):
            kept.append(line)
        else:
            doubtful.append(line)
    grew = True
    while grew:  # a doubtful line just below a kept one of the same plane, overlapping it, joins the box
        grew = False
        for d in list(doubtful):
            if any(k[0] == d[0] and k[5] == d[5] and 0 < d[1] - k[1] <= 3 * d[5]
                   and d[2] < k[2] + k[3] * k[5] and k[2] < d[2] + d[3] * d[5] for k in kept):
                kept.append(d)
                doubtful.remove(d)
                grew = True
    out_ = []
    for plane, y, x, n, text, step in sorted(kept):
        b = out_[-1] if out_ else None
        if b and b["plane"] == plane and b["step"] == step and abs(b["x"] - x) <= 2 \
                and 0 < y - b["lines"][-1][0] <= 3:
            b["lines"].append((y, x, n, text))
        else:
            out_.append({"plane": plane, "x": x, "step": step, "lines": [(y, x, n, text)]})
    items = []
    for b in out_:
        if len(b["lines"]) > 1 and b["lines"][1][3].startswith("「") and "「" not in b["lines"][0][3]:
            items.append(dict(b, lines=b["lines"][:1], name=True))
            b = dict(b, lines=b["lines"][1:])
        if len(b["lines"]) > 1 and not any(re.search(r"[。、！？…!?.,「」『』]", t) for *_, t in b["lines"]):
            items += [dict(b, x=l[1], lines=[l]) for l in b["lines"]]
        else:
            items.append(b)
    for b in items:
        b["text"] = "".join(t for *_, t in b["lines"])
    return items


def patches(md, list_, overlay, font_):
    """(y0, y1, x0, x1, pixels) over each box: its colours, the translation in 8x8 Latin letters, two rows of
    letters per row of 16x16 characters (the translation is longer than the Japanese), one per row of 8x8 ones."""
    import textwrap
    from retro_translator.core.rewriting import rom_text
    from retro_translator.core.overlay import squeeze
    frame_, out_ = md.frame, []
    for b in list_:
        t = romaji(b["text"]) if b.get("name") else overlay(b["text"])
        if not t:
            continue
        p = b.get("step", 2)  # tiles per character: 2 (16x16) or 1 (8x8)
        y_start, y_end = b["lines"][0][0], b["lines"][-1][0] + p
        dx, dy = md.scroll(b["plane"], y_start * 8)
        y0, x0 = (y_start * 8 - dy) % 1024, (min(x for _, x, _, _ in b["lines"]) * 8 + dx) % 512
        width = max(x + p * n for _, x, n, _ in b["lines"]) * 8 - min(x for _, x, _, _ in b["lines"]) * 8
        alt = (y_end - y_start) * 8
        y1, x1 = min(frame_.shape[0], y0 + alt), min(frame_.shape[1], x0 + width)
        if y1 <= y0 or x1 <= x0:
            continue
        area = frame_[y0:y1, x0:x1].copy()
        colors, n = np.unique(area.reshape(-1, 3), axis=0, return_counts=True)
        order = np.argsort(-n)
        background, ink = colors[order[0]], colors[order[1]] if len(order) > 1 else 255 - colors[order[0]]
        max_lines = (y1 - y0) // 8
        if not re.search(r"[。！？…!?.]", b["text"]):  # a menu item has no article: "Diary 1", not "The Diary 1"
            t = re.sub(r"(?i)^(the|an?|l[ae]s?|l'|el|los|las|os?|as|uma?|une?)\s+(?=\S)", "", t)
            t = t[:1].upper() + t[1:]
        options = []  # no orphan row, then the least shortened text, then the widest letters; words never split
        for advance in (8, 7, 6):
            fits = (x1 - x0) // advance
            for k, v in enumerate(rom_text.shorten(t, ".")):
                lines = textwrap.wrap(v, fits, break_long_words=False)
                if len(lines) <= max_lines and all(len(l) <= fits for l in lines):
                    orphan = len(lines) > 1 and len(lines[-1]) <= 2  # "Diary" over a lone "1"
                    options.append((orphan, k, -advance, lines))
        if options:
            _, _, advance, lines = min(options, key=lambda o: o[:3])
            advance = -advance
        else:
            lines = textwrap.wrap(t, fits)[:max_lines]
        area[:] = background
        y = (max_lines - len(lines)) // 2 * 8  # centred in the box height
        for line in lines:
            for j, ch in enumerate(line):
                m = font_[ch]
                if advance < 8:
                    m = squeeze(m, advance)
                px = j * advance
                if y + 8 <= area.shape[0] and px + m.shape[1] <= area.shape[1]:
                    area[y:y + 8, px:px + m.shape[1]][m] = ink
            y += 8
        out_.append((y0, y1, x0, x1, area))
    return out_
