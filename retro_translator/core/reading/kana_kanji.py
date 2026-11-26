"""Kana -> kanji conversion, like a Japanese input method: game text is often all kana ("せんとうそくど"), which
translation models misread; written with kanji ("戦闘速度") it translates well. Best path over the Mozc open-source
dictionary (word costs plus the connection cost between word classes). No AI.
Data built by tools/kanji.py into kanji/."""
import gzip
import os
import re

import numpy as np
from retro_translator import DATA

_DATA = {}
UNKNOWN = 1851  # class of a common noun: unknown runs (names, katakana words) are read as nouns
UNKNOWN_COST = 6000


def _load():
    if not _DATA:
        dic = {}
        with gzip.open(os.path.join(DATA, "kanji", "dic.tsv.gz"), "rt", encoding="utf-8") as f:
            for line in f:
                reading, lid, rid, cost, word = line.rstrip("\n").split("\t")
                dic.setdefault(reading, []).append((int(lid), int(rid), int(cost), word))
        _DATA["dic"] = dic
        written = {}  # words by how they are written: text read from the screen may already have kanji ("少し")
        for entries in dic.values():
            for lid, rid, cost, word in entries:
                if re.search(r"[一-鿿]", word):
                    written.setdefault(word, []).append((lid, rid, cost, word))
        _DATA["written"] = written
        _DATA["con"] = np.load(os.path.join(DATA, "kanji", "connection.npz"))["c"].astype(np.int32)
        _DATA["max"] = max(map(len, dic))
    return _DATA


def _hiragana(t):
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in t)


def convert(text):
    """The kana of `text` written as a Japanese writer would, with kanji. Katakana words stay katakana."""
    d = _load()
    dic, con, n = d["dic"], d["con"], len(text)
    search_ = _hiragana(text)
    # best[i] = (cost, rid, start, word) of the best path ending at i
    best = [None] * (n + 1)
    best[0] = (0, 0, -1, "")
    for i in range(n):
        if best[i] is None:
            continue
        cost0, rid0 = best[i][0], best[i][1]
        options = []
        for end in range(i + 1, min(n, i + d["max"]) + 1):
            for lid, rid, cost, word in dic.get(search_[i:end], ()):
                if re.fullmatch(r"[ァ-ヶー]+", text[i:end]) and word != text[i:end]:
                    continue  # a katakana word is not rewritten as kanji
                if re.fullmatch(r"[ァ-ヶー]+", word) and word != text[i:end]:
                    continue  # nor hiragana as a katakana name ("しのん" -> "シノン")
                options.append((end, lid, rid, cost, word))
            options += [(end, *e) for e in d["written"].get(text[i:end], ())]
        k = re.match(r"[ァ-ヶー]+|[^ぁ-ゖァ-ヶー一-鿿]+|[一-鿿]", text[i:])  # unknown run: kept as it is
        options.append((i + (k.end() if k else 1), UNKNOWN, UNKNOWN, UNKNOWN_COST,
                       text[i:i + (k.end() if k else 1)]))
        for end, lid, rid, cost, word in options:
            total = cost0 + cost + con[rid0, lid]
            if best[end] is None or total < best[end][0]:
                best[end] = (total, rid, i, word)
    parts, i = [], n
    while i > 0:
        parts.append(best[i][3])
        i = best[i][2]
    return "".join(reversed(parts))
