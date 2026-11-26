"""Development: the AI (Ollama) translates the text already read from the games -> memory/<lang>.json. This is NOT
read by the executable (no fixed phrase list by design): it is the corpus that teaches the general engine (vocabulary
and Apertium correction rules) and measures it on held-out games. Resumes where it stopped; waits for a free GPU."""
import glob
import json
import os
import sys
import time
import urllib.request

from retro_translator.core.reading import decipher
from retro_translator.core.reading import table

MODEL = "qwen2.5vl:7b"  # same model as the evaluation: no model swap on the GPU and no extra memory
NAMES = {"pt": "Brazilian Portuguese", "es": "Spanish", "fr": "French", "en": "English"}


def sentences(game, dic):
    """Text lines of the game, read with the vision AI table; without it, with the decipherer (cached in captures/)."""
    import pickle
    found = pickle.load(open(f"captures/{game}.pkl", "rb"))
    reference = os.path.exists(f"tables/{game}.json")
    if reference:
        tab = json.load(open(f"tables/{game}.json"))
    else:
        path_ = f"captures/{game}.font.json"
        if not os.path.exists(path_):
            indices = pickle.load(open(f"captures/{game}.idx.pkl", "rb"))
            json.dump(decipher.read_font(found, indices, exclude=game), open(path_, "w"))
        tab = json.load(open(path_))
    out_ = set()
    for excerpt in found:
        t = " ".join(table.decode_(excerpt, tab).split())
        words = [p for p in t.split() if any(c.isalpha() for c in p)]
        if "?" in t.replace("?", "", t.count("?") - 1) or len(words) < 2:
            continue
        good_ones = [p for p in words if dic(p.lower()) > decipher.UNKNOWN_WORD]
        if reference and len(good_ones) >= 0.7 * len(words):
            out_.add(t)
        # read by the decipherer: clear sentences only ("on Son Iron", "OUR UNTO MOST" got through)
        elif not reference and len(words) >= 3 and len(good_ones) >= 0.85 * len(words) \
                and sum(len(p.strip(".,!?:;'\"-")) >= 3 for p in good_ones) >= 2:
            out_.add(t)
    return out_


def translate(text, language, game):
    prompt = (f"Translate this line from a Sega Mega Drive game into natural {NAMES[language]}, "
              f"as an official localization would. Keep names of characters, places and items. Keep the same "
              f"capitalization style. Keep it about the same length. Output only the translation.\n\n{text}")
    body = json.dumps({"model": MODEL, "prompt": prompt, "stream": False, "options": {"temperature": 0}}).encode()
    req = urllib.request.Request(table.OLLAMA, body, {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=600))["response"].strip().strip('"')


def main(language="pt"):
    os.makedirs("memory", exist_ok=True)
    path_ = f"memory/{language}.json"
    memory = json.load(open(path_, encoding="utf-8")) if os.path.exists(path_) else {}
    dic = decipher.Dictionary()
    for t in sorted(glob.glob("captures/*.idx.pkl")):
        game = os.path.basename(t)[:-len(".idx.pkl")]
        if not os.path.exists(f"captures/{game}.pkl"):
            continue
        list_ = sorted(sentences(game, dic))
        for f in list_:
            if f not in memory:
                while table.gpu_busy():
                    time.sleep(30)
                memory[f] = translate(f, language, game.split("_(")[0].replace("_", " "))
                json.dump(memory, open(path_ + ".tmp", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
                os.replace(path_ + ".tmp", path_)
        print(game, len(memory), flush=True)


if __name__ == "__main__":
    while True:  # new collections arrive from the batch: run again from time to time (finished work is skipped)
        main(*sys.argv[1:])
        time.sleep(600)
