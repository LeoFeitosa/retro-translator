"""Development: plays a ROM for some minutes, learns its font table and saves it to the font library
(retro_translator/data/tables). Usage: python -m tools.learn_font ROM [minutes]"""
import json
import os
import sys

from retro_translator import DATA
from retro_translator.core.reading.table import collect, decode_, learn

rom = sys.argv[1]
minutes = float(sys.argv[2]) if len(sys.argv) > 2 else 3
found = collect(rom, minutes)
print(f"{len(found)} distinct excerpts")
table, votes = learn(found)
name_ = os.path.splitext(os.path.basename(rom))[0]
os.makedirs(os.path.join(DATA, "tables"), exist_ok=True)
json.dump({"table": table, "votes": {g: dict(v) for g, v in votes.items()}},
          open(os.path.join(DATA, "tables", f"{name_}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"{len(table)} glyphs -> {os.path.join(DATA, 'tables', name_ + '.json')}")
print("--- excerpts decoded with the table ---")
for excerpt, _ in found.most_common(40):
    print(decode_(excerpt, table))
