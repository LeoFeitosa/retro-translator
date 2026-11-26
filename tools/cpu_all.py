import json, os, pickle, sys
from collections import Counter
sys.path.insert(0, ".")
from retro_translator.core.reading import decipher
dic = decipher.Dictionary()
for l in open("results.jsonl"):
    r = json.loads(l)
    if (r.get("accuracy") or 0) < 0.8:
        continue
    j = os.path.splitext(r["game"])[0]
    try:
        a = pickle.load(open(f"captures/{j}.pkl", "rb")); ix = pickle.load(open(f"captures/{j}.idx.pkl", "rb"))
        tab = json.load(open(f"tables/{j}.json"))
    except FileNotFoundError:
        continue
    m = decipher.read_font(a, ix, exclude=j)
    usage = Counter(g for w in decipher.words(a) for g in w if g in tab)
    ok = round(sum(n for g, n in usage.items() if m.get(g) == tab[g]) / sum(usage.values()), 2) if usage else None
    low = round(sum(n for g, n in usage.items() if (m.get(g) or "").lower() == tab[g].lower()) / sum(usage.values()), 2) if usage else None
    print(j[:34], r.get("cpu_accuracy"), ok, "semcaixa", low, flush=True)
