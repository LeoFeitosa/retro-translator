"""Starts the program.
    python -m retro_translator [GAME] [language]      the window (without a game it opens the file picker)
    python -m retro_translator --test GAME [language] no window: plays by itself and saves screens to output/
Keys: arrows, Z/X/C = A/B/C, Enter = Start, Esc = quit, F1 = translation on/off."""
import os
import sys

from retro_translator.app import window
from retro_translator.core import preparation
from retro_translator.core.rewriting import rom_text


def run(args):
    if args[:1] == ["--brightness"]:  # internal: the screen measured in a separate process (rom_text.link_)
        print(rom_text.brightness(*args[1:3]))
    elif args[:1] == ["--screens"]:  # internal: the screen fingerprints (rom_text.visible)
        print(rom_text.screens(*args[1:3]))
    elif args[:1] == ["--font"]:  # internal: one language of the font decipherment (decipher.language_and_font)
        import json
        import pickle
        from retro_translator.core.reading import decipher
        found, indices = pickle.load(open(args[2], "rb"))
        print(json.dumps(decipher.read_font(found, indices, args[3] or None, args[1])))
    elif args[:1] == ["--kana"]:  # internal: the Japanese check (preparation.learn_font)
        import json
        from retro_translator.core.reading import cjk
        print(json.dumps({g.hex(): c for g, c in cjk.learn(args[1], "ja")[0].items()}))
    elif args[:1] == ["--test"]:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        window.main(args[1], args[2] if len(args) > 2 else "pt", test=6000)
    else:
        try:
            window.main(*args[:2])
        except Exception:  # the windowed executable has no console: the error goes to a file the user can send
            import traceback
            os.makedirs(preparation.FOLDER, exist_ok=True)
            open(os.path.join(preparation.FOLDER, "error.log"), "w", encoding="utf-8").write(traceback.format_exc())
            raise


if __name__ == "__main__":
    if sys.argv[1:2] and sys.argv[1] in ("--brightness", "--screens", "--font", "--kana"):
        try:  # a helper process: on error it just ends (the executable would show a dialog nobody sees, waiting
            run(sys.argv[1:])  # forever), and the program goes on without its answer
        except Exception:
            sys.exit(1)
    else:
        run(sys.argv[1:])
