"""The window: the home screen (game, language, folder), the preparing screen, the refusal screen and the game
itself with the translation drawn over it. Started by retro_translator/__main__.py."""
import json
import os
import random
import sys
import threading
import time

import numpy as np
import pygame

from retro_translator.core.reading import cjk
from retro_translator.core.rewriting import rom_text
from retro_translator.core import overlay
from retro_translator.core import progress
from retro_translator import consoles
from retro_translator import DATA
from retro_translator.app import updater
from retro_translator.app.dialogs import pick_folder, pick_rom
from retro_translator.app.settings import clear_if_changed, default_folder, settings
from retro_translator.app.texts import LANGUAGES, TEXT
from retro_translator.core import preparation
from retro_translator.core.preparation import prepare, title

KEYS = {pygame.K_UP: "UP", pygame.K_DOWN: "DOWN", pygame.K_LEFT: "LEFT", pygame.K_RIGHT: "RIGHT",
          pygame.K_z: "Y", pygame.K_x: "B", pygame.K_c: "A", pygame.K_RETURN: "START"}
SCALE = 3
INK, PANEL, EDGE = (13, 15, 41), (22, 25, 59), (44, 79, 209)
YELLOW, WHITE, SILVER, DIM, GREEN = (242, 194, 48), (255, 255, 255), (190, 198, 214), (96, 104, 150), (96, 214, 128)
STEPS = [("learn", ["play", "font", "kana"]), ("translate", ["translate"]), ("test", ["test"])]  # what the screen lists
# share of the whole preparation each phase takes (measured on Alien Storm and Madou): the one bar covers them all
WEIGHT = {"play": 0.22, "font": 0.35, "kana": 0.25, "translate": 0.08, "test": 0.10}
EXPECTED = {"play": 70, "font": 110, "kana": 80, "translate": 25, "test": 30}  # seconds, for a phase with no count
_GLYPHS, _RENDERED = {}, {}
def update(screen, info, t):
    """The update screen: downloads the new executable with a progress bar (Esc cancels) and restarts into it.
    False when it did not finish: the program goes on as it is."""
    clock = pygame.time.Clock()

    def progress(done):
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE):
                raise KeyboardInterrupt
        panel = frame_(screen, "")
        write(screen, t["updating"].format(info["version"]), (panel.centerx, panel.y + 120), WHITE, 3, "center")
        f_ = done / info["size"]
        bar = pygame.Rect(panel.x + 40, panel.centery, panel.w - 80, 48)
        pygame.draw.rect(screen, INK, bar)
        pygame.draw.rect(screen, YELLOW, (bar.x + 4, bar.y + 4, int((bar.w - 8) * f_), bar.h - 8))
        write(screen, f"{int(f_ * 100)}%   {done >> 20} / {info['size'] >> 20} MB", (panel.centerx, bar.bottom + 24),
              SILVER, 2, "center")
        scanlines(screen)
        pygame.display.flip()
        clock.tick(60)

    new = updater.download(info, progress)
    if not new:
        return False
    updater.install(new)
    pygame.quit()
    os._exit(0)


def _glyph(ch):
    """GNU Unifont, the 8x16 pixel font the program already carries: accents, arrows and kana all have a drawing."""
    if not _GLYPHS:
        import gzip
        with gzip.open(os.path.join(DATA, "kanji", "unifont.hex.gz"), "rt") as f:
            for line in f:
                c, h = line.strip().split(":")
                _GLYPHS[chr(int(c, 16))] = h
    h = _GLYPHS.get(ch) or _GLYPHS["?"]
    w = len(h) // 4
    return np.array([[int(h[i * w // 4:(i + 1) * w // 4], 16) >> (w - 1 - j) & 1 for j in range(w)]
                     for i in range(16)], bool)


def write(screen, text, pos, color, size=2, align="left"):
    """Pixel text with a drop shadow; align left, center or right of pos."""
    key = (text, color, size)
    if key not in _RENDERED:
        m = np.hstack([_glyph(c) for c in text] or [np.zeros((16, 1), bool)]).T
        surfs = []
        for c in ((1, 1, 1), color):
            px = np.zeros(m.shape + (3,), np.uint8)
            px[m] = c
            sf = pygame.surfarray.make_surface(px)
            sf.set_colorkey((0, 0, 0))
            surfs.append(pygame.transform.scale(sf, (m.shape[0] * size, 16 * size)))
        _RENDERED[key] = surfs
    shadow, img = _RENDERED[key]
    x = pos[0] - {"left": 0, "center": img.get_width() // 2, "right": img.get_width()}[align]
    screen.blit(shadow, (x + size, pos[1] + size))
    return screen.blit(img, (x, pos[1]))


def notice(screen, text, color, small=False):
    """A small retro box on top of the game: F1 on/off, or a line being translated."""
    size = 1 if small else 2
    w = len(text) * 8 * size + 24
    box = pygame.Rect(screen.get_width() - w - 12, 12, w, 16 * size + 16)
    pygame.draw.rect(screen, INK, box)
    pygame.draw.rect(screen, EDGE, box, 3)
    write(screen, text, (box.x + 12, box.y + 8), color, size)


def frame_(screen, name_):
    """What both screens share: dark backdrop, scanlines, the name, the game and the panel."""
    w, h = screen.get_size()
    screen.fill(INK)
    write(screen, "RETRO TRANSLATOR", (w // 2, 20), YELLOW, 4, "center")
    write(screen, title(name_)[:52], (w // 2, 92), SILVER, 2, "center")
    panel = pygame.Rect(24, 136, w - 48, h - 200)
    pygame.draw.rect(screen, PANEL, panel)
    pygame.draw.rect(screen, EDGE, panel, 4)
    pygame.draw.rect(screen, INK, panel.inflate(-12, -12), 2)
    return panel


def scanlines(screen):
    if "lines" not in _RENDERED:
        lines = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        for y in range(0, screen.get_height(), 3):
            pygame.draw.line(lines, (0, 0, 0, 60), (0, y), (screen.get_width(), y))
        _RENDERED["lines"] = lines
    screen.blit(_RENDERED["lines"], (0, 0))


def home(screen, rom=None, language=None):
    """The first screen: the game, the language and the folder for the translated game, then start. Arrows or
    mouse; Enter (or a click) on the game or the folder opens the system's own dialog. The last choices come back;
    the screen speaks the language chosen on it."""
    last = settings()
    rom = rom or (last.get("rom") if last.get("rom") and os.path.exists(last["rom"]) else None)
    codes = [c for c, _ in LANGUAGES]
    k_lang = codes.index(language or last.get("language", "pt")) if (language or last.get("language", "pt")) in codes \
        else 0
    folder = last.get("folder") or default_folder()
    row, clock, rows = (3 if rom else 0), pygame.time.Clock(), []
    new_build = {}  # filled in the background when a newer version is published
    threading.Thread(target=updater.check_update, args=(new_build,), daemon=True).start()
    auto_tried, pointer = False, None
    while True:
        if new_build and not auto_tried:  # updates by itself, like any program: no click; failed, the button stays
            auto_tried = True  # for another try and the program goes on as it is
            update(screen, new_build, TEXT[codes[k_lang]])
        t = TEXT[codes[k_lang]]
        panel = frame_(screen, os.path.splitext(os.path.basename(rom))[0] if rom else "")
        values = [title(os.path.splitext(os.path.basename(rom))[0]) if rom else t["no_game"],
                  "◀ " + LANGUAGES[k_lang][1] + " ▶", folder, None]
        labels = [t["game"], t["to"], t["folder"], t["start"]]
        slot, rows = (panel.h - 40) // 4, []
        for k in range(4):
            y = panel.y + 20 + slot * k
            box = pygame.Rect(panel.x + 20, y, panel.w - 40, slot - 12)
            rows.append(box)
            on = k == row
            if k == 3:  # the start button
                ready = rom is not None
                pygame.draw.rect(screen, (YELLOW if on else EDGE) if ready else (34, 38, 82), box.inflate(-200, -8))
                write(screen, labels[k], box.center[:1] + (box.centery - 24,), INK if on and ready else
                      (WHITE if ready else DIM), 3, "center")
                continue
            if on:
                pygame.draw.rect(screen, INK, box)
                if pygame.time.get_ticks() // 400 % 2 == 0:
                    write(screen, "▶", (box.x + 12, box.y + 14), YELLOW)
            write(screen, labels[k], (box.x + 48, box.y + 6), SILVER if on else DIM)
            v = values[k]
            limit = (box.w - 72) // 24
            if len(v) > limit:  # a long path keeps its end, where the folder's name is
                v = "…" + v[-(limit - 1):]
            write(screen, v, (box.x + 48, box.y + 42), YELLOW if on else WHITE if (k or rom) else DIM, 3)
        if new_build:  # a newer version: a button where the key hints were
            box = pygame.Rect(screen.get_width() // 2 - 330, screen.get_height() - 58, 660, 48)
            rows.append(box)
            pygame.draw.rect(screen, YELLOW if row == 4 else GREEN, box)
            write(screen, t["update"].format(new_build["version"]), box.center[:1] + (box.y + 8,), INK, 2, "center")
        else:
            hint = t["keys_home"] if row != 1 else t["keys_lang"]
            write(screen, hint, (screen.get_width() // 2, screen.get_height() - 48), DIM, 2, "center")
        scanlines(screen)
        pygame.display.flip()
        clock.tick(30)
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE):
                sys.exit()
            act = None
            if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_UP, pygame.K_DOWN):
                row = (row + (1 if ev.key == pygame.K_DOWN else -1)) % len(rows)
            elif ev.type == pygame.KEYDOWN and ev.key in (pygame.K_LEFT, pygame.K_RIGHT) and row == 1:
                k_lang = (k_lang + (1 if ev.key == pygame.K_RIGHT else -1)) % len(LANGUAGES)
            elif ev.type == pygame.MOUSEMOTION:  # only a pointer that moves: the window opening under it does not
                # take the selection off the button
                if pointer is not None and ev.pos != pointer:
                    row = next((k for k, r in enumerate(rows) if r.collidepoint(ev.pos)), row)
                pointer = ev.pos
            elif ev.type == pygame.KEYDOWN and ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                act = row
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                act = next((k for k, r in enumerate(rows) if r.collidepoint(ev.pos)), None)
            if act == 0:
                rom = pick_rom() or rom
                row = 3 if rom else 0
            elif act == 1:
                k_lang = (k_lang + 1) % len(LANGUAGES)
            elif act == 2:
                folder = pick_folder(t["folder"]) or folder
            elif act == 4 and new_build:
                if not update(screen, new_build, t):
                    row = 3  # the download did not finish: the program goes on as it is
            elif act == 3 and rom:
                settings(rom=rom, language=codes[k_lang], folder=folder)
                return rom, codes[k_lang], folder


def draw_progress(screen, name_, language, work, seconds):
    """One frame of the preparing screen: every step with its state and a block bar for the current one."""
    t = TEXT[language]
    panel = frame_(screen, name_)
    write(screen, t["title"], (panel.centerx, panel.y + 18), WHITE, 2, "center")
    steps = STEPS[:1] if work["japanese"] else STEPS  # Japanese: translated while playing, nothing to rewrite
    phases = [p for _, ps in steps for p in ps]
    now_p = phases.index(work["phase"]) if work["phase"] in phases else len(phases)
    now = next((k for k, (_, ps) in enumerate(steps) if work["phase"] in ps), len(steps))
    blink = int(seconds * 2.5) % 2 == 0
    view = pygame.Rect(panel.x + 24, panel.y + 64, 320, 224)  # the game the program is playing by itself, live
    pygame.draw.rect(screen, INK, view.inflate(16, 16))
    pygame.draw.rect(screen, EDGE, view.inflate(16, 16), 4)
    if progress.frame is not None:
        screen.blit(pygame.surfarray.make_surface(progress.frame.swapaxes(0, 1)), view)
    elif blink:
        write(screen, "...", view.center, DIM, 2, "center")
    x = view.right + 32
    slot = min(64, view.h // len(steps))
    top = view.y + (view.h - slot * len(steps)) // 2  # the steps sit in the middle of the game view's height
    for k, (name_s, _) in enumerate(steps):
        y = top + slot * k + (slot - 48) // 2
        if k < now:
            write(screen, "✓", (x, y), GREEN, 3)
        elif k == now and blink:
            write(screen, "▶", (x, y), YELLOW, 3)
        elif k > now:
            write(screen, "·", (x, y), DIM, 3)
        write(screen, t[name_s], (x + 40, y + 8), SILVER if k < now else YELLOW if k == now else DIM)
    if now_p < len(phases):  # what is happening right now, in a sentence
        write(screen, t["why_" + phases[now_p]], (panel.centerx, view.bottom + 26), SILVER, 2, "center")
    elif work.get("saved"):
        line = f"{t['saved']}: {work['saved']}"
        if len(line) > 56:  # a long path keeps its end: the folder and the file
            line = f"{t['saved']}: …" + work["saved"][-(53 - len(t["saved"])):]
        write(screen, line, (panel.centerx, view.bottom + 26), GREEN, 2, "center")
    else:
        write(screen, t["screen_only"], (panel.centerx, view.bottom + 26), SILVER, 2, "center")
    bar = pygame.Rect(panel.x + 24, panel.bottom - 64, panel.w - 48, 40)
    if now < len(steps):
        write(screen, t["step"].format(now + 1, len(steps)), (bar.x, bar.y - 40), WHITE)
    else:
        write(screen, t["ready"], (bar.x, bar.y - 40), GREEN)
    pygame.draw.rect(screen, INK, bar)
    cells, gap = 24, 4
    cw = (bar.w - 8 - gap * (cells - 1)) / cells
    if now_p >= len(phases):
        f = 1.0
    else:  # the whole preparation: the phases done, plus the share of the current one
        part = progress.fraction()
        if part is None:  # a phase that cannot count: its expected time, never quite reaching its end
            import math
            part = 1 - math.exp(-(time.time() - work.get("since", time.time())) / EXPECTED[phases[now_p]])
        total = sum(WEIGHT[p] for p in phases)
        f = (sum(WEIGHT[p] for p in phases[:now_p]) + WEIGHT[phases[now_p]] * min(part, 0.99)) / total
        f = work["shown"] = max(f, work.get("shown", 0))  # the bar never goes back
    lit = set(range(int(f * cells + 1e-9)))
    write(screen, f"{int(f * 100)}%", (bar.right, bar.y - 40), WHITE, 2, "right")
    for c in range(cells):
        pygame.draw.rect(screen, (GREEN if f == 1.0 else YELLOW) if c in lit else (34, 38, 82),
                         (int(bar.x + 4 + c * (cw + gap)), bar.y + 4, int(cw), bar.h - 8))
    write(screen, f"{t['first']}   {int(seconds) // 60}:{int(seconds) % 60:02d}",
          (screen.get_width() // 2, screen.get_height() - 48), DIM, 2, "center")
    scanlines(screen)


def preparing(screen, name_, language, rom, folder=None):
    """Runs prepare() in a thread and shows its steps; nothing is shown when everything was already done."""
    work = {"phase": "play", "japanese": False, "result": None, "error": None, "saved": None}
    thread = threading.Thread(target=prepare, args=(rom, name_, language, work, folder), daemon=True)
    thread.start()
    thread.join(0.3)
    clock, t0 = pygame.time.Clock(), pygame.time.get_ticks()
    shown = thread.is_alive()
    while thread.is_alive():
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE):
                pygame.quit()
                os._exit(0)  # the work thread may be inside the emulator
        draw_progress(screen, name_, language, work, (pygame.time.get_ticks() - t0) / 1000)
        pygame.display.flip()
        clock.tick(30)
    if work["error"]:
        raise work["error"]
    if work.get("unreadable"):
        refuse(screen, name_, language)
        return None
    if shown:  # every step ticked: a moment to see it finished and where the translated game went
        for _ in range(90 if folder else 30):
            pygame.event.pump()
            draw_progress(screen, name_, language, work, (pygame.time.get_ticks() - t0) / 1000)
            pygame.display.flip()
            clock.tick(30)
    return work["result"]


def refuse(screen, name_, language):
    """The game cannot be read reliably: said plainly, and back to choosing a game."""
    t, clock = TEXT[language], pygame.time.Clock()
    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit()
                os._exit(0)
            if (ev.type == pygame.KEYDOWN and ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE)) or \
                    (ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1):
                return
        panel = frame_(screen, name_)
        write(screen, "!", (panel.centerx, panel.y + 40), YELLOW, 6, "center")
        write(screen, t["unreadable"], (panel.centerx, panel.y + 200), WHITE, 2, "center")
        write(screen, t["unreadable2"], (panel.centerx, panel.y + 250), SILVER, 2, "center")
        write(screen, t["another"], (panel.centerx, panel.bottom - 70), YELLOW, 2, "center")
        scanlines(screen)
        pygame.display.flip()
        clock.tick(30)


def main(rom=None, language=None, test=0):
    rom = os.path.abspath(rom) if rom else None
    os.makedirs(preparation.FOLDER, exist_ok=True)
    updater.remove_old_build()
    clear_if_changed()
    os.chdir(preparation.FOLDER)  # collections and translations kept in the user's folder (the program may be in a read-only folder)
    pygame.init()
    screen = pygame.display.set_mode((320 * SCALE, 224 * SCALE))
    pygame.display.set_caption("Retro Translator")
    folder, result = None, None
    while result is None:  # a game that cannot be read sends the player back to choose another
        if not test:
            rom, language, folder = home(screen, rom, language)
        name_ = os.path.splitext(os.path.basename(rom))[0]
        pygame.display.set_caption(f"Retro Translator - {title(name_)}")
        result = preparing(screen, name_, language, rom, folder)
        if result is None and test:
            return
    table, translated = result
    font_ = overlay.Font({} if overlay.translation.SOURCE in ("ja", "zh") else table)  # Japanese: Latin letters
    # of the library (the Latin table of a kana font is kana read as letters)
    trans = overlay.Overlay(language, os.path.join(preparation.FOLDER, f"{name_}.{language}.json"))
    japanese = overlay.translation.SOURCE in ("ja", "zh")
    reader = cjk.Reader(overlay.translation.SOURCE, preparation.CJK["map"], bytes(consoles.for_rom(rom).read_rom(rom))) if japanese else None
    memory = translated != rom and os.path.exists(translated + ".memory")  # the game verifies its ROM on power-up
    md = consoles.for_rom(rom).Emulator(rom if memory else translated)
    if memory:
        original_bytes, translated_bytes = bytes(consoles.for_rom(rom).read_rom(rom)), open(translated, "rb").read()
    accents = {}
    if os.path.exists(translated + ".accents.json"):
        accents = json.load(open(translated + ".accents.json", encoding="utf-8"))
    with_accent = []
    rate, fps = md.audio_rate()
    if not test:
        pygame.mixer.init(int(rate), -16, 2, 1024)
        channel = pygame.mixer.Channel(0)
        md.sound = bytearray()
    clock, buttons, rnd = pygame.time.Clock(), set(), random.Random(1)
    last, stable, patches, on, working, built = None, 0, [], True, [None], False
    toast = -10 ** 6  # when F1 was pressed: its notice stays on screen for a moment
    tl = TEXT.get(language, TEXT["en"])
    frame_n = 0
    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE):
                pygame.quit()
                return
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_F1:
                on, toast = not on, pygame.time.get_ticks()
            if ev.type in (pygame.KEYDOWN, pygame.KEYUP) and ev.key in KEYS:
                (buttons.add if ev.type == pygame.KEYDOWN else buttons.discard)(KEYS[ev.key])
        if test and frame_n % 20 == 0:  # test mode: plays by itself like the collection
            b = rnd.choice(["A", "B", "START", "A", "B", "UP", "DOWN", "LEFT", "RIGHT", None, None])
            buttons = {b} if b else set()
        md.run_frames(1, buttons)
        frame_n += 1
        if memory and frame_n == rom_text.AFTER_GAME:
            md.write_rom(translated_bytes, original_bytes)
        if frame_n % 15 == 0 and on:
            if japanese:
                if reader.learn():  # new characters placed: kept for the next time
                    value_ = json.load(open(os.path.join(preparation.FOLDER, f"{name_}.font.json"), encoding="utf-8"))
                    value_["cjk"] = {g.hex(): c for g, c in reader.map_.items()}
                    json.dump(value_, open(os.path.join(preparation.FOLDER, f"{name_}.font.json"), "w", encoding="utf-8"))
                    last = None
                list_ = cjk.blocks(md, reader)
                texts = tuple(b["text"] for b in list_)
            else:
                with_accent = overlay.add_accents(md, table, font_, accents)
                list_ = overlay.blocks(md, table)
                texts = tuple(t for b in list_ for _, t, _ in b["lines"])
            if texts != last:  # text changed: drop the old translation and wait for it to settle
                last, stable, patches, built = texts, 0, [], False
            else:
                stable += 1
            if stable >= 2 and list_ and not built:  # ~0.5 s still: text being typed out is skipped
                missing_ = trans.missing_(list(texts) if japanese else overlay.requests(list_))
                if not missing_ and japanese:
                    patches, built = cjk.patches(md, list_, trans, font_), True
                elif not missing_:
                    sound, md.sound = md.sound, None  # the extra frame for the clean background is not played
                    patches, built = overlay.patches(md, table, trans, font_, list_), True
                    md.sound = sound
                elif working[0] is None or not working[0].is_alive():  # translates without making the game wait
                    working[0] = threading.Thread(target=trans.translate_many, args=(missing_,), daemon=True)
                    working[0].start()
                    if test:  # in the test the game runs unthrottled: wait for the translation as if it were live
                        working[0].join()
        img = md.frame.copy()
        if on:
            for y0, y1, x0, x1, px in patches + with_accent:
                img[y0:y1, x0:x1] = px
        sup = pygame.surfarray.make_surface(img.swapaxes(0, 1))
        screen.blit(pygame.transform.scale(sup, screen.get_size()), (0, 0))
        if pygame.time.get_ticks() - toast < 1500:
            notice(screen, tl["on"] if on else tl["off"], GREEN if on else SILVER)
        elif on and working[0] is not None and working[0].is_alive() and pygame.time.get_ticks() // 300 % 2:
            notice(screen, tl["working"], YELLOW, small=True)
        pygame.display.flip()
        if not test:
            if md.sound and channel.get_queue() is None:
                channel.queue(pygame.mixer.Sound(buffer=bytes(md.sound)))
                md.sound = bytearray()
            clock.tick(fps)
        elif frame_n % 600 == 0:
            os.makedirs("output", exist_ok=True)
            pygame.image.save(screen, os.path.join("output", f"play_{name_}_{frame_n // 600:02d}.png"))
            if frame_n >= test:
                pygame.quit()
                return
