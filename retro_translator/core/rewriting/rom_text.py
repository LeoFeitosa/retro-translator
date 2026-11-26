"""Finds in the ROM the text shown on screen (relative search, no AI): the tile sequence of a line
becomes bytes or 16-bit words with a constant offset. With the place found, the text is replaced
inside the ROM itself and the game draws the translation on its own.
Usage: python -m retro_translator.core.rewriting.rom_text ROM"""
import os
import random
import re
import sys

import numpy as np

from retro_translator import HERE, consoles


def search(rom, tiles):
    """tiles: tile indices of the line (None = empty cell, matches anything).
    Returns [(position, width in bytes, base)] with tiles[i] = rom[p + i*width] + base."""
    found = []
    known = [(i, t) for i, t in enumerate(tiles) if t is not None]
    if len(known) < 4 or len({t for _, t in known}) < 3:
        return found  # too short or repetitive: matches anywhere
    for width_, start in ((1, 0), (2, 0), (2, 1)):
        b = rom[start:len(rom) - (len(rom) - start) % width_]
        v = np.frombuffer(b, ">u2" if width_ == 2 else np.uint8).astype(np.int64)
        mod = 256 ** width_
        i0, t0 = known[0]
        cand = np.arange(max(len(v) - len(tiles), 0))
        for i, t in known[1:]:
            cand = cand[(v[cand + i] - v[cand + i0]) % mod == (t - t0) % mod]
        found += [(start + int(c) * width_, width_, int(t0 - v[c + i0])) for c in cand]
    return found


def _alphabet(code):
    """Letters the game did not show during collection ("Q"), when the seen ones are in alphabetical order: same distance."""
    from collections import Counter
    new_ones = {}
    for a, z in (("A", "Z"), ("a", "z")):
        dist = Counter(c - ord(l) for c, l in code.items() if a <= l <= z)
        if not dist:
            continue
        d, n = dist.most_common(1)[0]
        if n >= 8 and n >= 0.8 * sum(dist.values()):
            used_ = set(code)
            new_ones.update({ord(l) + d: l for l in map(chr, range(ord(a), ord(z) + 1))
                          if l not in code.values() and ord(l) + d not in used_ and ord(l) + d >= 0})
    return new_ones


WEIGHT = {}


def codes(table, indices, width_, base, space):
    """ROM code -> letter, from the font table (glyph -> letter) and the tile of each glyph.
    tile = code + base; tiles out of the code's reach are other graphics (garbage, scenery) and are left out."""
    from collections import Counter, defaultdict
    mod = 256 ** width_
    votes = defaultdict(Counter)  # the same tile holds different glyphs during the game: the most seen one wins
    for g, letter in table.items():
        for t, n in indices.get(g, {}).items():
            if letter and 0 <= t - base < mod:
                votes[t - base][letter] += n
    code = {c: v.most_common(1)[0][0] for c, v in votes.items()}
    WEIGHT.clear()
    WEIGHT.update({c: v.most_common(1)[0][1] for c, v in votes.items()})  # how often each code was seen as its letter
    if space is not None:
        code[space] = " "
    return code


def extract(rom, code, width_, minimum=4, filter_=None):
    """ROM runs readable with this code: [(position, text)]. Without a filter, main uses looks_english."""
    v = np.frombuffer(rom[:len(rom) - len(rom) % width_], ">u2" if width_ == 2 else np.uint8)
    sentences, start_, buf = [], None, []
    for i, c in enumerate(v.tolist() + [None]):
        letter = code.get(c)
        if letter is not None:
            start_ = i if start_ is None else start_
            buf.append(letter)
            continue
        if start_ is not None:
            buf = _real_end(rom, start_ * width_, width_, "".join(buf))
        text = buf.strip() if start_ is not None else ""
        if start_ is not None and len(text) >= minimum and (filter_ is None or filter_(text)):
            sentences.append((start_ * width_, buf))
        start_, buf = None, []
    return sentences


def _real_end(rom, p, width_, text):
    """Where the text really ends: code and data right after it may fall in the letter range ("OPTIONS   09").
    A length stored before the string (byte or word) rules; otherwise a letterless tail after 2+ spaces is cut."""
    import re
    for n in (width_, 2 * width_):
        size_ = int.from_bytes(rom[p - n:p], "big") if p >= n else 0
        if len(text) / 2 <= size_ < len(text):
            return text[:size_]
    m = re.search(r" {2,}[^A-Za-z]*$", text)
    return text[:m.start()] if m and text[:m.start()].strip() else text


def find_codes(rom, found, value, table, n=3):
    """Candidates [(width, base, space, seen positions, code -> learned sign)] for the ROM text, from the collected
    sentences (no replay). value: glyph -> number the ROM stores up to a base (the tile, or the letter in alphabetical order)."""
    from collections import Counter
    sentences = sorted({t for t in found if None in t and sum(value.get(c) is not None for c in t) >= 8},
                       key=lambda t: (len(t), repr(t)))[-80:]  # ties by content: a set's order changes on every run
    votes, spaces, seen, marks_ = Counter(), {}, {}, {}
    for t in sentences:
        ent = [value.get(c) if c is not None else None for c in t]
        for p, width, base in search(rom, ent):
            votes[width, base] += 1
            seen.setdefault((width, base), []).append(p)
            spaces.setdefault((width, base), Counter()).update(
                int.from_bytes(rom[p + i * width:p + (i + 1) * width], "big") for i, c in enumerate(t) if c is None)
            for i, c in enumerate(t):  # punctuation and digits: the ROM byte where the screen shows the sign
                letter = table.get(c) if c is not None else None
                if letter and not letter.isalpha():
                    marks_.setdefault((width, base), {}).setdefault(
                        int.from_bytes(rom[p + i * width:p + (i + 1) * width], "big"), Counter())[letter] += 1
    return [(l, b, spaces[l, b].most_common(1)[0][0] if spaces[l, b] else None, seen[l, b],
             {c: v.most_common(1)[0][0] for c, v in marks_.get((l, b), {}).items()})
            for (l, b), _ in votes.most_common(n)]


def banks(groups, seen, slack=1024):
    """Only messages in confirmed text banks: a cluster (gaps <= slack) with some sentence seen on screen.
    Machine code sometimes decodes as English, and changing it crashes the game (3 Ninjas)."""
    out_, bank = [], []
    for g in groups + [None]:
        if g is not None and (not bank or g[0][0] - bank[-1][-1][0] <= slack):
            bank.append(g)
            continue
        if bank:
            start_, end = bank[0][0][0], bank[-1][-1][0] + len(bank[-1][-1][1]) * 2
            if any(start_ - slack <= p <= end for p in seen):
                out_ += bank
        bank = [g]
    return out_


def messages(rom, sentences, width_):
    """Joins the lines of one box: between them only short control codes (line break, position of the
    next line...). A gap with 00 or FF is end of text and splits."""
    end = lambda f: f[0] + len(f[1]) * width_
    groups = []
    for f in sentences:
        if groups:
            gap = rom[end(groups[-1][-1]):f[0]]
            if 0 < len(gap) <= 4 * width_ and not any(b in gap for b in (0, 255)):
                groups[-1].append(f)
                continue
        groups.append([f])
    return groups


def _fit(text, letters):
    """Text with only what the font has: strips accents, swaps case if missing, other signs become a space.
    None if a letter or digit is missing: a gap or a wrong glyph in the middle of a word is worse than the original."""
    import unicodedata
    out_ = []
    for c in unicodedata.normalize("NFD", text):
        if unicodedata.combining(c):
            continue
        swap = c if c in letters else c.upper() if c.upper() in letters else c.lower() if c.lower() in letters else None
        if swap is None and c.isalnum():
            return None
        out_.append(swap or " ")
    return "".join(out_)


def paragraph(group, box=0):
    """Lines of the same running text (otherwise it is a list or menu, and each line is an item that cannot take text
    from its neighbour). It continues on the next line when the line ends with a comma or a linking word or the next
    one starts in lowercase; or when the line stopped because the next word did not fit and there is sentence punctuation."""
    lines = [" ".join(t.split()) for _, t in group]
    if len(lines) < 2:
        return False
    pairs_ = [(a, b) for a, b in zip(lines, lines[1:]) if a and b]
    if any(a[-1] in ",;" or a.split()[-1].lower() in LINK or b[:1].islower() for a, b in pairs_):
        return True
    width = max(max(map(len, lines)), box)
    return all(len(a) + 1 + len(b.split()[0]) > width for a, b in pairs_) and any(c in " ".join(lines) for c in ".!?")


LINK = set("the a an to of in on at for with and or but your my his her their our its this that is are was be "
              "you i we he she they it from by as since than like into about while when if so not will would can "
              "have has had were".split())
CONTINUES = {"to", "of", "and", "or", "but", "than", "nor", "into"}  # a piece that starts with one goes on from another


ARTICLES = {"o", "a", "os", "as", "um", "uma", "uns", "umas", "el", "la", "los", "las", "un", "una",
            "le", "les", "une", "des", "the", "an"}  # pt, es, fr, en


def shorten(text, point="."):
    """Shorter and shorter versions, to fit the original's space (as hand-made ROM translations do): the whole
    sentence; without articles; then the longest word abbreviated with a period ("Velocidade" -> "Veloc."), one at a time."""
    yield text
    ps = text.split()
    ps = [p for i, p in enumerate(ps) if i == 0 or p.lower() not in ARTICLES]
    yield " ".join(ps)
    if not point:
        return  # a word cut with no period to show it reads as a misspelling
    abbreviated = set()
    while True:
        long_ones = [i for i, p in enumerate(ps) if sum(c.isalpha() for c in p) > 5 and p not in abbreviated]
        if not long_ones:
            return
        i = max(long_ones, key=lambda i: len(ps[i]))
        rest = "".join(c for c in ps[i] if not c.isalpha())  # trailing punctuation ("jogo:" -> "jog.:")
        letters = "".join(c for c in ps[i] if c.isalpha())
        k = 4
        while k < len(letters) - 2 and letters[k].lower() not in "aeiou":
            k += 1  # cut after the consonant: Veloc., Exib., Jogad.
        ps[i] = letters[:k] + point + rest.lstrip(".")
        abbreviated.add(ps[i])
        yield " ".join(ps)


def build(group, original, width_, inv, translation, limit, total=None):
    """Translation bytes on the same lines as the message (at most as many lines, each up to `limit` letters).
    With `total`, takes exactly that many letters (padded with spaces); None if it does not fit."""
    import textwrap
    n = len(group)
    # spaces at the start and end of the message are screen positions ("is \0 pounds \0 ounces"): kept
    start_ = len(group[0][1]) - len(group[0][1].lstrip(" "))
    end_ = len(group[-1][1]) - len(group[-1][1].rstrip(" ")) if group[-1][1].strip() else 0
    fitted = _fit(translation, inv)
    if fitted is None:
        REASONS["letter the font does not have"] += 1
        return None
    for text in shorten(fitted, "." if "." in inv else ""):
        lines = textwrap.wrap(text, limit, initial_indent=" " * start_)
        if lines and len(lines) <= n and (total is None or sum(map(len, lines)) <= total):
            break
    else:
        return None
    if len(lines) == n:
        lines[-1] += " " * end_
    if total is not None and sum(map(len, lines)) > total:
        return None
    if total is not None:
        lines += [""] * (n - len(lines))
        missing = total - sum(map(len, lines))
        for i in reversed(range(n)):  # pads the end of the lines with spaces, without exceeding the box width
            extra = min(missing, limit - len(lines[i]))
            lines[i] += " " * extra
            missing -= extra
    lines += [""] * (n - len(lines))
    end = lambda f: f[0] + len(f[1]) * width_
    if any(c not in inv for l in lines for c in l):
        REASONS["letter the font does not have"] += 1  # usually the space, when this message's font has none known
        return None
    gaps = [bytes(original[end(a):b[0]]) for a, b in zip(group, group[1:])] + [b""]  # the same codes, in order
    return b"".join(b"".join(inv[c].to_bytes(width_, "big") for c in l) + g for l, g in zip(lines, gaps))


def write_(rom, group, original, width_, inv, translation, limit):
    """Puts the translation in place of the message, with the same lines and breaks. False if it does not fit."""
    code = build(group, original, width_, inv, translation, limit, sum(len(t) for _, t in group))
    if code is None:
        return False
    rom[group[0][0]:group[0][0] + len(code)] = code
    return True


def free(original, console):
    """(start, end) of the FF/00 padding at the end of the ROM; the last 4 bytes are kept to balance the checksum."""
    end = console.data_end(original)
    p = end
    while p - 2 > console.TEXT_START and original[p - 2:p] == b"\xff\xff":
        p -= 2
    if end - p < 1024:  # little FF at the end may be real data: store nothing there
        return end, end
    return p + 16, end - 4  # margin after the last data (it may be a real FF)


def pointers(rom, target_):
    """Places (even) where the ROM stores the address `alvo` in 32 bits."""
    import re
    return [m.start() for m in re.finditer(re.escape(target_.to_bytes(4, "big")), bytes(rom)) if m.start() % 2 == 0]


from collections import Counter as _Counter
REASONS = _Counter()  # why a message neither fit nor moved (measurement)


def relocate(rom, original, group, code, width_, code_end, free_space):
    """A message that did not fit: writes it to free space and repoints its pointers. Only when the message ends with
    the form's end code (without it the game would keep reading the next one) and some even pointer points at it
    (or at the control codes right before it)."""
    start_, end = group[0][0], group[-1][0] + len(group[-1][1]) * width_
    if code_end is None or original[end:end + len(code_end)] != code_end:
        REASONS["no end code"] += 1
        return False
    for k in range(0, 4 * width_ + 1, width_):
        if k and original[start_ - k:start_ - k + width_] in free_space["text"]:
            break  # what comes before the message is already other text
        places = pointers(original, start_ - k)
        if places:
            new = bytes(original[start_ - k:start_]) + code + code_end
            p = free_space["next"]
            p += p % 2
            if p + len(new) > free_space["end"]:
                REASONS["no free space"] += 1
                return False
            rom[p:p + len(new)] = new
            free_space["next"] = p + len(new)
            for l in places:
                rom[l:l + 4] = p.to_bytes(4, "big")
            return True
    REASONS["no pointer"] += 1
    return False


def inv_of_message(group, data, width_, inv):
    """Letter -> code for writing this message. The codes the message itself already uses win (a tile index may
    hold another font's glyph on another screen, which can outvote it: Alien Storm wrote "ARCADE" as garbage).
    Other letters must sit where this message's alphabet order puts them; otherwise they are left out."""
    from collections import Counter
    local = {}
    for p, t in group:
        for i, ch in enumerate(t):
            if ch.strip() or 0 < i < len(t.rstrip()):  # a space between words is this message's own space code
                local.setdefault(ch, int.from_bytes(data[p + i * width_:p + (i + 1) * width_], "big"))
    new = {l: c for l, c in inv.items() if l.isalnum() or l == " "}  # punctuation is never proven by words:
    new.update(local)  # only the signs this message already shows are sure to look right (Starflight: "." was "©")
    for upper_ in (True, False):
        dist = Counter(c - ord(l) for l, c in local.items() if l.isalpha() and l.isupper() == upper_)
        if not dist:
            continue
        d, n = dist.most_common(1)[0]
        if n < 2 or n < 0.8 * sum(dist.values()):
            continue  # letters of this message are not in alphabetical order: nothing to check against
        for l in [l for l in new if l.isalpha() and l.isupper() == upper_ and l not in local]:
            if new[l] != ord(l) + d:
                del new[l]  # a code from another font: better to leave the message as it is
                if " " not in local:
                    new.pop(" ", None)  # the form's space belongs to that other font too (Alien Storm: "SOMHH")
    return new


def accents(translations):
    """Unaccented word -> accented word, taken from this game's translations (the ROM font has no accents; the program
    redraws only those letters on screen). Ambiguous forms are left out: a form that also appears unaccented
    ("ESTA"/"ESTÁ") or with two different accents."""
    import re
    import unicodedata
    from collections import Counter, defaultdict
    remove_ = lambda w: "".join(c for c in unicodedata.normalize("NFD", w) if not unicodedata.combining(c))
    with_, without = defaultdict(set), Counter()
    for t in translations:
        for w in re.findall(r"[^\W\d_]+", t):
            k = remove_(w).upper()
            if k == w.upper():
                without[k] += 1
            else:
                with_[k].add(w.upper())
    return {k: next(iter(v)) for k, v in with_.items() if len(v) == 1 and not without[k]}


def sentence_blocks(g):
    """Running text split into blocks of whole sentences: from a line that starts a sentence to a line that ends
    one. A game may keep a whole conversation as one message (Phantasy Star II); each block is translated and written
    in its own lines, and what is left at the end without its sentence end stays as it is."""
    ends = lambda t: re.search(r"[.!?][\"')]?\s*$", t)
    blocks, current = [], []
    for f in g:
        current.append(f)
        if ends(f[1]):
            blocks.append(current)
            current = []
    if not blocks:
        return [g]  # no sentence ends at a line end: the old way (whole_sentences decides)
    return blocks


def whole_sentences(g, lines, width):
    """In running text (it or a line right next to it in the ROM has sentence punctuation) the message must start
    and end a sentence: games that keep each line of a box apart ("I am haunted by" / "nightmares every night.")
    would get half of it translated. Menus (no punctuation around) pass."""
    start, end = g[0][0], g[-1][0] + len(g[-1][1]) * width
    prev = [t for p, t in lines if start - 3 * width <= p + len(t) * width <= start and p < start]
    next_ = [t for p, t in lines if end <= p <= end + 3 * width]
    texts = [" ".join(t for _, t in g)] + prev + next_
    if not any(re.search(r"[.!?]", t) for t in texts):
        return True
    ends = lambda t: re.search(r"[.!?:\"')]\s*$", t)
    return all(ends(t) for t in prev) and (not next_ or ends(texts[0]))


def _trim_junk(f, width):
    """With both cases read, bytes before a message (pointers, codes) read as letters stick to its first word:
    "chkmAfter going home", "kI am". The first word starts at its last capital when the case changes inside it."""
    p, t = f
    lead = len(t) - len(t.lstrip())
    word = t[lead:].split(" ")[0]
    if not re.search(r"[a-z][A-Z]|[A-Z]{2}[a-z]", word):
        return f
    k = max((i for i, ch in enumerate(word) if ch.isupper() and (i + 1 == len(word) or word[i + 1].islower())),
            default=None)
    return f if k is None else (p + (lead + k) * width, t[lead + k:])


def _text_stretches(data, marked, width, start):
    """The ROM stretches that already read as text with the letters known for sure (marked in capitals): the rest of
    a ROM is code and graphics, which read as letters by chance."""
    from wordfreq import zipf_frequency
    out_ = []
    for p, t in extract(data, marked, width, 2):
        known = re.findall(r"(?<![A-Za-z])[A-Z]{3,}(?![A-Za-z])", t)
        if p >= start and len(known) >= 2 and sum(zipf_frequency(w.lower(), "en") >= 3 for w in known) >= 0.7 * len(known):
            out_.append(t)
    return out_


def proven_by_words(data, code, guessed, width, start):
    """The guessed letters (by the order of the alphabet) that the ROM's text proves: each one must appear in at
    least 3 words of real text, 3 in 4 of them real English words. {code: letter} of the ones proven."""
    from wordfreq import zipf_frequency
    if not guessed:
        return {}
    marked = {**code, **{c: l.upper() for c, l in code.items() if l.isalpha()}, **{c: l.lower() for c, l in guessed.items()}}
    words = [w for t in _text_stretches(data, marked, width, start) for w in re.findall(r"[A-Za-z]{3,}", t)]
    ok = {}
    for c, l in guessed.items():
        using = [w for w in words if l.lower() in w]
        if len(using) >= 3 and sum(zipf_frequency(w.lower(), "en") >= 3 for w in using) >= 0.75 * len(using):
            ok[c] = l
    return ok


def second_case(data, code, width, start):
    """The other case of the alphabet, which the screen reading folds into one: often the 26 codes right before or
    after it (Phantasy Star II: capitals at 0x0B, lowercase at 0x25), or 32 away as in ASCII. Accepted only when the ROM's words that use it
    are real words; the block used more often is the lowercase one. {code: letter in its case}, or {} if unproven."""
    from wordfreq import zipf_frequency
    letters_ = {c: l for c, l in code.items() if l.isalpha()}
    if len(letters_) < 20:
        return {}
    for k in (-26, 26, -32, 32):  # right next to it, or as in ASCII
        other = {c + k: l for c, l in letters_.items() if c + k >= 0 and c + k not in code}
        if len(other) < 20:
            continue
        marked = {**code, **{c: l.upper() for c, l in letters_.items()}, **{c: l.lower() for c, l in other.items()}}
        texts = _text_stretches(data, marked, width, start)
        used = [w for t in texts for w in re.findall(r"(?<![A-Za-z])[a-z][A-Z]{2,}(?![A-Za-z])", t)]  # "wHAT"
        if len(used) < 30 or sum(zipf_frequency(w.lower(), "en") >= 3 for w in used) < 0.75 * len(used):
            continue
        n_other = sum(ch.islower() for t in texts for ch in t)
        n_base = sum(ch.isupper() for t in texts for ch in t)
        lower, upper = (other, letters_) if n_other > n_base else (letters_, other)
        return {**{c: l.lower() for c, l in lower.items()}, **{c: l.upper() for c, l in upper.items()}}
    return {}


def real_words(text):
    """Every word of the (English) text exists: a message read with a missing or wrong letter is not translated. A
    short word must be common ("OU", "OST", "TART" are pieces of "YOU", "MOST", "START"); a contraction is judged by its stem."""
    from wordfreq import zipf_frequency
    cased = any(c.islower() for c in text)  # in mixed case a capitalized word is a name ("Nei", "Paseo")
    for w in re.findall(r"[^\W\d_]+(?:'[^\W\d_]+)?", text):
        if cased and re.fullmatch(r"[A-Z][a-z]+", w):
            continue
        stem, _, tail = w.lower().partition("'")
        if tail and tail not in ("s", "t", "ll", "re", "ve", "d", "m"):
            return False
        if stem in ("a", "i") or (stem == "can" and tail == "t") or stem.endswith("n") and tail == "t":
            continue
        if len(stem) < 2 or zipf_frequency(stem, "en") < (5.3 if len(stem) == 2 else 4.5 if len(stem) == 3 else 3.5 if len(stem) == 4 else 2.5):
            return False
    return True


def ascii_text(data, start):
    """The game's own English kept in plain ASCII, found without reading the screen (a font drawn in variable
    width cannot be read tile by tile): its language when there is enough of it (40 stretches of real words),
    else None. Whether it is what the player sees is proven later by visible()."""
    from wordfreq import zipf_frequency
    best = None
    runs = [r.decode() for r in re.findall(rb"[ -~]{8,}", data[start:]) if b"%" not in r]  # "%d": debug text
    for language in ("en", "fr", "es"):
        good = 0
        for t in runs:
            ws = re.findall(r"[^\W\d_]{3,}", t)
            good += len(ws) >= 2 and sum(zipf_frequency(w.lower(), language) >= 3 for w in ws) >= 0.8 * len(ws)
        if good >= 40 and (best is None or good > 1.3 * best[1]):
            best = (language, good)
    return best and best[0]


def ascii_shape(data, start):
    """The plain ASCII text as one more form for translate(): every printable code, written back only with the
    characters the game already uses (a letter it never shows may not be in its font)."""
    code = {c: chr(c) for c in range(0x20, 0x7F)}
    sentences = [f for f in extract(data, code, 1, 2) if f[0] >= start and "%" not in f[1]]
    from retro_translator.core import overlay
    groups = [g for g in messages(data, sentences, 1) if overlay.looks_english(" ".join(t for _, t in g))]
    if not groups:
        return None
    used = {data[q] for g in groups for p, t in g for q in range(p, p + len(t))}
    inv = {chr(c): c for c in sorted(used)}
    from collections import Counter
    ends = Counter(data[g[-1][0] + len(g[-1][1]):][:1] for g in groups)
    return groups, 1, inv, ends.most_common(1)[0][0], sorted(sentences)


def translate(route, language="pt", out_=None, table=None, ascii_only=False):
    """Translated ROM (.bin). Returns (path, messages replaced, messages found) or None when no code is found."""
    from retro_translator.core.reading import evaluate
    from retro_translator.core.reading import decipher
    from retro_translator.core.translating import translation
    from retro_translator.core import overlay
    from collections import Counter
    found, indices = evaluate.collection(route)
    name_ = os.path.splitext(os.path.basename(route))[0]
    if table is None:
        table = decipher.read_font(found, indices, exclude=name_)
    console = consoles.for_rom(route)
    data = console.read_rom(route)
    tile = {g: c.most_common(1)[0][0] for g, c in indices.items()}
    letter = {g: ord(l) for g, l in table.items() if l and l.isalpha()}
    shapes = []  # a game may store text in several forms (menus in ASCII, dialog in tiles...): use them all
    for mode_, value in (("tile", tile), ("letter", letter)) if not ascii_only else ():
        for width, base, space, seen, marks_ in find_codes(data, found, value, table):
            if mode_ == "tile":
                code = codes(table, indices, width, base, space)
                deduced = _alphabet(code)  # good for reading; for writing the glyph may not even be loaded
                code.update(deduced)
            else:  # alphabetical order (ASCII or similar); punctuation comes from what was seen on screen
                deduced = {}
                code = {c: chr(c + base) for c in range(256 ** width) if 0 < c + base < 0x7F and chr(c + base).isalpha()}
                if base == 0 and space == 32:  # letters and space at ASCII codes: it is ASCII (this beats the screen
                    code.update({c: chr(c) for c in range(0x21, 0x7F)})  # reading, which mixes up "," and "!")
                else:
                    code.update(marks_)
                if space is not None:
                    code[space] = " "
                proven = {l for l in table.values() if l and l.isalpha()}
                guessed = {c: l for c, l in code.items() if l.isalpha() and l not in proven}
                code = {c: l for c, l in code.items() if not l.isalpha() or l in proven}
                # a letter only deduced from the alphabet order may sit elsewhere in this font (Phantasy Star II:
                # "w" written as "u"): it is kept only when the ROM's words prove it
                code.update(proven_by_words(data, code, guessed, width, console.TEXT_START))
                code.update(second_case(data, code, width, console.TEXT_START))
            sentences = [f for f in extract(data, code, width, 2) if f[0] >= console.TEXT_START]
            if any(l.islower() for l in code.values()):
                sentences = [f for f in map(_trim_junk, sentences, [width] * len(sentences)) if f[1]]
            groups = messages(data, sentences, width)
            groups = [g for g in groups if overlay.looks_english(" ".join(t for _, t in g))]  # "BALROG" alone is misleading
            groups = banks(groups, seen)
            # next to a glyph the table cannot read, the text is cut mid-word ("What" read as "HAT", "Select a number"
            # as "T A NUM ER"): translated, the pieces mix with what is left around them. Any line touching one drops
            # the whole message
            if mode_ == "tile":
                unread = {t - base for g, ts in indices.items() if g not in table and g.strip("0/") for t in ts}
            else:
                letters_ = [c for c in range(256 ** width) if 0x41 <= c + base <= 0x5A]  # the other case is often
                # the 26 codes right before or after (Phantasy Star II: capitals at 0x0B, lowercase at 0x25); once
                # second_case proved where it is, the codes on the other side are something else (punctuation)
                cased = any(l.islower() for l in code.values())
                unread = {c + k for c in letters_ for k in ((0,) if cased else (-26, 0, 26))} - set(code) - {space}

            def touches(f):
                for p, step in ((f[0] - width, -width), (f[0] + len(f[1]) * width, width)):
                    while 0 <= p < len(data) and int.from_bytes(data[p:p + width], "big") == space:
                        p += step
                    if 0 <= p < len(data) and int.from_bytes(data[p:p + width], "big") in unread:
                        return True
                return False
            groups = [g for g in groups if not any(touches(f) for f in g)]
            if deduced:  # a letter only deduced from the alphabet order is good for finding text, not for reading
                # it (Sword of Vermilion: "C" read as "O", "SEORET PASSAGE")
                groups = [g for g in groups if not any(int.from_bytes(data[p:p + width], "big") in deduced
                                                       for f in g for p in range(f[0], f[0] + len(f[1]) * width, width))]
            if groups:
                inv = {}  # for writing: the code most often seen as each letter (a garbage glyph read as "A" loses)
                for c, l in sorted(code.items(), key=lambda x: -WEIGHT.get(x[0], 0) if mode_ == "tile" else 0):
                    if c not in deduced:  # write only glyphs seen on screen as that letter
                        inv.setdefault(l, c)
                # end code: the most common one right after the messages (needed to move text elsewhere)
                ends = Counter(data[g[-1][0] + len(g[-1][1]) * width:][:width] for g in groups)
                code_end = ends.most_common(1)[0][0] if ends else None
                shapes.append((groups, width, inv, code_end, sorted(sentences)))
                if os.environ.get("RT_DEBUG"):
                    print("SHAPE", mode_, width, base, space, len(groups), sum(" " in t.strip() for g in groups for _, t in g), flush=True)
    if ascii_only:  # the screen font could not be read: only the game's plain ASCII text (visible() decides)
        shapes = [f for f in [ascii_shape(data, console.TEXT_START)] if f]
    # the form that reads the most messages first; another form only keeps what does not overlap bytes already taken
    units, taken = [], set()
    for groups, width, inv, code_end, lines in sorted(shapes, key=lambda f: -len(f[0])):
        # dialog box width of the form: the most common among the longest lines of multi-line messages
        larger = Counter(max(len(t) for _, t in g) for g in groups if len(g) > 1)
        box = larger.most_common(1)[0][0] if larger else 0
        end = lambda f: f[0] + len(f[1]) * width
        ok_ = [f[0] for g in groups for f in g
                 if re.search(r"(?i)registered|trademark|licen[sc]ed|copyright|©", f[1])]
        parts = []
        for g in groups:  # a line ending in ":" is a title or label: running text starts after it
            start_ = 0
            for i, (_, t) in enumerate(g):
                if t.rstrip().endswith(":"):
                    parts += [g[start_:i + 1]]
                    start_ = i + 1
            parts += [g[start_:]] if g[start_:] else []
        for g in parts:
            band = range(g[0][0] // 2, (g[-1][0] + len(g[-1][1]) * width) // 2 + 1)
            if taken.isdisjoint(band):
                taken.update(band)  # text of this form, replaced or not: another form does not read over it
                if any(abs(g[0][0] - p) <= 256 for p in ok_):
                    continue  # legal notices and trademarks stay as they are
                limit = max(len(t) for _, t in g)  # menu width, or the box width if the message gets close to it
                c = box if box - 4 <= limit <= box else 0
                # next to a value the game inserts mid-line ("is \0 pounds"): it starts or ends in the
                # middle of a screen line, and rewrapping would push the text out of it
                before, after = data[max(g[0][0] - 2 * width, 0):g[0][0]], data[end(g[-1]):end(g[-1]) + 2 * width]
                middle = (0 in before and any(32 <= b < 127 for b in data[g[0][0] - 3 * width:g[0][0] - width])) or \
                       (0 in after and any(32 <= b < 127 for b in data[end(g[-1]) + width:end(g[-1]) + 3 * width]))
                pieces = sentence_blocks(g) if not middle and paragraph(g, c) else [[f] for f in g]  # a wider box
                # may not be this message's box
                units += [(u, width, inv, code_end, limit) for u in pieces if whole_sentences(u, lines, width)]
    if not units:
        return None
    texts = [" ".join(" ".join(t.split()) for _, t in u) for u, *_ in units]
    trans = translation.translate_batch(texts, language)
    rom, done, moved = bytearray(data), 0, 0
    start_, end = free(data, console)
    free_space = {"next": start_, "end": end}
    for (u, width, inv, code_end, limit), t in zip(units, trans):
        if not t or (_fit(t, inv) or "").split() == " ".join(x for _, x in u).split():  # unchanged (proper name): leave it
            continue
        if not overlay.looks_english(" ".join(x for _, x in u)):
            continue  # a lone line of a group (list item) that is not text by itself: code inside the bank
        if re.fullmatch(r"\W*\w{1,3}\W*", " ".join(x for _, x in u)):
            continue  # a lone word of up to 3 letters is as often other data that spells it by chance (Alien Storm:
            # the bytes of "Sav" in "Save the people" in another font read "RAN", whose translation overwrote them)
        source = " ".join(x for _, x in u).strip()
        if any(c.islower() for c in source) and not any(c.islower() for c in inv):
            continue  # lowercase text and no lowercase letter proven: it would come out in the wrong case or letters
        if any(c.islower() for c in source) and not (re.match(r"[\W\d]*[A-Z0-9\"'(¡¿]", source)
                                                     and re.search(r"[.!?:\"')]$", source)):
            continue  # a piece of a longer sentence: alone, its translation mixes with the English around it
        if re.match(r" \S|'\w", u[0][1]) or re.search(r"\S $", u[-1][1]) or \
                re.search(r"[,;]$", source) or source.split()[-1].lower() in LINK or \
                source.split()[0].lower() in CONTINUES:
            continue  # cut at a glyph the table cannot read (one space at an edge: a letter missing next to it, padding
            # uses more; a contraction without its start, "'LL KEEP"), or it goes on in another message
        if re.search(r"[.!?]", source) and re.search(r"\S {2,}\S|(^|[.!?] ),|(^| )[.,!?;:]", source):
            continue  # a gap where the game inserts a name or a number ("It will cost   Meseta"): the translation
            # cannot keep it in the right place
        if not real_words(source):
            continue  # a word that does not exist: a letter is missing or wrong ("OU HAVE", "LADE SLIPPED")
        if any(c in x for _, x in u for c in "©®™") or "registered" in " ".join(x for _, x in u).lower():
            continue  # legal notices and trademarks stay as they are
        inv = inv_of_message(u, data, width, inv)
        if write_(rom, u, data, width, inv, t, limit):
            done += 1
            continue
        code = build(u, data, width, inv, t, limit)
        if code is None:
            REASONS["does not fit the box"] += 1
            if os.environ.get("RT_DEBUG"):
                print("NOFIT", len(u), limit, repr(" / ".join(x for _, x in u)), "->", repr(t), flush=True)
        free_space["text"] = {c.to_bytes(width, "big") for c in inv.values()}
        if code is not None and relocate(rom, data, u, code, width, code_end, free_space):
            done += 1
            moved += 1
    console.fix_checksum(rom, data)
    out_ = out_ or os.path.join("output", f"{name_}.{language}.bin")
    os.makedirs(os.path.dirname(out_) or ".", exist_ok=True)
    open(out_, "wb").write(rom)
    import json
    json.dump(accents([t for t in trans if t]), open(out_ + ".accents.json", "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(dict(zip(texts, trans)), open(out_ + ".texts.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    return out_, done, len(units), len(shapes), moved


AFTER_GAME = 120  # frames: ROM checks run on power-up


def screens(route, translated=None):
    """A fingerprint of the screen every 20 frames of ~8 min of play with buttons in a fixed order (the same for
    the original and the translation; with `translated`, written into memory after start-up)."""
    import zlib
    console = consoles.for_rom(route)
    m, rnd, v = console.Emulator(route), random.Random(3), []
    for i in range(1500):
        if translated and i == AFTER_GAME // 20:
            m.write_rom(open(translated, "rb").read(), bytes(console.read_rom(route)))
        b = rnd.choice(["A", "B", "START", "A", "B", "UP", "DOWN", "LEFT", "RIGHT", None, None])
        m.run_frames(4, [b] if b else [])
        m.run_frames(16)
        v.append(zlib.crc32(m.frame.tobytes()))
        _leave_view(m, i)
    return v


def visible(original, translated, memory=False):
    """The translation shows on screen: played the same way, some screen differs from the original's. Without it a
    game would be called translated while the player sees nothing change (text the game never shows)."""
    a = _brightness_in_process(original, mode="--screens")
    b = _brightness_in_process(*((original, translated) if memory else (translated,)), mode="--screens")
    return bool(a and b) and a != b


def brightness(route, translated=None):
    """Average screen brightness at 10 points of the first ~2 min pressing START (own process: the core opens
    one ROM per process). With `translated`, boots the original and writes the translation into memory after start-up."""
    console = consoles.for_rom(route)
    m, v = console.Emulator(route), []
    for i in range(400):
        if translated and i == AFTER_GAME // 20:
            m.write_rom(open(translated, "rb").read(), bytes(console.read_rom(route)))
        m.run_frames(4, ["START"] if i % 20 == 0 else [])
        m.run_frames(16)
        _leave_view(m, i)
        if i % 40 == 39:
            v.append(int(m.frame.mean()))
    return v


def _leave_view(m, i):
    """In the measuring process: the screen it is playing, left for the program's window every few steps."""
    path = os.environ.get("RT_VIEW")
    if path and i % 5 == 0:
        np.save(path + ".tmp.npy", m.frame)
        os.replace(path + ".tmp.npy", path)


def _brightness_in_process(*roms, mode="--brightness"):
    import subprocess
    import tempfile
    import time
    from retro_translator.core import progress
    if getattr(sys, "frozen", False):  # in the exe, the program itself measures
        cmd = [sys.executable, mode, *roms]
    else:
        cmd = [sys.executable, "-m", "retro_translator", mode, *roms]
    root = os.path.dirname(HERE)  # the folder that holds the package
    view = os.path.join(tempfile.gettempdir(), f"rt-view-{os.getpid()}.npy")
    out_ = tempfile.TemporaryFile("w+")  # a file, not a pipe: a full pipe would stop the child while this waits
    p = subprocess.Popen(cmd, stdout=out_, stderr=subprocess.DEVNULL, text=True,
                         env={**os.environ, "PYTHONPATH": root, "RT_VIEW": view})  # the package is found from any folder
    t0 = time.time()
    while p.poll() is None:  # the game being tested shows on the preparing screen, as it plays
        if time.time() - t0 > 600:
            p.kill()
            return None
        time.sleep(0.3)
        try:
            progress.show(np.load(view))
        except (OSError, ValueError):
            pass
    try:
        os.remove(view)
    except OSError:
        pass
    out_.seek(0)
    lines = out_.read().strip().splitlines()
    return eval(lines[-1]) if p.returncode == 0 and lines else None


def link_(original, translated):
    """Makes the translated ROM run like the original (dark screen where the original shows something = hung). Each game
    treats the sum its own way: some verify it, others use the header or the end of the ROM for something else; tries
    balancing at the end, not touching it and recomputing the header. If none runs, finds the culprit changes (bisection)
    and reverts only those. False if it cannot."""
    ref = _brightness_in_process(original)
    if ref is None:
        return False
    console = consoles.for_rom(original)
    orig = bytes(console.read_rom(original))
    end = console.data_end(orig)
    total_ = [console.HEADER_SUM, range(end - 4, end - 2)]

    def good(version):
        open(translated, "wb").write(version)
        v = _brightness_in_process(translated)
        return bool(v) and all(t > 5 or o <= 5 for o, t in zip(ref, v))

    def versions(trans):
        base = bytearray(trans)
        for r in total_:
            base[r.start:r.stop] = orig[r.start:r.stop]
        header = bytearray(base)
        console.set_header_sum(header)
        return (bytes(trans), bytes(base), bytes(header))

    trans = bytes(open(translated, "rb").read())
    if any(good(v) for v in versions(trans)):
        return True
    # the game verifies its ROM its own way: boot the original and write the translation into memory after start-up
    open(translated, "wb").write(trans)
    v = _brightness_in_process(original, translated)
    if v and all(t > 5 or o <= 5 for o, t in zip(ref, v)):
        return "memory"
    for _ in range(6):
        if any(good(v) for v in versions(trans)):
            return True
        diff = [i for i in np.flatnonzero(np.frombuffer(orig, np.uint8) != np.frombuffer(trans, np.uint8)).tolist()
               if not any(i in r for r in total_)]
        regions = []
        for i in diff:
            if regions and i - regions[-1][1] <= 8:
                regions[-1][1] = i
            else:
                regions.append([i, i])

        valid = console.header_sum_valid(orig)

        def with_(sub):  # only these text changes, with the right header sum for them (if the game uses it)
            d = bytearray(orig)
            for a, b in sub:
                d[a:b + 1] = trans[a:b + 1]
            if valid:
                console.set_header_sum(d)
            return bytes(d)

        print("regions", len(regions), "do all break?", not good(with_(regions)), flush=True) if os.environ.get("RT_DEBUG") else None
        current, n = regions, 2  # smallest set of changes that still hangs (ddmin)
        while len(current) >= 2:
            for piece in (current[i::n] for i in range(n)):
                rest = [r for r in current if r not in piece]
                if not good(with_(rest)):
                    current, n = rest, max(n - 1, 2)
                    break
            else:
                if n >= len(current):
                    break
                n = min(len(current), n * 2)
        if os.environ.get("RT_DEBUG"):
            print("culpadas", current, flush=True)
        d = bytearray(trans)
        for a, b in regions:  # the culprit and its neighbours (the same string table usually has the same use)
            if any(a - 256 <= y and b + 256 >= x for x, y in current):
                d[a:b + 1] = orig[a:b + 1]
        trans = bytes(d)
    return False


def lines_on_screen(md, table):
    """[(text, [tile indices])] of the visible text lines."""
    from retro_translator.core import overlay
    grids = md.planes()
    out_ = []
    for b in overlay.blocks(md, table):
        for y, text, tr in b["lines"]:
            line = grids[b["plane"]][y]
            ent = [int(line[(b["x"] + i) % len(line)]) & 0x7FF if c else None for i, c in enumerate(tr)]
            out_.append((text, ent))
    return out_
