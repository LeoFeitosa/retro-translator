"""Mega Drive emulator (Genesis Plus GX via libretro) driven from Python,
with direct reads of video memory (VRAM, VDP registers, CRAM)."""
import ctypes as C
import os
import subprocess

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
CORE = os.path.join(HERE, "lib", "genesis_plus_gx_libretro." + ("dll" if os.name == "nt" else "so"))  # built by
# tools/build_dll.sh (Windows) or from the Genesis Plus GX source with core_patch/ (Linux)

# libretro joypad ids
BUTTON = dict(B=0, Y=1, SELECT=2, START=3, UP=4, DOWN=5, LEFT=6, RIGHT=7, A=8, X=9, L=10, R=11)

ENV_CB = C.CFUNCTYPE(C.c_bool, C.c_uint, C.c_void_p)
VIDEO_CB = C.CFUNCTYPE(None, C.c_void_p, C.c_uint, C.c_uint, C.c_size_t)
AUDIO_CB = C.CFUNCTYPE(None, C.c_int16, C.c_int16)
AUDIO_BATCH_CB = C.CFUNCTYPE(C.c_size_t, C.c_void_p, C.c_size_t)
POLL_CB = C.CFUNCTYPE(None)
STATE_CB = C.CFUNCTYPE(C.c_int16, C.c_uint, C.c_uint, C.c_uint, C.c_uint)


class GameInfo(C.Structure):
    _fields_ = [("path", C.c_char_p), ("data", C.c_void_p), ("size", C.c_size_t), ("meta", C.c_char_p)]


def _symbols(only):
    """Addresses from the local symbol table (vram, reg... are not exported)."""
    tab = {}
    for line in subprocess.run(["nm", only], capture_output=True, text=True, check=True).stdout.splitlines():
        parts = line.split()
        if len(parts) == 3:
            tab[parts[2]] = int(parts[0], 16)
    return tab


class MegaDrive:
    def __init__(self, rom):
        self.lib = C.CDLL(CORE)
        if hasattr(self.lib, "retro_memory_view"):  # our core (gpgx/libretro.c): works on Windows
            f = self.lib.retro_memory_view
            f.restype, f.argtypes = C.c_void_p, [C.c_uint]
            addresses = [f(i) for i in range(4)]
        else:  # core without the function: symbol table (Linux only)
            yes = _symbols(CORE)
            base = C.cast(self.lib.retro_run, C.c_void_p).value - yes["retro_run"]
            addresses = [base + yes[n] for n in ("vram", "reg", "cram", "vsram")]
        self._vram = (C.c_uint8 * 0x10000).from_address(addresses[0])
        self._reg = (C.c_uint8 * 0x20).from_address(addresses[1])
        self._cram = (C.c_uint8 * 0x80).from_address(addresses[2])
        self._vsram = (C.c_uint8 * 0x80).from_address(addresses[3])
        self._f = f if hasattr(self.lib, "retro_memory_view") else None
        self.frame = None
        self.buttons = set()
        self._dir = C.c_char_p(os.path.join(HERE, "system").encode())
        os.makedirs(self._dir.value, exist_ok=True)

        # callbacks must stay alive while the library exists
        self.sound = None  # bytearray while the game is played with sound (app/window.py); None discards
        self._cbs = [ENV_CB(self._env), VIDEO_CB(self._video), AUDIO_CB(lambda l, r: None),
                     AUDIO_BATCH_CB(self._audio), POLL_CB(lambda: None), STATE_CB(self._input)]
        for name_, cb in zip(["retro_set_environment", "retro_set_video_refresh", "retro_set_audio_sample",
                             "retro_set_audio_sample_batch", "retro_set_input_poll", "retro_set_input_state"],
                            self._cbs):
            getattr(self.lib, name_)(cb)
        self.lib.retro_init()

        data = open(rom, "rb").read()
        self._buf = C.create_string_buffer(data, len(data))
        info = GameInfo(rom.encode(), C.cast(self._buf, C.c_void_p), len(data), None)
        self.lib.retro_load_game.restype = C.c_bool
        if not self.lib.retro_load_game(C.byref(info)):
            raise RuntimeError(f"core recusou a ROM: {rom}")

    def _env(self, cmd, data):
        cmd &= 0xFFFF
        if cmd in (9, 31):  # GET_SYSTEM_DIRECTORY / GET_SAVE_DIRECTORY
            C.cast(data, C.POINTER(C.c_char_p))[0] = self._dir.value
            return True
        if cmd == 10:  # SET_PIXEL_FORMAT
            self.format_ = C.cast(data, C.POINTER(C.c_int))[0]
            return True
        return False

    def _video(self, data, w, h, pitch):
        if not data:  # repeated frame
            return
        if getattr(self, "format_", 0) == 2:  # RGB565
            px = np.ctypeslib.as_array(C.cast(data, C.POINTER(C.c_uint16)), (h, pitch // 2))[:, :w]
            r = ((px >> 11) & 31) * 255 // 31
            g = ((px >> 5) & 63) * 255 // 63
            b = (px & 31) * 255 // 31
            self.frame = np.dstack([r, g, b]).astype(np.uint8)
        else:  # XRGB8888
            px = np.ctypeslib.as_array(C.cast(data, C.POINTER(C.c_uint8)), (h, pitch))[:, :w * 4]
            self.frame = px.reshape(h, w, 4)[:, :, 2::-1].copy()

    def _audio(self, data, n):
        if self.sound is not None:
            self.sound += C.string_at(data, n * 4)  # n stereo 16-bit frames
        return n

    def audio_rate(self):
        class Av(C.Structure):
            _fields_ = [("w", C.c_uint), ("h", C.c_uint), ("mw", C.c_uint), ("mh", C.c_uint), ("asp", C.c_float),
                        ("fps", C.c_double), ("rate", C.c_double)]
        av = Av()
        self.lib.retro_get_system_av_info(C.byref(av))
        return av.rate, av.fps

    def _input(self, port, device, index, id_):
        return int(port == 0 and device == 1 and id_ in self.buttons)

    def write_rom(self, new, original):
        """Replaces in the loaded ROM the bytes where `novo` differs from `original` (linear order). For games that
        verify the ROM on power-up: the translation goes in after the check. gpgx stores each word with its bytes
        swapped (little-endian host)."""
        size_ = C.c_uint32.from_address(self._f(5)).value
        rom = (C.c_uint8 * size_).from_address(self._f(4))
        swap = rom[0x100] == original[0x101] and rom[0x100] != original[0x100]  # "ESAG" instead of "SEGA"
        diff = np.flatnonzero(np.frombuffer(new[:size_], np.uint8) != np.frombuffer(original[:size_], np.uint8))
        for i in diff.tolist():
            rom[i ^ 1 if swap else i] = new[i]

    def run_frames(self, frames=1, buttons=()):
        self.buttons = {BUTTON[b] for b in buttons}
        for _ in range(frames):
            self.lib.retro_run()
        self.buttons = set()

    def save(self):
        n = self.lib.retro_serialize_size()
        buf = C.create_string_buffer(n)
        self.lib.retro_serialize(buf, C.c_size_t(n))
        return buf.raw

    def load(self, state):
        self.lib.retro_unserialize(C.create_string_buffer(state, len(state)), C.c_size_t(len(state)))

    # ---- video memory ----
    @property
    def vram(self):
        return np.frombuffer(self._vram, dtype=np.uint8)

    @property
    def reg(self):
        return bytes(self._reg)

    def planes(self):
        """Visible tile grids: {'A'|'B'|'W': matrix (rows, columns) of 16-bit entries}."""
        r, v = self.reg, self.vram
        width = {0: 32, 1: 64, 3: 128}.get(r[16] & 3, 32)
        alt = {0: 32, 1: 64, 3: 128}.get((r[16] >> 4) & 3, 32)
        h40 = r[12] & 1
        bases = {"A": (r[2] & 0x38) << 10, "B": (r[4] & 7) << 13}
        alt = min(alt, 4096 // width)  # the VDP never goes past 4096 cells (Clay Fighter asks for 128x128)
        # direct view of VRAM (clean_background writes to it); copy only if the plane runs past the end of memory
        out = {k: (v[b:b + width * alt * 2] if b + width * alt * 2 <= len(v)
                   else np.take(v, np.arange(b, b + width * alt * 2), mode="wrap")).view("<u2").reshape(alt, width)
               for k, b in bases.items()}
        if (r[17] & 0x1F) or (r[18] & 0x1F):  # window enabled
            wb = (r[3] & (0x3C if h40 else 0x3E)) << 10
            wl = 64 if h40 else 32
            out["W"] = v[wb:wb + wl * 32 * 2].view("<u2").reshape(32, wl)
        return out

    def pattern(self, entry):
        """8x8 tile (colour indices 0-15) of a grid entry, already flipped."""
        n = entry & 0x7FF
        b = self.vram[n * 32:n * 32 + 32].reshape(8, 2, 2)[:, :, ::-1].reshape(8, 4)  # words stored LE
        px = np.empty((8, 8), np.uint8)
        px[:, 0::2], px[:, 1::2] = b >> 4, b & 15
        if entry & 0x800:
            px = px[:, ::-1]
        if entry & 0x1000:
            px = px[::-1]
        return px

    def scroll(self, plane, screen_line):
        """(x offset, y offset) in pixels of plane A or B on a screen line."""
        if plane == "W":
            return 0, 0
        r, i = self.reg, 0 if plane == "A" else 1
        hs = (r[13] & 0x3F) << 10
        mode_ = r[11] & 3
        if mode_ == 2:
            hs += (screen_line & ~7) * 4
        elif mode_ == 3:
            hs += screen_line * 4
        dx = int(self.vram[hs + 2 * i:hs + 2 * i + 2].view("<u2")[0]) & 0x3FF
        dy = int(np.frombuffer(self._vsram, dtype="<u2")[i]) & 0x7FF
        return dx, dy
