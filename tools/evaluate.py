"""Development: the bulk evaluation of a ROM folder, one game per process (the core loads one ROM per process);
results.jsonl keeps every finished game. Usage, from the repository root: python -m tools.evaluate ROM_FOLDER [limit]
| python -m tools.evaluate --collect ROM_FOLDER (CPU-only collection, several games at once)."""
import json
import os
import subprocess
import sys
import time

from retro_translator.core.reading import table
from retro_translator.core.reading.evaluate import evaluate, region_ok

if sys.argv[1] == "--um":  # child process: one game only (the core loads one ROM per process)
    print(json.dumps(evaluate(sys.argv[2]), ensure_ascii=False))
    sys.exit()
if sys.argv[1] == "--collect":  # CPU-only step, several games at once, ahead of the GPU step
    from concurrent.futures import ThreadPoolExecutor
    folder = sys.argv[2]
    games = sorted(n for n in os.listdir(folder) if region_ok(n)
                   and not os.path.exists(os.path.join("captures", os.path.splitext(n)[0] + ".idx.pkl")))

    def one(name_):
        p = subprocess.run([sys.executable, "-c", "from retro_translator.core.reading import evaluate; "
                            f"evaluate.collection({os.path.join(folder, name_)!r})"],
                           capture_output=True, text=True, timeout=1800)
        print(name_, "collected" if p.returncode == 0 else "failure: " + p.stderr.strip()[-150:], flush=True)

    with ThreadPoolExecutor(3) as ex:  # ponytail: 3 of 8 cores, other jobs also use the CPU
        list(ex.map(one, games))
    sys.exit()
folder = sys.argv[1]
limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10 ** 6
done_ = set()
if os.path.exists("results.jsonl"):
    done_ = {json.loads(l)["game"] for l in open("results.jsonl")}
games = sorted(n for n in os.listdir(folder) if region_ok(n) and n not in done_)[:limit]
for name_ in games:
    while table.gpu_busy():  # waits for other GPU jobs to release the card
        time.sleep(60)
    try:
        p = subprocess.run([sys.executable, "-m", "tools.evaluate", "--um", os.path.join(folder, name_)],
                           capture_output=True, text=True, timeout=4 * 3600)
        r = json.loads(p.stdout.strip().splitlines()[-1]) if p.returncode == 0 else \
            {"failure": p.stderr.strip().splitlines()[-1][:200] if p.stderr.strip() else f"exit {p.returncode}"}
    except subprocess.TimeoutExpired:
        r = {"failure": "timed out"}
    r["game"] = name_
    with open("results.jsonl", "a") as f:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(name_, r.get("accuracy"), r.get("glyphs"), r.get("failure", ""), flush=True)
