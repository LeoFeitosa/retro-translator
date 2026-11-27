"""Finds the letter of each glyph without AI: treats the game text as a substitution cipher
and solves it with a word frequency dictionary (simulated annealing). CPU only, seconds.

decipher(found, language) -> {glyph: lowercase letter or punctuation}
Case (upper/lower) is decided later from the glyph height (table.fix_case).
"""
import math
import os

import numpy as np
import random
from collections import Counter, defaultdict

from wordfreq import top_n_list, zipf_frequency

from retro_translator.core.reading.table import mask
from retro_translator import DATA

LETTERS = "abcdefghijklmnopqrstuvwxyz"
PUNCTUATION = ".,!?'-:"
SYMBOLS = LETTERS + PUNCTUATION
UNKNOWN_WORD = -3.0
MAX_PER_LETTER = 2
PRIOR_WEIGHT = 5
PENALTY = 30  # same letter: one uppercase glyph and one lowercase glyph


def words(found):
    """Words (tuples of glyphs) of all distinct text runs, with counts."""
    count_ = Counter()
    for excerpt in found:
        if not any(c is None for c in excerpt):  # sentences only: graphic garbage rarely has spaces
            continue
        if all(a is None or b is None for a, b in zip(excerpt, excerpt[1:])):  # grid "A B C D"
            continue
        current = []
        for c in list(excerpt) + [None]:
            if c is None:
                if current:
                    count_[tuple(current)] += 1
                current = []
            else:
                current.append(c)
    return count_


class Dictionary:
    def __init__(self, language="en", n=30000):
        self.score = {w: zipf_frequency(w, language) for w in top_n_list(language, n) if w.isalpha() or "'" in w}
        self.memo = {}

    def __call__(self, text):
        """The search asks about the same strings millions of times: each one is worked out once."""
        if text not in self.memo:
            if len(self.memo) > 2000000:
                self.memo.clear()
            self.memo[text] = self._score(text)
        return self.memo[text]

    def _score(self, text):
        core = text.rstrip(".,!?:-")
        end = text[len(core):]
        if not core or (len(end) > 1 and end not in ("...", "!?", "?!")):
            return UNKNOWN_WORD
        if core.isdigit():  # numbers are common game text ("1 player"); the search does not use digits, only the font order
            return 3.0
        if any(c in ".,!?:-" for c in core) or (len(core) == 1 and core not in "ai"):
            return UNKNOWN_WORD
        return self.score.get(core, UNKNOWN_WORD)


def library(exclude=None, folder=None):
    """Letter of each glyph already seen in other games (majority vote), excluding the game itself."""
    import glob
    import json
    import os
    folder = folder or os.path.join(DATA, "tables")
    votes = defaultdict(Counter)
    for path_ in glob.glob(os.path.join(folder, "*.json")):
        if exclude and os.path.splitext(os.path.basename(path_))[0] == exclude:
            continue
        for g, l in json.load(open(path_, encoding="utf-8")).items():
            votes[g][l] += 1
    return {g: v.most_common(1)[0][0] for g, v in votes.items()}


def decipher(found, language="en", steps=300000, attempts=10, dictionary=None, prior=None):
    """The search lands on a bad optimum about half the time (Bass: score -250 against +200). Bad optima
    differ from each other; the good one repeats. Stops when two attempts give the same map (90% of
    the glyphs), at most `attempts`; without agreement, the highest score."""
    dic = dictionary or Dictionary(language)
    done = []
    for s in range(attempts):
        score, map_ = _reheat(found, dic, steps, s, prior or {})
        for score2, map2 in done:
            if map_ and sum(map_[g] == map2.get(g) for g in map_) >= 0.9 * len(map_):
                return map_ if score >= score2 else map2
        done.append((score, map_))
    return max(done, key=lambda r: r[0])[1]


def _reheat(found, dic, steps, seed, prior):
    ws = words(found)
    list_ = list(ws)
    weight = [math.log2(1 + ws[w]) for w in list_]
    glyphs = sorted({g for w in list_ for g in w})
    if not glyphs:  # game without a sentence with spaces: nothing to decipher
        return 0, {}
    where_ = defaultdict(list)
    for i, w in enumerate(list_):
        for g in set(w):
            where_[g].append(i)
    # start: glyph frequency matched to English letter frequency
    freq = Counter(g for w in list_ for g in w)
    order_en = "etaoinshrdlcumwfgypbvkjxqz"
    rnd = random.Random(seed)
    # shape: period, comma, apostrophe and hyphen are small glyphs; letters are large glyphs
    px = {g: int(mask(g).sum()) for g in glyphs}
    median = sorted(px.values())[len(px) // 2]
    can = {g: [s for s in SYMBOLS if _fits(s, px[g] / median)] or list(SYMBOLS) for g in glyphs}
    map_ = {}
    for i, (g, _) in enumerate(freq.most_common()):
        map_[g] = order_en[i % 26] if order_en[i % 26] in can[g] else can[g][0]
    predicted = {g: prior[g].lower() for g in glyphs if g in prior and prior[g].lower() in can[g]}
    map_.update(predicted)

    def bonus(m):  # a glyph equal to one from another game pulls toward the same letter, without forcing it
        return PRIOR_WEIGHT * sum(m[g] == l for g, l in predicted.items())

    def word_score(i):
        return weight[i] * dic("".join(map_[g] for g in list_[i]))

    usage = Counter(map_.values())  # kept up to date with each change: counting the whole map every step was slow

    def excess():
        return sum(max(0, n - MAX_PER_LETTER) for n in usage.values())

    scores = [word_score(i) for i in range(len(list_))]
    before = excess()
    total = sum(scores) - PENALTY * before + bonus(map_)
    best, best_map = total, dict(map_)
    for step in range(steps):
        temp = 2.0 * (1 - step / steps) + 0.05
        if rnd.random() < 0.5:
            g = rnd.choice(glyphs)
            old = {g: map_[g]}
            map_[g] = rnd.choice(can[g])
        else:
            g, h = rnd.sample(glyphs, 2) if len(glyphs) > 1 else (glyphs[0], glyphs[0])
            old = {g: map_[g], h: map_[h]}
            if map_[h] not in can[g] or map_[g] not in can[h]:
                continue
            map_[g], map_[h] = map_[h], map_[g]
        for k, v in old.items():
            usage[v] -= 1
            usage[map_[k]] += 1
        after = excess()
        affected = set(i for k in old for i in where_[k])
        new_ones = {i: word_score(i) for i in affected}
        new_total = (total + sum(new_ones[i] - scores[i] for i in affected) - PENALTY * after
                      + PENALTY * before
                      + PRIOR_WEIGHT * sum((map_[k] == predicted[k]) - (old[k] == predicted[k]) for k in old if k in predicted))
        if new_total >= total or rnd.random() < math.exp((new_total - total) / temp):
            total, before = new_total, after
            for i, v in new_ones.items():
                scores[i] = v
            if total > best:
                best, best_map = total, dict(map_)
        else:
            for k, v in old.items():
                usage[map_[k]] -= 1
                usage[v] += 1
            map_.update(old)
    return best, best_map


def _fits(symbol, ratio):
    """ratio = glyph pixels / median of the game's glyphs."""
    if symbol in ".,'-:":
        return ratio <= 0.4
    if symbol in "!?":
        return True
    return ratio >= 0.3


def box(map_, found=()):
    """Each font height (8 and 16) decides on its own: comparing the top of one with the other means nothing (Battlemaster)."""
    groups = defaultdict(dict)
    for g, l in map_.items():
        groups[mask(g).shape[0]][g] = l
    out_ = {}
    for sub in groups.values():
        out_.update(_case(sub, found))
    return out_


def _case(map_, found=()):
    """Upper or lower case and the exact punctuation mark, from the glyph.
    A letter without ascender (a, c, e...) taller than the lowercase height is uppercase. A letter with an ascender
    (l/L, t/T...) with two glyphs: the uppercase one is the one that starts more words."""
    top = {g: int(mask(g).any(1).argmax()) for g in map_}
    occurrences = Counter(g for w, n in words(found).items() for g in w for _ in range(n))
    lows = Counter()
    for g, l in map_.items():
        if l in "acemnorsuvwxz":
            lows[top[g]] += occurrences[g] or 1
    if not lows:
        return dict(map_)
    # lowercase height: the lowest top among the frequent ones (upper and lower case of the same letter
    # may have the same number of glyphs; occurrences in the text and position break the tie)
    x_alt = max((t for t, n in lows.items() if n >= 0.2 * sum(lows.values())), default=lows.most_common(1)[0][0])
    # there is lowercase if a relevant share of the letters rises above it (a rare glyph from another font does not count:
    # Battletoads was all uppercase, but garbage with top 0 made the whole game lowercase)
    tall_ones = Counter()
    for g, l in map_.items():
        if l in LETTERS:
            tall_ones[top[g] <= x_alt - 2] += occurrences[g] or 1  # 1 px of difference is part of the letter design (Buck Rogers)
    has_lower = tall_ones[True] >= 0.1 * sum(tall_ones.values())
    # words are also split at punctuation ("time.If" is two)
    parts = Counter()
    for w, n in words(found).items():
        current = []
        for g in list(w) + [None]:
            if g is None or map_.get(g, "a") not in LETTERS:
                if current:
                    parts[tuple(current)] += n
                current = []
            else:
                current.append(g)
    start, total = Counter(), Counter()
    for w, n in parts.items():
        start[w[0]] += n
        for g in w:
            total[g] += n
    base = Counter(_letter_background(g) for g, l in map_.items() if l in "acemnorsuvwxz").most_common(1)[0][0]
    out_ = {}
    per_letter = defaultdict(list)
    for g, l in map_.items():
        per_letter[l].append(g)
    for l, gs in per_letter.items():
        if l not in LETTERS:
            out_.update({g: _sign(g, l, base, x_alt) for g in gs})
            continue
        for g in gs:
            if not has_lower:
                out_[g] = l.upper()
            elif l in "gjpqy" and len(gs) > 1 and any(_letter_background(h) > base for h in gs):
                # two glyphs of the same letter and only one drops below the baseline: the other is uppercase (George: G read as g)
                out_[g] = l if _letter_background(g) > base else l.upper()
            elif l in "bdfhkltgjpqyi":
                continue  # decided below, from context
            else:
                out_[g] = l.upper() if top[g] < x_alt else l
    # letter with an ascender (height does not decide): inside an all-uppercase word it is uppercase; inside a word with
    # lowercase it is lowercase; without context, the glyph that starts more words (of two for the same letter) is uppercase
    caps, minus = Counter(), Counter()
    for w, n in parts.items():
        for i, g in enumerate(w):
            others = [out_[o] for o in w if o != g and o in out_ and out_[o].isalpha()]
            if not others or g in out_:
                continue
            if all(c.isupper() for c in others):
                caps[g] += n
            elif i > 0:
                minus[g] += n
    for l, gs in per_letter.items():
        for g in gs:
            if g in out_:
                continue
            if caps[g] != minus[g]:
                out_[g] = l.upper() if caps[g] > minus[g] else l
                continue
            others = [start[o] / total[o] for o in gs if o != g and total[o]]
            part = start[g] / total[g] if total[g] else 0
            out_[g] = l.upper() if others and part >= 0.5 and part > max(others) else l
    return out_


def by_order(map_, indices, neighbours=4, minimum=2):
    """The font is usually stored in ASCII order in video memory: position - code is constant within a block
    (PS2: one block of uppercase, another of lowercase). Each glyph gets the character its memory
    neighbours predict, when they agree; this fixes rare letters and brings digits and punctuation."""
    pos = {g: c.most_common(1)[0][0] for g, c in indices.items()}
    known = sorted((pos[g], pos[g] - ord(l)) for g, l in map_.items() if g in pos and len(l) == 1)
    out_ = dict(map_)
    general = Counter(d for _, d in known).most_common(1)
    for g, i in pos.items():
        m = mask(g.lstrip("#"))
        if g not in map_ and (m.all(0).any() or m.all(1).any()):
            continue  # a full row or column is a frame/graphic, not a letter (Cadash: solid blocks became J)
        near = Counter(d for j, d in known if 0 < abs(j - i) <= neighbours)
        d, n = near.most_common(1)[0] if near else (None, 0)
        if n >= minimum and n >= 0.8 * sum(near.values()) and 33 <= i - d <= 126:
            out_[g] = chr(i - d)
        elif general and general[0][1] >= 10 and "0" <= chr(max(0, i - general[0][0])) <= "9":
            # neighbours disagree (neighbouring digits come out of the dictionary as single letters):
            # the game's dominant offset only applies to digits, which sit right before A in ASCII
            out_[g] = chr(i - general[0][0])
    return out_


def _letter_background(g):
    m = mask(g)
    return int(len(m) - 1 - m.any(1)[::-1].argmax())


def _sign(g, l, base, x_alt):
    """Period, comma, hyphen, apostrophe and colon from position and shape; ! and ? from width."""
    m = mask(g)
    if l in "!?":  # ! is a narrow stroke; ? has the wide curve on top (Cadash: "PLAYER!" read as "PLAYER?")
        return "!" if int(m.any(0).sum()) <= 3 else "?"
    if l not in ".,'-:":
        return l
    lines = np.flatnonzero(m.any(1))
    tall, low = lines[0], lines[-1]
    if len(lines) < low - tall + 1 and low >= base - 1:
        return ":"  # colon: two pieces with an empty row between them
    if low < x_alt + 1:
        return "'"
    if low < base - 1:
        return "-"
    blocks = {tuple(m[i]) for i in lines}
    return "," if low > base or len(blocks) > 1 else "."  # period is a block of equal rows; comma has a tail


def sequence(map_, found, indices, language="en", dictionary=None):
    """Font stored in ASCII order: each offset (memory position - letter code) becomes a candidate map
    that overrides the search where it lands on a letter or digit. The one with the best dictionary score wins
    (3 Ninjas: the search got 5 of 31 right, the order A..Y was contiguous in memory)."""
    if not map_ or not indices:
        return map_
    dic = dictionary or Dictionary(language)
    ws = words(found)

    def score(m):
        return sum(math.log2(1 + n) * dic("".join(m.get(g, "#") for g in w)) for w, n in ws.items())

    pos = {g: c.most_common(1)[0][0] for g, c in indices.items() if g in map_}
    best, best_map = 0, map_
    word_order, word_map = 0, None
    confirmed, d_confirmed = (0, 0, 0), None
    px = {g: int(mask(g).sum()) for g in pos}
    median = sorted(px.values())[len(px) // 2] or 1
    size = {g: n / median for g, n in px.items()}
    for d in sorted({i - x for i in pos.values() for x in range(48, 123)}, reverse=True):  # tie: uppercase/digit
        m = dict(map_)
        covers = equal = uppers = 0
        # shape: the right offset puts punctuation on the small glyphs and letters/digits on the large ones (Bass: d and d-32
        # tied; one put ". , -" on the small glyphs, the other "n l m")
        shape = 0
        for g, i in pos.items():
            if 33 <= i - d < 127:
                c = chr(i - d)
                if c in ".,'-:;`" or c.isalnum():
                    shape += (c in ".,'-:;`") == (size[g] < 0.4)
        for g, i in pos.items():
            if 0 <= i - d < 128 and chr(i - d).isalnum():
                m[g] = chr(i - d).lower()
                covers += 1
                equal += map_[g] == m[g]
                uppers += not chr(i - d).islower()
        # compares only the words the order reads in full (Bonanza: "players start test" against "off a trust?!")
        covered = {w: k for w, k in ws.items() if all(g in pos and 0 <= pos[g] - d < 128 and chr(pos[g] - d).isalnum() for g in w)}
        if len(covered) >= 3:
            gain = sum(math.log2(1 + k) * (dic("".join(m[g] for g in w)) - dic("".join(map_[g] for g in w)))
                        for w, k in covered.items())
            if gain > best:
                best, best_map = gain, m
            # a single number (d) forming 3+ real words of 4+ letters is no accident; the search, with ~30 free letters,
            # invents words in short text (Bonanza: "trust?!" instead of "players")
            read_ones = ["".join(m[g] for g in w) for w in covered if len(w) >= 2]
            long_ones = {x for x in read_ones if len(x) >= 4 and x.isalpha() and dic(x) > UNKNOWN_WORD}
            if len(long_ones) >= 3 and sum(dic(x) > UNKNOWN_WORD for x in read_ones) >= 0.6 * len(read_ones) and len(long_ones) > word_order:
                word_order, word_map = len(long_ones), m
        # the search already agrees with the order on many glyphs: the order applies to the others too, even if the
        # dictionary prefers something else on little text (ATP Tennis: A..Y right, n o p r s t read as a a a c l a)
        # tie (uppercase at 65 also matches d-32): keep the offset that explains more glyphs
        # tie between d and d-32 (A and a in the same place): keep the one that gives uppercase and digits (Buck Rogers: 0-9 became p-y)
        if equal >= max(6, 0.3 * covers) and (equal + 0.5 * shape, uppers, covers) > confirmed:  # chance: ~1 in 20
            confirmed, d_confirmed = (equal + 0.5 * shape, uppers, covers), d
    if d_confirmed is None:
        if os.environ.get("DEBUG"): print("seq: dictionary", word_order)
        return word_map or best_map
    if os.environ.get("DEBUG"): print("seq: confirmed", d_confirmed, confirmed)
    # per contiguous font block: only where the search does not form its own sequence (Bass: lowercase at another
    # offset, correct; ATP: "n o p r s t" read as "a a a c l a", no sequence at all)
    out_ = dict(map_)
    order = sorted((i, g) for g, i in pos.items())
    blocks, current = [], []
    for i, g in order:
        if current and i - current[-1][0] > 3:
            blocks.append(current)
            current = []
        current.append((i, g))
    blocks.append(current)
    for block in blocks:
        target_ = [(i, g) for i, g in block if 0 <= i - d_confirmed < 128 and chr(i - d_confirmed).isalnum()]
        own = Counter(i - ord(map_[g]) for i, g in block if len(map_[g]) == 1).most_common(1)
        if target_ and not (own and own[0][1] >= max(3, 0.5 * len(block))):
            test = dict(out_)
            for i, g in target_:
                test[g] = chr(i - d_confirmed).lower()
            # a font block has each letter once: the search repeating letters there is garbage (ATP: n o p t -> a a a a);
            # distinct letters = a font outside ASCII order that the search got right (Beavis)
            letters = [out_[g].lower() for _, g in block if out_[g].isalpha()]
            if len(set(letters)) < 0.8 * len(letters):
                out_ = test
    return out_


def read_font(found, indices, exclude=None, language="en"):
    """Glyph -> letter table with CPU only: this is what the executable uses."""
    map_ = decipher(found, language, prior=library(exclude=exclude))
    return by_order(box(sequence(map_, found, indices, language), found), indices)


LANGUAGES = ("en", "fr", "es")  # game languages with a translation path (translation.ROUTES)


def language_and_font(found, indices, exclude=None):
    """(language, table, real words read): the font is deciphered as each language and the one that reads the most real words of
    its own language wins; English unless another reads clearly more (a few words match in any language)."""
    import re
    from wordfreq import zipf_frequency
    from retro_translator.core import progress
    import json
    import pickle
    import tempfile
    from retro_translator.core import worker
    best = None
    progress.expect(len(LANGUAGES))
    # each language on its own processor core (the slowest step of learning, a third of the time)
    with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
        pickle.dump((found, indices), f)
    try:
        jobs = [worker.start("--font", language, f.name, exclude or "") for language in LANGUAGES]
        tables = []
        for language, job in zip(LANGUAGES, jobs):
            got = worker.result(job)
            tables.append(json.loads(got) if got else read_font(found, indices, exclude, language))
            progress.tick()
    finally:
        os.remove(f.name)
    for language, table in zip(LANGUAGES, tables):
        text = " ".join("".join(table.get(c) or "_" if c else " " for c in t) for t in found)
        score = len({w for w in re.findall(r"[^\W\d_]{3,}", text.lower()) if zipf_frequency(w, language) >= 3})
        if best is None or score > 1.3 * best[0]:
            best = (score, language, table)
    return best[1], best[2], best[0]


MIN_WORDS = 2  # real words a glyph must be read in before its letter is trusted
MIN_LETTERS = 10  # confirmed letters a game needs before it is translated at all


def confirmed(table, found, language, evidence=None):
    """The table without the letters it only guessed: a glyph keeps its letter when it is read inside at least
    MIN_WORDS different real words of the language (the words of each glyph go into `evidence` when given). A guessed glyph (a second font, a digit labelled as a letter)
    would be written into the translation and read back as a wrong letter; unknown, its line is left as it was."""
    from collections import defaultdict
    from wordfreq import zipf_frequency
    words = defaultdict(set)
    for t in found:
        run = []
        for c in list(t) + [None]:
            letter = table.get(c) if c else None
            if letter and letter.isalpha():
                run.append((c, letter))
                continue
            word = "".join(l for _, l in run).lower()
            if len(word) >= 3 and zipf_frequency(word, language) >= 3:
                for g, _ in run:
                    words[g].add(word)
            run = []
    kept = {g: l for g, l in table.items() if not l.isalpha() or len(words[g]) >= MIN_WORDS}
    if len(kept) < len(table):  # words that leaned on a dropped glyph prove nothing: again, until nothing drops
        return confirmed(kept, found, language, evidence)
    if evidence is not None:
        evidence.update({g: sorted(w) for g, w in words.items()})
    return kept


def trusted(table):
    """Enough letters confirmed to translate the game without guessing."""
    return len({l.upper() for l in table.values() if l.isalpha()}) >= MIN_LETTERS
