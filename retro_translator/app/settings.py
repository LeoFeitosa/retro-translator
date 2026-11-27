"""The user's folder: the last choices (game, language, folder) and the clean-up when a new version runs."""
import json
import os
import sys

from retro_translator import DATA, HERE
from retro_translator.core import preparation

def build_fingerprint():
    """Fingerprint of this build: the executable itself, or, from source, the code and the rules."""
    import glob
    import hashlib
    h = hashlib.sha1()
    paths = [sys.executable] if getattr(sys, "frozen", False) else \
        sorted(glob.glob(os.path.join(HERE, "**", "*.py"), recursive=True) + glob.glob(os.path.join(DATA, "rules", "*")))
    for a in paths:
        with open(a, "rb") as f:
            for block in iter(lambda: f.read(1 << 20), b""):
                h.update(block)
    return h.hexdigest()


def clear_if_changed():
    """A new version learns and translates every game again: what an older build left behind (translated ROMs,
    fonts, markers) is deleted, so nothing has to be cleaned by hand."""
    import shutil
    mark, v = os.path.join(preparation.FOLDER, "version.txt"), build_fingerprint()
    if os.path.exists(mark) and open(mark).read() == v:
        return
    for name_ in os.listdir(preparation.FOLDER):
        # the user's choices, the reports, the AI download (2.8 GB) and the open logs survive a new version
        if name_ in ("settings.json", preparation.REPORTS, "ai", "crash.log", "error.log"):
            continue
        route = os.path.join(preparation.FOLDER, name_)
        shutil.rmtree(route, ignore_errors=True) if os.path.isdir(route) else os.remove(route)
    open(mark, "w").write(v)


def settings(**new):
    """The last choices (game, language, folder), kept for the next time."""
    path_ = os.path.join(preparation.FOLDER, "settings.json")
    value_ = json.load(open(path_, encoding="utf-8")) if os.path.exists(path_) else {}
    if new:
        value_.update(new)
        os.makedirs(preparation.FOLDER, exist_ok=True)
        json.dump(value_, open(path_, "w", encoding="utf-8"))
    return value_


def default_folder():
    docs = os.path.join(os.path.expanduser("~"), "Documents")
    return os.path.join(docs if os.path.isdir(docs) else os.path.expanduser("~"), "Retro Translator")
