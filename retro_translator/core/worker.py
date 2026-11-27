"""Work on other processor cores: the program starts itself again with an internal option (as rom_text does for
the screen tests), so it works the same in the executable; the caller polls and never blocks the window."""
import os
import subprocess
import sys
import tempfile
import time

from retro_translator import HERE


def start(*args, env=None):
    """A process running `retro_translator <args>`: its printed answer is read with result()."""
    cmd = [sys.executable, *args] if getattr(sys, "frozen", False) else [sys.executable, "-m", "retro_translator", *args]
    out_ = tempfile.TemporaryFile("w+")  # a file, not a pipe: a full pipe would stop the child while this waits
    p = subprocess.Popen(cmd, stdout=out_, stderr=subprocess.DEVNULL, text=True,
                         env={**os.environ, "PYTHONPATH": os.path.dirname(HERE), **(env or {})})
    return p, out_


def result(job, limit=1800):
    """The last line the process printed, or None when it failed or took too long."""
    p, out_ = job
    t0 = time.time()
    while p.poll() is None:
        if time.time() - t0 > limit:
            p.kill()
            return None
        time.sleep(0.2)
    out_.seek(0)
    lines = out_.read().strip().splitlines()
    out_.close()
    return lines[-1] if p.returncode == 0 and lines else None


def stop(job):
    """The answer is not needed any more."""
    p, out_ = job
    if p.poll() is None:
        p.kill()
        p.wait()
    out_.close()
