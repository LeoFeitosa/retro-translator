import re, subprocess, sys, os
BIN = os.path.expanduser("~/apertium-win/bin")
MODES = os.path.expanduser("~/apertium-local/root/usr/share/apertium/modes")
DATA = os.path.expanduser("~/apertium-win/data")  # transfer rules recompiled with the Windows build
def w(p): return subprocess.run(["wslpath", "-w", p], capture_output=True, text=True).stdout.strip()
def pipeline(pairs):
    txt = " ".join(open(f"{MODES}/{pairs}.mode").read().split()).replace("$1", "-g").replace("$2", "")
    steps = []
    for stage in txt.split("|"):
        parts = re.findall(r"'[^']*'|\S+", stage)
        cmd = [f"{BIN}/{parts[0]}.exe"] + [w(p.strip("'").replace("/usr/share/apertium", DATA)) if p.startswith("'") else p for p in parts[1:]]
        steps.append(cmd)
    return steps
def run_frames(text, pairs_):
    value_ = subprocess.run([f"{BIN}/apertium-destxt.exe"], input=text.encode(), capture_output=True).stdout
    for pairs in pairs_:
        for cmd in pipeline(pairs):
            r = subprocess.run(cmd, input=value_, capture_output=True)
            if r.returncode: print("ERROR", cmd[0], r.stderr[:200]); return
            value_ = r.stdout
    print(subprocess.run([f"{BIN}/apertium-retxt.exe"], input=value_, capture_output=True).stdout.decode("utf-8", "replace"))
run_frames(sys.stdin.read(), sys.argv[1:])
