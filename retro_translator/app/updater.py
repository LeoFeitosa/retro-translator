"""In-app update of the Windows executable: finds a newer published release, downloads it next to the running
one, swaps the files (a running file can be renamed, not overwritten) and starts the new one."""
import json
import os
import re
import subprocess
import sys
import urllib.request

from retro_translator import VERSION

LATEST = "https://api.github.com/repos/LeoFeitosa/retro-translator/releases/latest"
ASSET = "retro-translator.exe"


def _version_tuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3])


def check_update(found):
    """In the background: the newest published executable, when it is newer than this one. Offline, or run from the
    source code, nothing happens."""
    if not getattr(sys, "frozen", False):
        return
    try:
        req = urllib.request.Request(LATEST, headers={"User-Agent": "retro-translator",
                                                      "Accept": "application/vnd.github+json"})
        d = json.load(urllib.request.urlopen(req, timeout=10))
        asset = next(a for a in d["assets"] if a["name"] == ASSET)
        if _version_tuple(d["tag_name"]) > _version_tuple(VERSION):
            found.update(version=d["tag_name"].lstrip("v"), url=asset["browser_download_url"], size=asset["size"])
    except Exception:
        pass


def download(info, progress):
    """Downloads the new executable next to this one; progress(bytes done) is called per block and may raise
    KeyboardInterrupt to cancel. Returns its path, or None (nothing is left behind)."""
    new = sys.executable + ".new"
    done = 0
    try:
        resp = urllib.request.urlopen(urllib.request.Request(info["url"], headers={"User-Agent": "retro-translator"}),
                                      timeout=30)
        with open(new, "wb") as f:
            for block in iter(lambda: resp.read(1 << 20), b""):
                f.write(block)
                done += len(block)
                progress(done)
        if os.path.getsize(new) != info["size"]:
            raise IOError("incomplete download")
        return new
    except (Exception, KeyboardInterrupt):
        if os.path.exists(new):
            os.remove(new)
        return None


def install(new):
    """Puts the downloaded executable in this one's place and starts it; this process must end right after."""
    exe = sys.executable
    old = exe + ".old"
    if os.path.exists(old):
        os.remove(old)
    os.replace(exe, old)
    os.replace(new, exe)
    # a fresh unpack: the new process must not reuse this one's folder, removed when this process ends
    subprocess.Popen([exe], env={**os.environ, "PYINSTALLER_RESET_ENVIRONMENT": "1"})


def remove_old_build():
    """The executable an update replaced is deleted the next time (while it ran it could only be renamed)."""
    old = sys.executable + ".old"
    if getattr(sys, "frozen", False) and os.path.exists(old):
        try:
            os.remove(old)
        except OSError:
            pass
    remove_stale_unpacks()


def remove_stale_unpacks():
    """A run that crashed or was killed leaves its unpacked copy (~700 MB, _MEI* in the temporary folder): the ones of
    this program, older than a day, go. One in use cannot be deleted, so a running copy is never touched."""
    import glob
    import shutil
    import time
    here = getattr(sys, "_MEIPASS", None)
    if not here:
        return
    for d in glob.glob(os.path.join(os.path.dirname(here), "_MEI*")):
        if os.path.normcase(d) == os.path.normcase(here) or time.time() - os.path.getmtime(d) < 86400:
            continue
        if os.path.isdir(os.path.join(d, "retro_translator")) or os.path.isdir(os.path.join(d, "apertium")):
            try:  # Windows refuses to rename a folder with a file in use: a copy still open keeps its files
                os.rename(d, d + "-old")
            except OSError:
                continue
            shutil.rmtree(d + "-old", ignore_errors=True)
