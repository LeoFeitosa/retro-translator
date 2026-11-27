"""Optional local AI translation (the player turns it on in the program): a small language model run by llama.cpp,
both downloaded the first time it is used and kept in the user's folder. Nothing to configure: llama.cpp uses the
graphics card when there is one, else the processor. When it is off, missing or fails, the usual translator works."""
import atexit
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import tarfile
import time
import urllib.request
import zipfile

from retro_translator.core import progress

ENABLED = False  # set by the program from the player's choice
MODEL = ("https://huggingface.co/ggml-org/gemma-4-E2B-it-GGUF/resolve/main/gemma-4-E2B-it-Q4_0.gguf",
         2841481184, "8e30dff3ac4c8434c49a7036fa15564bdbb6044e42bf04550bf1a096ad7e6a52")
ENGINE = {  # llama.cpp b12793: the Vulkan build uses any graphics card and falls back to the processor
    "win32": ("https://github.com/ggml-org/llama.cpp/releases/download/b12793/llama-b12793-bin-win-vulkan-x64.zip",
              39194083, "5b9ce0c4f774a03496aabc32318802ca52e6e1aff186cfd87b2c7d1f6f8c5828"),
    "linux": ("https://github.com/ggml-org/llama.cpp/releases/download/b12793/llama-b12793-bin-ubuntu-x64.tar.gz",
              23461829, "163ccab0b39b7bc0dc2018a79720932ca6ed976f6936593f7ccaa017d55f7d89"),
}
NAMES = {"en": "English", "pt": "Brazilian Portuguese", "pt-PT": "European Portuguese", "es": "Spanish",
         "fr": "French", "ja": "Japanese", "zh": "Chinese"}
_server = {}


def folder():
    from retro_translator.core import preparation
    return os.path.join(preparation.FOLDER, "ai")


def _model_path():
    return os.path.join(folder(), os.path.basename(MODEL[0]))


def _server_path():
    for root, _, files in os.walk(os.path.join(folder(), "engine"), followlinks=True):
        for f in files:
            if f in ("llama-server.exe", "llama-server"):
                return os.path.join(root, f)
    return None


def ready():
    return os.path.exists(_model_path()) and _server_path() is not None


def _download(url, size, sha, path):
    """Resumes a partial download; the file is used only when its checksum matches."""
    part = path + ".part"
    have = os.path.getsize(part) if os.path.exists(part) else 0
    req = urllib.request.Request(url, headers={"Range": f"bytes={have}-"} if have else {})
    chunk = 1 << 20
    progress.expect(size // chunk + 1)
    progress.done = have // chunk
    with urllib.request.urlopen(req, timeout=60) as r, open(part, "ab" if have and r.status == 206 else "wb") as f:
        while True:
            data = r.read(chunk)
            if not data:
                break
            f.write(data)
            progress.tick()
    h = hashlib.sha256()
    with open(part, "rb") as f:
        for data in iter(lambda: f.read(chunk), b""):
            h.update(data)
    if h.hexdigest() != sha:
        os.remove(part)  # damaged or changed: the next try starts over
        raise OSError("download does not match its checksum")
    os.replace(part, path)


def install():
    """Downloads what is missing (engine ~40 MB, model ~2.8 GB). Raises OSError when it cannot."""
    os.makedirs(folder(), exist_ok=True)
    if _server_path() is None:
        url, size, sha = ENGINE["win32" if sys.platform == "win32" else "linux"]
        archive = os.path.join(folder(), os.path.basename(url))
        _download(url, size, sha, archive)
        target = os.path.join(folder(), "engine")
        if archive.endswith(".zip"):
            zipfile.ZipFile(archive).extractall(target)
        else:
            tarfile.open(archive).extractall(target, filter="data")
        os.remove(archive)  # only the program files stay
        for root, _, files in os.walk(target):
            for f in files:
                os.chmod(os.path.join(root, f), 0o755)
    if not os.path.exists(_model_path()):
        _download(*MODEL, _model_path())


def _start():
    if _server.get("proc") and _server["proc"].poll() is None:
        return _server["port"]
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    proc = subprocess.Popen([_server_path(), "-m", _model_path(), "--host", "127.0.0.1", "--port", str(port),
                             "-c", "4096", "--no-webui"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            creationflags=0x08000000 if sys.platform == "win32" else 0)  # no console window
    atexit.register(proc.terminate)
    for _ in range(600):  # loading the model takes a while the first time
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2)
            break
        except Exception:
            if proc.poll() is not None:
                raise OSError("the AI engine did not start")
            time.sleep(0.5)
    _server.update(proc=proc, port=port)
    return port


def _ask(port, prompt, tokens):
    body = {"messages": [{"role": "user", "content": prompt}], "temperature": 0, "max_tokens": tokens,
            "chat_template_kwargs": {"enable_thinking": False}}  # the answer itself, no reasoning first
    r = urllib.request.urlopen(urllib.request.Request(
        f"http://127.0.0.1:{port}/v1/chat/completions", json.dumps(body).encode(),
        {"Content-Type": "application/json"}), timeout=600)
    return json.load(r)["choices"][0]["message"]["content"].strip()


def translate(texts, language, source="en"):
    """Each text in `language` (None where it failed). The texts come in screen or ROM order, so they go together as a
    numbered list: the neighbours give the sense a line alone lacks ("DISTRESS" next to "FRIENDLY", "HOSTILE" is a
    signal, not suffering), and one request per group is faster than one per line."""
    port = _start()
    name_s, name_d = NAMES.get(source, source), NAMES.get(language, language)
    # the instructions tested on game text: a small change made the small model worse ("A party come e come")
    head = (f"You are a professional {name_s} ({source}) to {name_d} ({language}) translator. Your goal is to accurately "
            f"convey the meaning and nuances of the original {name_s} text while adhering to {name_d} grammar, "
            "vocabulary, and cultural sensitivities. The text is from a retro video game: keep character and place names "
            f"unchanged, keep it short, and keep the same capitalization style. Produce only the {name_d} translation, "
            "without any additional explanations or commentary. ")
    out_ = [None] * len(texts)
    single = [i for i, t in enumerate(texts) if "\n" in t]  # a text of several lines would break the numbering
    lines = [i for i in range(len(texts)) if i not in single]
    for k in range(0, len(lines), 16):
        part = lines[k:k + 16]
        try:
            answer = _ask(port, head + "The lines are text of the same game screen. Translate each numbered line, keep "
                          "the numbering, one line each:\n\n" + "\n".join(f"{n + 1}. {texts[i]}"
                                                                        for n, i in enumerate(part)),
                          64 + 48 * len(part))
        except Exception:
            single += part
            continue
        got = {int(m.group(1)): m.group(2).strip() for m in re.finditer(r"^\s*(\d+)\.\s*(.*)$", answer, re.M)}
        for n, i in enumerate(part):
            if got.get(n + 1):
                out_[i] = got[n + 1]
            else:
                single.append(i)  # the model skipped or merged it: alone
    for i in single:
        try:
            out_[i] = _ask(port, head + f"Please translate the following {name_s} text into {name_d}:\n\n\n{texts[i]}",
                           256) or None
        except Exception:
            pass
    return out_
