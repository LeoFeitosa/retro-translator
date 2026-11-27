"""The preparation of a game, with no screen: learns its font from the screen (refusing a game whose letters
cannot be proven), finds and replaces its text in the ROM and keeps a translated copy. The window shows its
progress through the work dict (phase, result, error)."""
import json
import os
import re
import time

from retro_translator import VERSION, consoles
from retro_translator.core import overlay, progress
from retro_translator.core.reading import cjk, decipher, evaluate
from retro_translator.core.rewriting import rom_text
from retro_translator.core.translating import ai

MIN_KANA = 8  # glyphs placed by the kana order of the ROM font that make a game Japanese (Latin games: 0)


CJK = {}
FOLDER = os.path.join(os.path.expanduser("~"), ".retro-translator")  # learned games and settings (the program may be in a read-only folder)
REPORTS = "unreadable"  # one report per game refused for its letters
PHASES = ["play", "font", "kana", "ai", "translate", "test"]


def title(name_):
    """The game's name as a person writes it: "Madou_Monogatari_I_(J)_[!]" -> "Madou Monogatari I"."""
    return " ".join(re.sub(r"\([^)]*\)|\[[^]]*\]", " ", name_).replace("_", " ").split()) or name_


def learn_font(rom, name_, work):
    """Glyph -> letter table, cached per game. The first time it plays by itself for a few minutes (fast) and deciphers."""
    os.makedirs(FOLDER, exist_ok=True)
    path_ = os.path.join(FOLDER, f"{name_}.font.json")
    if not os.path.exists(path_):
        from retro_translator.core import worker
        kana_job = worker.start("--kana", rom)  # needs nothing from the font: on its own core at the same time
        step(work, "play")
        found, indices = evaluate.collection(rom)
        step(work, "font")
        language, table, _ = decipher.language_and_font(found, indices, exclude=name_)
        guessed, evidence = table, {}
        if language != "ja":
            table = decipher.confirmed(table, found, language, evidence)
        trusted = decipher.trusted(table)
        if trusted and language == "en":  # read as English in real words: not Japanese, no need to wait for it
            worker.stop(kana_job)
            map_ = {}
        else:
            step(work, "kana")
            got = worker.result(kana_job)  # Japanese read as Latin letters can look like Spanish words
            map_ = {bytes.fromhex(g): c for g, c in json.loads(got).items()} if got else cjk.learn(rom, "ja")[0]
        if len(map_) >= MIN_KANA:
            language = "ja"
        else:
            map_ = {}
        ascii_ = None
        if not (trusted or language == "ja"):
            report_unreadable(rom, language, guessed, table, evidence, found)
            console = consoles.for_rom(rom)  # a font drawn in variable width: maybe its text is plain ASCII
            ascii_ = rom_text.ascii_text(console.read_rom(rom), console.TEXT_START)
            language = ascii_ or language
        json.dump({"language": language, "table": table, "trusted": trusted or language == "ja", "ascii": bool(ascii_),
                   "cjk": {g.hex(): c for g, c in map_.items()}}, open(path_, "w", encoding="utf-8"))
    value_ = json.load(open(path_, encoding="utf-8"))
    overlay.translation.SOURCE = value_["language"]
    CJK["map"] = {bytes.fromhex(g): c for g, c in value_.get("cjk", {}).items()}
    work["unreadable"] = not value_.get("trusted", False)
    work["ascii"] = value_.get("ascii", False)  # unreadable on screen, its plain ASCII text translated instead
    return value_["table"]


def report_unreadable(rom, language, guessed, table, evidence, found):
    """A game refused for its letters leaves everything needed to make the next version read it: which glyphs were
    guessed, which were proven by real words, and the text as it was read. Kept across versions."""
    import hashlib
    data = open(rom, "rb").read()
    raw = bytes(consoles.for_rom(rom).read_rom(rom))
    folder = os.path.join(FOLDER, REPORTS)
    os.makedirs(folder, exist_ok=True)
    lines = []
    for t in found:
        line = "".join((guessed.get(c) or "_") if c else " " for c in t).strip()
        if line and line not in lines:
            lines.append(line)
    report = {"version": VERSION, "rom": os.path.basename(rom), "size": len(data),
              "md5": hashlib.md5(data).hexdigest(), "header": raw[0x150:0x180].decode("latin-1").strip(),
              "language": language, "min_words": decipher.MIN_WORDS, "min_letters": decipher.MIN_LETTERS,
              "confirmed_letters": "".join(sorted({l.upper() for l in table.values() if l.isalpha()})),
              "glyphs": [{"glyph": g, "guess": l, "confirmed": g in table, "words": evidence.get(g, [])}
                         for g, l in sorted(guessed.items(), key=lambda x: x[1])],
              "lines_read": lines[:400]}
    name_ = os.path.splitext(os.path.basename(rom))[0]
    json.dump(report, open(os.path.join(folder, f"{name_}.json"), "w", encoding="utf-8"), ensure_ascii=False,
              indent=1)


def step(work, phase):
    work["phase"], work["since"] = phase, time.time()
    progress.expect(0)


def tag(language):
    """The language of the files a translation is kept in: the AI's own apart, so turning it on translates again."""
    return language + (".ai" if ai.ENABLED else "")


def prepare(rom, name_, language, work, folder=None):
    """Everything the first time needs: learns the font and, for a Latin game, writes the translated ROM."""
    try:
        table = learn_font(rom, name_, work)
        if work["unreadable"] and not work["ascii"]:  # a wrong letter table gives a broken translation: better none
            return
        work["japanese"] = overlay.translation.SOURCE in ("ja", "zh")
        translated = os.path.join(FOLDER, f"{name_}.{tag(language)}.bin")
        if work["japanese"]:
            translated = rom  # the ROM holds no Latin letters to rewrite: the translation is drawn on top
        elif os.path.exists(translated + ".rejected"):
            translated = rom
        elif not os.path.exists(translated):
            try:  # text found in the ROM is replaced right there: the game draws the translation itself
                if ai.ENABLED and not ai.ready():  # chosen on the home screen: downloaded once, here
                    step(work, "ai")
                    try:
                        ai.install()
                    except OSError:  # no connection or a damaged download: the usual translation, said on screen
                        ai.ENABLED, work["ai_failed"] = False, True
                        translated = os.path.join(FOLDER, f"{name_}.{tag(language)}.bin")
                step(work, "translate")
                mode_ = rom_text.translate(rom, language, translated, table, ascii_only=work["ascii"])
                step(work, "test")
                mode_ = mode_ and mode_[1] and rom_text.link_(rom, translated)  # nothing written: not translated
                if mode_ and work["ascii"] and not rom_text.visible(rom, translated, mode_ == "memory"):
                    mode_ = False  # text the player never sees (debug menus): not a translation
                if mode_ == "memory":
                    open(translated + ".memory", "w").close()
                if not mode_:
                    if os.path.exists(translated):
                        os.replace(translated, translated + ".rejected")  # does not run like the original: overlay only
                    else:
                        open(translated + ".rejected", "w").close()  # no text found in the ROM: do not search again
                    translated = rom
            except Exception as e:
                print("ROM not translated:", e, flush=True)
                translated = rom
        if work["ascii"] and translated == rom:  # nothing visible could be translated: refused, as unreadable
            return
        # a Latin game whose ROM could not be rewritten: only the overlay translates, and only what it reads whole
        work["partial"] = translated == rom and not work["japanese"]
        work["unreadable"] = False
        if folder and translated != rom and not os.path.exists(translated + ".memory"):
            os.makedirs(folder, exist_ok=True)  # a copy for any emulator, the same kind of file that came in
            work["saved"] = os.path.join(folder, f"{title(name_)} ({language}){os.path.splitext(rom)[1]}")
            consoles.for_rom(rom).write_rom(rom, open(translated, "rb").read(), work["saved"])
        work["result"] = table, translated
    except Exception as e:
        work["error"] = e
    finally:
        work["phase"] = None
