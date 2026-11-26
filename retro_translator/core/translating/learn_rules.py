"""Development: learns general correction rules for Apertium by comparing with the AI translations (memory/<lang>.json).
Rule = a swap of up to 3 words seen in several games and almost always right. Measured on held-out games (chrF).
Output: rules/<lang>.json, which the executable applies after Apertium (no AI)."""
import difflib
import re
from collections import Counter, defaultdict


MIN_GAMES, MIN_PRECISION, MAX_N = 3, 0.6, 3


def tokens(t, box=False):
    return re.findall(r"\w+(?:-\w+)*|[^\w\s]", t if box else t.lower())  # "apanhá-la" is one word


def chrf(hyp, ref, n=6, beta=2):
    def ngr(s, k):
        s = s.lower()
        return Counter(s[i:i + k] for i in range(len(s) - k + 1))
    p = r = 0
    for k in range(1, n + 1):
        h, g = ngr(hyp, k), ngr(ref, k)
        common = sum((h & g).values())
        p += common / max(1, sum(h.values()))
        r += common / max(1, sum(g.values()))
    p, r = p / n, r / n
    return 0 if p + r == 0 else (1 + beta ** 2) * p * r / (beta ** 2 * p + r)


def apply(text_tokens, rules):
    out_, i = [], 0
    while i < len(text_tokens):
        for n in range(MAX_N, 0, -1):
            key_ = " ".join(text_tokens[i:i + n]).lower()  # case-insensitive match; the rest of the text keeps its case
            if len(text_tokens[i:i + n]) == n and key_ in rules:
                out_ += rules[key_].split()
                i += n
                break
        else:
            out_.append(text_tokens[i])
            i += 1
    return out_


def join_(toks):
    return re.sub(r" ([^\w\s])", r"\1", " ".join(toks))


def learn(pairs_):
    """pairs: list of (game, apertium_tokens, ai_tokens)."""
    swaps, games = Counter(), defaultdict(set)
    for game, a, b in pairs_:
        for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
            if op == "replace" and i2 - i1 <= MAX_N and j2 - j1 <= MAX_N:
                k = (" ".join(a[i1:i2]), " ".join(b[j1:j2]))
                swaps[k] += 1
                games[k].add(game)
    seen = Counter()
    for _, a, _ in pairs_:
        for n in range(1, MAX_N + 1):
            for i in range(len(a) - n + 1):
                seen[" ".join(a[i:i + n])] += 1
    rules = {}
    for (src, to), n in swaps.most_common():
        if src in rules or len(games[(src, to)]) < MIN_GAMES or n < MIN_PRECISION * seen[src]:
            continue
        rules[src] = to
    return rules
