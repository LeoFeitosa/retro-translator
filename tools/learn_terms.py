"""Development: game vocabulary for short menu items. Apertium translates "Arcade" as "Arcada" and "Court" as "Corte";
the AI (Ollama) translates each short item from the games' ROM text (output/*.texts.json) in the sense of a video game
menu, with the other items of the same menu as context. Kept only where it differs from Apertium.
Output: rules/<lang>.terms.json, used by the executable (no AI) for any game's items of up to two words.
Usage: python -m tools.learn_terms [lang]"""
import glob
import json
import os
import re
import sys
import time
import urllib.request

from retro_translator.core.reading import table
from retro_translator.core.translating import translation
from tools.learn_translation import NAMES
from retro_translator import DATA

MODEL = "qwen2.5:14b"  # text only: better wording than the vision model, still fits the GPU


def short(text):
    """A short item made only of common English words: general game vocabulary, valid for any game (never a name
    or a phrase of one game)."""
    from wordfreq import zipf_frequency
    return re.fullmatch(r"[A-Za-z][A-Za-z'\-]*( [A-Za-z][A-Za-z'\-]*)?", text.strip()) is not None and \
        all(zipf_frequency(w, "en") >= 3.5 for w in text.lower().split())


def ask(item, menu, language):
    while table.gpu_busy():  # other GPU jobs have priority
        time.sleep(30)
    prompt = (f"These are items shown together on a screen of a Sega Mega Drive game: {', '.join(menu)}.\n"
              f"Translate the item \"{item}\" into {NAMES[language]} the way an official localization of the game "
              f"for {NAMES[language]} players would show it on that screen. Gaming terms those players use in English "
              f"stay in English. Names stay unchanged. Keep it short. "
              f"Output only the translation.")
    body = json.dumps({"model": MODEL, "prompt": prompt, "stream": False, "options": {"temperature": 0}}).encode()
    req = urllib.request.Request(table.OLLAMA, body, {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=600))["response"].strip().strip('".').strip()


def _stems(text):
    """First 4 letters (no accents) of each word of 4+ letters: "Automático" and "Automática" share one."""
    import unicodedata
    t = unicodedata.normalize("NFD", text.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return {w[:4] for w in re.findall(r"[a-z]{4,}", t)}


def accept(item, ap, answer, language):
    """The AI answer only where it is safe: Apertium left a name or acronym as it is (the AI invents from the menu
    context: "RNC" -> "DIFICULDADE"), every word is common in the language ("MUSICA DE FONDO" is Spanish), and the
    plural stays plural ("CONTROLS" -> "CONTROLE")."""
    from wordfreq import zipf_frequency
    if not answer or "\n" in answer or len(answer) > 2 * len(item) + 8:
        return False
    if (ap or "").lower() == item.lower():
        return False
    if any(zipf_frequency(w, language) < 2.5 for w in re.findall(r"\w+", answer.lower())
           if w not in item.lower().split()):  # English words kept as they are (Arcade, Start) are fine
        return False
    if len(answer.split()) > len(item.split()):
        return False  # adds meaning ("AUTOMATIC" -> "REPRODUÇÃO AUTOMÁTICA", "NOT FOR" -> "NÃO PARA REVIEW")
    if answer.lower() == item.lower():
        return not (_stems(item) & _stems(ap or ""))  # keeping the English only beats a word that is not a
        # cognate of it ("CREDITS" -> "CRÉDITOS" is already right)
    if not (_stems(answer) & _stems(ap or "")):
        return False  # a new meaning, not a better wording of Apertium's ("BROTHER BEAR" -> "TESTE DE SOM")
    if len(_stems(answer) - _stems(ap or "") - _stems(item)) > 1:
        return False  # more than one word Apertium did not give
    kept = [w for w in answer.lower().split() if w in item.lower().split()]
    if 0 < len(kept) < len(answer.split()):
        return False  # half English, half translated ("RAPID FIRE" -> "FIRE RÁPIDO")
    plural = lambda t: t.split()[-1].lower().endswith("s") if t.split() else False
    return plural(item) == plural(answer) or item.lower().split()[-1] == answer.lower().split()[-1]


def main(language="pt"):
    path_ = os.path.join(DATA, "rules", f"{language}.terms.json")
    terms = json.load(open(path_, encoding="utf-8")) if os.path.exists(path_) else {}
    for f in sorted(glob.glob("output/*.bin.texts.json")):  # English items of every game translated so far
        texts = json.load(open(f, encoding="utf-8"))
        items_ = [t for t in texts if short(t)]
        for item in items_:
            key_ = " ".join(item.lower().split())
            if key_ in terms:
                continue
            menu = [t for t in items_ if t != item][:12]
            pt = ask(item, menu, language)
            ap = translation.translate_batch([item], language, with_rules=False)[0]
            if not accept(item, ap, pt, language):
                pt = ap
            terms[key_] = pt if pt.lower() != (ap or "").lower() else None  # None: Apertium already gets it
            print(f"{item!r}: apertium {ap!r} -> {pt!r}", flush=True)
            tmp = path_ + ".tmp"
            json.dump(terms, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=0, sort_keys=True)
            os.replace(tmp, path_)


if __name__ == "__main__":
    main(*sys.argv[1:2])
