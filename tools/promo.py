"""Development: promotional videos, one per website language. Everything inside the window is the real program:
the program runs as a person would use it (fresh user folder, language picker, the first-time preparation, the game),
the keys are pressed by a script and every frame the window draws is recorded, with the game's own sound. The
preparation is shown sped up (its own clock shows the real time). Around the window: captions, music between the
scenes and effects. Usage: python -m tools.promo ROM OUT_DIR [languages]"""
import os
import random
import subprocess
import sys
import tempfile
import time
import zlib

import numpy as np
from PIL import Image, ImageDraw, ImageFont

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import pygame  # noqa: E402

from retro_translator import consoles  # noqa: E402
from retro_translator.app import texts  # noqa: E402
from retro_translator.app import window  # noqa: E402
from retro_translator.core import preparation  # noqa: E402

FPS = 60
W, H = 1920, 1080
WIN_W, WIN_H = 1440, 1008  # the 960x672 window at 1.5x
WX, WY = 40, (H - WIN_H) // 2
FONTS = os.environ.get("RT_FONTS", os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts"))
SITE = "leofeitosa.github.io/retro-translator"
SHOWN_FOLDER = "C:\\Games\\Retro Translator"  # the folder on the home screen: a Windows one, not the machine recording
FFMPEG = os.environ.get("RT_FFMPEG", "ffmpeg").split()  # the ffmpeg command, e.g. a "docker run ... ffmpeg-image"
INDIGO, DEEP, YELLOW, SILVER = (22, 25, 59), (13, 15, 41), (242, 194, 48), (221, 227, 232)
# the scenes: the game played by the same scripted input as tools/cjk_screen.py; the player stops to read each box
SCENES = {"A": (990, 1008), "B": (2186, 2200)}
HOLDS = {995: 180, 1000: 240, 1001: 180, 1002: 240, 1003: 180, 1005: 180, 1007: 180,
         2188: 180, 2190: 180, 2191: 180, 2193: 180, 2197: 180, 2198: 180, 2199: 180}
F1_AT = (1000, 110, 190)  # in that step's pause, F1 shows the original and then the translation again
# the boxes each video shows: the ones the current model translates right in that language
KEEP = {"en": {"A": [995, 1000, 1002, 1003], "B": [2199]}, "pt": {"A": [1000], "B": [2197]},
        "pt-PT": {"A": [1000, 1002], "B": [2199]}, "es": {"A": [1000, 1002], "B": [2199]},
        "fr": {"A": [1000, 1003], "B": [2197, 2199]}}
KEY = {"A": pygame.K_c, "B": pygame.K_x, "START": pygame.K_RETURN, "UP": pygame.K_UP, "DOWN": pygame.K_DOWN}

COPY = {  # video language -> captions; "shows" is the language the program translates into in that video
    "en": {"shows": "en", "tag": "Play retro games in your own language",
           "s1": "Open a game and pick your language", "s2": "The first time, it learns the game by itself",
           "s3": "Menus in your language", "s4": "Dialog too", "fast": "Sped up",
           "end1": "Free for Windows", "end2": "Offline. Nothing to install."},
    "pt": {"shows": "pt", "tag": "Jogue games retrô no seu idioma",
           "s1": "Abra o jogo e escolha o idioma", "s2": "Na primeira vez, ele aprende o jogo sozinho",
           "s3": "Menus no seu idioma", "s4": "Diálogos também", "fast": "Acelerado",
           "end1": "Grátis para Windows", "end2": "Sem internet. Sem instalar nada."},
    "pt-PT": {"shows": "pt-PT", "tag": "Jogue jogos retro na sua língua",
              "s1": "Abra o jogo e escolha a língua", "s2": "Da primeira vez, aprende o jogo sozinho",
              "s3": "Menus na sua língua", "s4": "Diálogos também", "fast": "Acelerado",
              "end1": "Gratuito para Windows", "end2": "Sem internet. Sem instalar nada."},
    "es": {"shows": "es", "tag": "Juega juegos retro en tu idioma",
           "s1": "Abre el juego y elige tu idioma", "s2": "La primera vez, aprende el juego solo",
           "s3": "Menús en tu idioma", "s4": "Y los diálogos", "fast": "Acelerado",
           "end1": "Gratis para Windows", "end2": "Sin conexión. Sin instalar nada."},
    "fr": {"shows": "fr", "tag": "Jouez aux jeux rétro dans votre langue",
           "s1": "Ouvrez le jeu et choisissez la langue", "s2": "La première fois, il apprend le jeu seul",
           "s3": "Les menus dans votre langue", "s4": "Les dialogues aussi", "fast": "Accéléré",
           "end1": "Gratuit pour Windows", "end2": "Hors ligne. Rien à installer."},
    "ja": {"shows": "en", "tag": "レトロゲームを、好きな言語で",
           "s1": "ゲームを開いて言語を選ぶ", "s2": "初回は、ゲームを自分で覚えます",
           "s3": "メニューを英語に", "s4": "会話も", "fast": "早送り",
           "end1": "Windows 用・無料", "end2": "オフラインで動き、インストール不要"},
}


def font(name, size):
    return ImageFont.truetype(os.path.join(FONTS, name), size)


class Recorder:
    """Drives window.main like a person and keeps what its window draws: (scene, step, compressed frame, sound)."""

    def __init__(self, lang, folder):
        self.lang, self.folder, self.frames = lang, folder, []
        self.phase, self.n, self.held, self.cur, self.last_shot = None, 0, set(), None, 0.0
        self.script, self.scene, self.step = None, None, None

    def _inputs(self, start, stop):
        """Per frame: (step, buttons, F1 pressed now)."""
        r = random.Random(2)
        for q in range(stop + 1):
            b = r.choice(["A", "B", "START", "START", "DOWN", "UP", None, None])
            for k in range(20):
                yield q, {b} if b and k < 4 else set(), False
            for k in range(HOLDS.get(q, 0) if q >= start else 0):
                yield q, set(), q == F1_AT[0] and k in F1_AT[1:]

    def events(self):
        self.n += 1
        if self.phase == "picker":  # the home screen: up to the language, one step every 0.7 s to the video's
            # language, down to the start button, Enter
            if self.n % 22:
                return []
            target = [c for c, _ in texts.LANGUAGES].index(self.lang)
            if self.moves:
                return [pygame.event.Event(pygame.KEYDOWN, key=self.moves.pop(0))]
            if self.pos != target:
                self.pos = (self.pos + 1) % len(texts.LANGUAGES)
                return [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT)]
            if not self.down:
                self.down = True
                self.moves = [pygame.K_DOWN, pygame.K_DOWN, pygame.K_RETURN]
            return []
        if self.phase != "game":
            return []
        try:
            self.step, buttons, f1 = next(self.script)
        except StopIteration:
            return [pygame.event.Event(pygame.QUIT)]
        out_ = [pygame.event.Event(pygame.KEYDOWN, key=KEY[b]) for b in buttons - self.held]
        out_ += [pygame.event.Event(pygame.KEYUP, key=KEY[b]) for b in self.held - buttons]
        self.held = buttons
        if f1:
            out_.append(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F1))
        return out_

    def flip(self, surface):
        self.cur = None
        if self.phase == "picker" and self.capture_intro:
            self.cur = self._keep("picker", None, surface)
        elif self.phase == "prep":
            time.sleep(1 / 30)  # the preparing screen runs at its own pace; the work thread needs the CPU
            if time.time() - self.last_shot >= 1.0:
                self.last_shot = time.time()
                self.cur = self._keep("prep", None, surface)
        elif self.phase == "game" and self.step is not None and self.step >= SCENES[self.scene][0]:
            self.cur = self._keep(self.scene, self.step, surface)

    def _keep(self, scene, step, surface):
        self.frames.append([scene, step, zlib.compress(pygame.image.tostring(surface, "RGB"), 1), b""])
        return len(self.frames) - 1

    def sound(self, data):
        if self.cur is not None:
            self.frames[self.cur][3] += bytes(data)


def record(rom, lang):
    """Two runs of the program from power-on, as a new user: scene A (with the picker and the first-time
    preparation) and scene B (the program already knows the game: it starts at once)."""
    home = tempfile.mkdtemp()
    preparation.FOLDER = os.path.join(home, ".retro-translator")
    rec = Recorder(lang, preparation.FOLDER)
    real = {"get": pygame.event.get, "flip": pygame.display.flip, "tick": pygame.time.Clock,
            "home": window.home, "check": window.updater.check_update, "preparing": window.preparing, "init": pygame.mixer.init,
            "channel": pygame.mixer.Channel, "sound": pygame.mixer.Sound}

    class Clock:
        def tick(self, *a):
            return 0

    class Channel:
        def __init__(self, *a):
            pass

        def get_queue(self):
            return None

        def queue(self, data):
            rec.sound(data)

    def home(screen, rom_=None, language=None):
        saved = window.settings(folder=window.settings().get("folder") or SHOWN_FOLDER).get("language", "pt")
        rec.phase, rec.n, rec.down = "picker", 0, False
        rec.pos, rec.moves = [c for c, _ in texts.LANGUAGES].index(saved), [pygame.K_UP, pygame.K_UP]
        return real["home"](screen, rom_, language)

    def preparing(*a):
        rec.phase, rec.last_shot = "prep", 0.0
        out_ = real["preparing"](*a)
        rec.phase = "game"
        return out_

    pygame.event.get = lambda *a, **k: rec.events()
    pygame.display.flip = lambda: (real["flip"](), rec.flip(pygame.display.get_surface()))
    pygame.time.Clock = Clock
    window.home, window.preparing = home, preparing
    window.updater.check_update = lambda *a: None  # no new version in the video
    pygame.mixer.init, pygame.mixer.Channel = (lambda *a, **k: None), Channel
    pygame.mixer.Sound = lambda buffer=b"": bytes(buffer)
    try:
        for scene in ("A", "B"):
            rec.scene, rec.capture_intro, rec.step, rec.held = scene, scene == "A", None, set()
            rec.script = rec._inputs(*SCENES[scene])
            window.main(rom, None)
    finally:
        pygame.event.get, pygame.display.flip, pygame.time.Clock = real["get"], real["flip"], real["tick"]
        window.home, window.preparing = real["home"], real["preparing"]
        window.updater.check_update = real["check"]
        pygame.mixer.init, pygame.mixer.Channel, pygame.mixer.Sound = real["init"], real["channel"], real["sound"]
    return rec.frames


RATE = 44100


def _env(n, attack=0.005, release=0.1):
    t = np.arange(n) / RATE
    return np.minimum(1, t / attack) * np.exp(-t / release)


def _fm(freq, seconds, ratio=1.0, index=2.0, release=0.2, attack=0.004):
    """Two-operator FM voice, the sound of the Mega Drive's sound chip."""
    n = int(seconds * RATE)
    t = np.arange(n) / RATE
    env = _env(n, attack, release)
    return np.sin(2 * np.pi * freq * t + index * env * np.sin(2 * np.pi * freq * ratio * t)) * env


def _hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def music(seconds):
    """Original chiptune: A minor, 128 BPM, Am F C G, FM bass, lead and arpeggio over a drum machine."""
    beat = 60 / 128
    out = np.zeros(int((seconds + 2) * RATE))
    rng = np.random.default_rng(7)

    def put(at, sound, gain):
        a = int(at * RATE)
        if a < len(out):
            out[a:a + len(sound)] += gain * sound[:len(out) - a]
    chords = [(45, [57, 60, 64]), (41, [53, 57, 60]), (48, [55, 60, 64]), (43, [55, 59, 62])]
    melody = [[76, None, 74, 72], [72, None, 69, 72], [76, 79, 76, 74], [74, None, 71, 74]]
    bars = int(seconds / (4 * beat)) + 1
    for bar in range(bars):
        root, chord = chords[bar % 4]
        t0 = bar * 4 * beat
        full = bar >= 2  # two bars of intro: arpeggio and kick only
        for k in range(8):  # bass, eighth notes, root and octave
            put(t0 + k * beat / 2, _fm(_hz(root + (12 if k % 2 else 0)), beat / 2, 1, 3.2, 0.12), 0.32 if full else 0.18)
        for k in range(16):  # arpeggio, sixteenths
            put(t0 + k * beat / 4, _fm(_hz(chord[k % 3] + 12), beat / 4, 2, 1.5, 0.05), 0.07)
        if full:
            for k, note in enumerate(melody[bar % 4]):
                if note:
                    put(t0 + k * beat, _fm(_hz(note), beat * 0.95, 1, 1.4, 0.35, 0.02), 0.16)
        for k in range(4):
            if k % 2 == 0:  # kick on 1 and 3
                n = int(0.18 * RATE)
                tt = np.arange(n) / RATE
                put(t0 + k * beat, np.sin(2 * np.pi * np.cumsum(45 + 90 * np.exp(-tt / 0.03)) / RATE)
                    * _env(n, 0.001, 0.09), 0.5)
            elif full:  # snare on 2 and 4
                n = int(0.16 * RATE)
                put(t0 + k * beat, (rng.standard_normal(n) * 0.6 + np.sin(2 * np.pi * 185 * np.arange(n) / RATE))
                    * _env(n, 0.001, 0.05), 0.22)
        if full:
            for k in range(8):  # closed hat
                n = int(0.04 * RATE)
                hat = np.diff(rng.standard_normal(n + 1)) * _env(n, 0.0005, 0.012)
                put(t0 + k * beat / 2, hat, 0.06)
    fade = int(1.5 * RATE)
    end = int(seconds * RATE)
    out = out[:end]
    out[-fade:] *= np.linspace(1, 0, fade)
    return out


def sfx(kind):
    """Short retro effects: blip (a step), coin (the translation appears), sweep (a scene change), key (typing)."""
    if kind == "blip":
        return np.concatenate([_square(988, 0.05), _square(1319, 0.08)]) * 0.18
    if kind == "coin":
        return np.concatenate([_square(1976, 0.06), _square(2637, 0.22, 0.12)]) * 0.14
    if kind == "key":
        return _square(1568, 0.025) * 0.08
    n = int(0.35 * RATE)  # sweep: rising noise burst
    t = np.arange(n) / RATE
    noise = np.random.default_rng(3).standard_normal(n)
    k = np.clip((t / t[-1]) * 40, 1, 40).astype(int)
    smooth = np.array([noise[max(0, i - k[i]):i + 1].mean() for i in range(n)])
    return smooth * np.sin(np.pi * t / t[-1]) * 0.6


def _square(freq, seconds, release=0.04):
    n = int(seconds * RATE)
    t = np.arange(n) / RATE
    return np.sign(np.sin(2 * np.pi * freq * t)) * _env(n, 0.001, release)


def _ease(x):
    return 1 - (1 - min(max(x, 0), 1)) ** 3



def compose(lang, frames, rate, out):
    """The real window at 1.5x on the left, the captions on the right; music only between the game scenes."""
    c = COPY[lang]
    shows = c["shows"]
    ja = lang == "ja"
    face = "NotoSansJP[wght].ttf" if ja else "ChakraPetch-Bold.ttf"
    mid, small, logo = font(face, 44), font("NotoSansJP[wght].ttf" if ja else "Karla[wght].ttf", 30), \
        font("ChakraPetch-Bold.ttf", 120)
    base = Image.new("RGB", (W, H), INDIGO)
    d_ = ImageDraw.Draw(base)
    for y in range(0, H, 4):
        d_.line([(0, y), (W, y)], fill=(19, 22, 53))
    d_.rounded_rectangle([WX - 12, WY - 12, WX + WIN_W + 12, WY + WIN_H + 12], 18, fill=DEEP)
    PX = WX + WIN_W + 44
    cards = {}

    def wrap(text, f, width):
        words, lines = (list(text) if ja else text.split(" ")), [""]
        for w_ in words:
            t = lines[-1] + ("" if ja or not lines[-1] else " ") + w_
            if f.getlength(t) > width and lines[-1]:
                lines.append(w_)
            else:
                lines[-1] = t
        return lines

    def card(step, text, badge, slide):
        key = (step, text, badge, round(slide, 2))
        if key not in cards:
            img = base.copy()
            dr = ImageDraw.Draw(img)
            dx = int((1 - _ease(slide)) * 200)
            y = WY + 30
            dr.ellipse([PX + dx, y, PX + dx + 60, y + 60], fill=YELLOW)
            dr.text((PX + dx + 30, y + 30), str(step), font=mid, fill=INDIGO, anchor="mm")
            y += 96
            for line in wrap(text, mid, W - PX - 30):
                dr.text((PX + dx, y), line, font=mid, fill="white")
                y += 58
            if badge:
                dr.rounded_rectangle([PX, y + 20, PX + small.getlength("▶▶ " + badge) + 32, y + 70], 8, fill=YELLOW)
                dr.text((PX + 16, y + 45), "▶▶ " + badge, font=small, fill=INDIGO, anchor="lm")
            dr.text((PX, WY + WIN_H - 44), SITE.split("/")[0], font=small, fill=(168, 176, 216), anchor="ls")
            dr.text((PX, WY + WIN_H - 8), "/" + SITE.split("/")[1], font=small, fill=(168, 176, 216), anchor="ls")
            cards[key] = img
        return cards[key].copy()

    def window(img, raw):
        im = Image.frombytes("RGB", (960, 672), zlib.decompress(raw))
        img.paste(im.resize((WIN_W, WIN_H), Image.NEAREST), (WX, WY))
        return img

    tmp = out + ".video.mp4"
    ff = subprocess.Popen(FFMPEG + ["-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                                    "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "18",
                                    "-pix_fmt", "yuv420p", tmp], stdin=subprocess.PIPE)
    n_out, events, game_audio, music_on = [0], [], [], []
    last = [None]

    def emit(img, sound=None, game=False):
        if sound:
            events.append((n_out[0], sound))
        music_on.append(not game)
        ff.stdin.write(img.tobytes())
        last[0] = img
        n_out[0] += 1

    order = np.random.default_rng(5).permutation((W // 64 + 1) * (H // 64 + 1))

    def blocks_to(target, n=16):
        a, b = np.array(last[0]), np.array(target)
        cols = W // 64 + 1
        events.append((n_out[0], "sweep"))
        for k in range(1, n + 1):
            img = a.copy()
            for cell in order[:len(order) * k // n]:
                y, x = divmod(int(cell), cols)
                img[y * 64:(y + 1) * 64, x * 64:(x + 1) * 64] = b[y * 64:(y + 1) * 64, x * 64:(x + 1) * 64]
            emit(Image.fromarray(img))

    # 1. intro: a CRT turning on over the program's first screen, then the name and the promise
    first = next(f for f in frames if f[0] == "picker")
    screen = Image.frombytes("RGB", (960, 672), zlib.decompress(first[2])).resize((W, H), Image.NEAREST)
    screen = Image.blend(screen, Image.new("RGB", (W, H), INDIGO), 0.75)
    black = Image.new("RGB", (W, H), (0, 0, 0))
    emit(black, "sweep")
    for k in range(24):
        img = black.copy()
        w_, h_ = max(2, int(W * _ease(k / 10))), max(3, int(H * _ease((k - 10) / 14)))
        box = ((W - w_) // 2, (H - h_) // 2)
        img.paste(Image.new("RGB", (w_, h_), (240, 240, 255)) if k < 10 else
                  screen.crop((box[0], box[1], box[0] + w_, box[1] + h_)), box)
        emit(img)
    for k in range(int(3 * FPS)):
        img = screen.copy()
        dr = ImageDraw.Draw(img)
        a = _ease(k / 24)
        dr.text((W // 2, H // 2 - 70 + int((1 - a) * 60)), "Retro Translator", font=logo,
                fill=tuple(int(255 * a + v * (1 - a)) for v in INDIGO), anchor="mm")
        b_ = _ease((k - 18) / 24)
        if b_ > 0:
            dr.text((W // 2, H // 2 + 60), c["tag"], font=mid,
                    fill=tuple(int(t * b_ + v * (1 - b_)) for t, v in zip(YELLOW, INDIGO)), anchor="mm")
        emit(img, "blip" if k == 18 else None)
    # 2. the program as it is: the picker (30 fps), the preparation (one frame a second, shown 60 times faster)
    keep = KEEP[shows]
    groups = [("picker", 1, c["s1"], None, 2), ("prep", 2, c["s2"], c["fast"], 1)]
    for scene, step, text, badge, repeat in groups:
        part = [f for f in frames if f[0] == scene]
        for i, f in enumerate(part):
            img = window(card(step, text, badge, min(1, i * repeat / 14)), f[2])
            if i == 0:
                blocks_to(img)
            for _ in range(repeat):
                emit(img, "blip" if i == 0 and _ == 0 else None)
    # 3. the game: only the boxes this language shows, with the game's sound and no music
    for scene, step, text in (("A", 3, c["s3"]), ("B", 4, c["s4"])):
        part = [f for f in frames if f[0] == scene and f[1] in keep[scene]]
        for i, f in enumerate(part):
            img = window(card(step, text, None, min(1, i / 14)), f[2])
            if i == 0:
                blocks_to(img)
            game_audio.append((n_out[0], f[3]))
            emit(img, "blip" if i == 0 else None, game=True)
    # 4. the end: name, offer and the address typed out
    end = Image.new("RGB", (W, H), INDIGO)
    blocks_to(end)
    for k in range(int(4.5 * FPS)):
        img = end.copy()
        dr = ImageDraw.Draw(img)
        a = _ease(k / 20)
        dr.text((W // 2, H // 2 - 150 - int((1 - a) * 40)), "Retro Translator", font=logo, fill="white", anchor="mm")
        if k >= 14:
            dr.text((W // 2, H // 2 - 20), c["end1"], font=mid, fill=YELLOW, anchor="mm")
            dr.text((W // 2, H // 2 + 50), c["end2"], font=small, fill=SILVER, anchor="mm")
        typed = min(len(SITE), max(0, (k - 30) // 2))
        dr.text((W // 2, H // 2 + 160), SITE[:typed] + ("_" if k // 15 % 2 else " "), font=mid, fill="white",
                anchor="mm")
        emit(img, "key" if k >= 30 and (k - 30) % 2 == 0 and typed < len(SITE) else ("blip" if k == 14 else None))
    ff.stdin.close()
    ff.wait()
    # sound: music only where the game is not playing (it fades out and back in), the game's own sound in the game
    total = n_out[0] / FPS
    mix = music(total)
    gate = np.repeat(np.array(music_on, float), int(np.ceil(RATE / FPS)))[:len(mix)]
    gate = np.pad(gate, (0, len(mix) - len(gate)), constant_values=1)
    ramp = int(0.4 * RATE)
    gate = np.convolve(gate, np.ones(ramp) / ramp, mode="same")
    mix *= gate
    for f, raw in game_audio:
        if not raw:
            continue
        g = np.frombuffer(raw, np.int16).reshape(-1, 2).astype(np.float32).mean(axis=1) / 32768
        g = np.interp(np.linspace(0, len(g), int(len(g) * RATE / rate), endpoint=False), np.arange(len(g)), g)
        a = int(f / FPS * RATE)
        mix[a:a + len(g)] += g[:len(mix) - a]
    for f, kind in events:
        e = sfx(kind) * (0.5 if not music_on[min(f, len(music_on) - 1)] else 1)
        a = int(f / FPS * RATE)
        mix[a:a + len(e)] += e[:len(mix) - a]
    mix = np.clip(mix / max(1.0, np.abs(mix).max() / 0.95), -1, 1)
    import wave
    with wave.open(out + ".wav", "wb") as w_:
        w_.setnchannels(1)
        w_.setsampwidth(2)
        w_.setframerate(RATE)
        w_.writeframes((mix * 32767).astype(np.int16).tobytes())
    subprocess.run(FFMPEG + ["-y", "-loglevel", "error", "-i", tmp, "-i", out + ".wav", "-c:v", "copy", "-c:a", "aac",
                             "-b:a", "192k", "-shortest", "-movflags", "+faststart", out], check=True)
    os.remove(tmp)
    os.remove(out + ".wav")


def main(rom, out_dir, only=None):
    import pickle
    os.makedirs(out_dir, exist_ok=True)
    rate = consoles.for_rom(rom).Emulator(rom).audio_rate()[0]
    langs = only.split(",") if only else list(COPY)
    for lang in langs:
        shows = COPY[lang]["shows"]
        cache = os.path.join(out_dir, f"program-{shows}.pkl")  # one recording per language the program shows
        if os.path.exists(cache):
            frames = pickle.load(open(cache, "rb"))
        else:
            frames = record(rom, shows)
            pickle.dump(frames, open(cache, "wb"))
        out = os.path.join(out_dir, f"retro-translator-{lang}.mp4")
        compose(lang, frames, rate, out)
        print("written", out, flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:4])
