"""Mean chrF of the executable's translation against the AI reference corpus (memory/<lang>.json): did a change
to the translation rules make the output closer to a sensible translation? Usage: python -m tools.chrf [lang]"""
import json
import sys

from retro_translator.core.translating import learn_rules
from retro_translator.core.translating import translation

language = sys.argv[1] if len(sys.argv) > 1 else "pt"
m = json.load(open(f"memory/{language}.json", encoding="utf-8"))
en = list(m)
out_ = []
for i in range(0, len(en), 200):
    out_ += translation.translate_batch(en[i:i + 200], language)
scores = [learn_rules.chrf(s or "", m[e]) for e, s in zip(en, out_)]
print(f"mean chrF: {sum(scores) / len(scores):.4f} over {len(scores)} sentences")
