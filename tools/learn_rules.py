"""Development: learns the phrase rules that bring the rule-based translation closer to the reviewed one
(translation memory) and measures them on games left out. Writes retro_translator/data/rules/<language>.json.
Usage: python -m tools.learn_rules [language]"""
import glob
import json
import os
import sys

from retro_translator import DATA
from retro_translator.core.reading import decipher
from retro_translator.core.translating import translation
from retro_translator.core.translating.learn_rules import apply, chrf, join_, learn, tokens
from tools import learn_translation


def main(language="pt"):
    memory = json.load(open(f"memory/{language}.json", encoding="utf-8"))
    cache_path = f"memory/{language}.apertium.json"
    cache = json.load(open(cache_path, encoding="utf-8")) if os.path.exists(cache_path) else {}
    dic = decipher.Dictionary()
    source = {}
    for t in sorted(glob.glob("captures/*.idx.pkl")):
        game = os.path.basename(t)[:-len(".idx.pkl")]
        if os.path.exists(f"captures/{game}.pkl") and (os.path.exists(os.path.join(DATA, "tables", f"{game}.json"))
                                                     or os.path.exists(f"captures/{game}.font.json")):
            for f in learn_translation.sentences(game, dic):
                source.setdefault(f, game)
    missing_ = [en for en in memory if en not in cache]
    for i in range(0, len(missing_), 200):  # in batch: starting the Apertium programs is what costs
        cache.update(zip(missing_[i:i + 200], translation.translate_batch(missing_[i:i + 200], language, with_rules=False)))
    json.dump(cache, open(cache_path, "w", encoding="utf-8"), ensure_ascii=False)
    pairs_ = [(source.get(en, en), tokens(cache[en]), tokens(pt)) for en, pt in memory.items()]
    # measured on held-out games: 5 folds
    list_ = sorted({j for j, _, _ in pairs_})
    before = after = 0
    for part in range(5):
        outside = set(list_[part::5])
        rules = learn([p for p in pairs_ if p[0] not in outside])
        for j, a, b in pairs_:
            if j in outside:
                before += chrf(join_(a), join_(b))
                after += chrf(join_(apply(a, rules)), join_(b))
    print(f"chrF on games left out of learning: {before / len(pairs_):.3f} -> {after / len(pairs_):.3f} ({len(pairs_)} sentences, {len(list_)} games)")
    rules = learn(pairs_)
    os.makedirs(os.path.join(DATA, "rules"), exist_ok=True)
    json.dump(rules, open(os.path.join(DATA, "rules", f"{language}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(len(rules), "rules:", list(rules.items())[:15])


if __name__ == "__main__":
    assert join_(apply(tokens("jogo em cima ."), {"jogo em cima": "fim de jogo"})) == "fim de jogo."
    main(*sys.argv[1:])
