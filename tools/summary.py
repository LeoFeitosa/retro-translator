"""Summary of results.jsonl: python -m tools.summary"""
import json
from collections import Counter
rs = [json.loads(l) for l in open("results.jsonl")]
ok = [r for r in rs if "failure" not in r]
med = [r for r in ok if r["accuracy"] is not None]
print(f"{len(rs)} games | failures {len(rs) - len(ok)} | no testable text {len(ok) - len(med)}")
if med:
    print(f"mean accuracy {sum(r['accuracy'] for r in med) / len(med):.2f} | "
          f"100%: {sum(r['accuracy'] == 1 for r in med)} | below 50%: {sum(r['accuracy'] < .5 for r in med)}")
    print("worst:", [(r["game"][:30], r["accuracy"]) for r in sorted(med, key=lambda r: r["accuracy"])[:10]])
cpu = [r["cpu_accuracy"] for r in ok if r.get("cpu_accuracy") is not None]
if cpu:
    print(f"CPU only (decipher): mean {sum(cpu) / len(cpu):.2f} over {len(cpu)} games | >=0.9: {sum(c >= .9 for c in cpu)}")
print("failures:", Counter(r["failure"][:60] for r in rs if "failure" in r).most_common(5))


def kind(r):
    """Likely cause, to fix by group and not game by game."""
    if "failure" in r:
        return "program failure"
    if r["excerpts"] < 5:
        return "almost no text in 3 min (collection)"
    if r["glyphs"] > 90:
        return "variable-width font or garbage (too many glyphs)"
    if r["accuracy"] is None and r["glyphs"] < 30:
        return "little text collected (<30 letters)"
    if r["accuracy"] is None:
        return "no testable excerpt (table does not close)"
    if r["accuracy"] >= 0.9:
        return "ok"
    if r.get("highs"):
        return "8x16 font with errors"
    if r.get("empty", 0) > r.get("readings", 0) / 2:
        return "AI cannot read the excerpt (OCR)"
    return "reading/alignment error"


groups = {}
for r in rs:
    groups.setdefault(kind(r), []).append(r["game"][:35])
print("\nby cause:")
for k, v in sorted(groups.items(), key=lambda kv: -len(kv[1])):
    print(f"  {len(v):4d}  {k}  ex.: {v[:3]}")
