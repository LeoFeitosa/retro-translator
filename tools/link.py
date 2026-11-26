import sys; sys.path.insert(0, ".")
from retro_translator import consoles
m = consoles.for_rom(sys.argv[1]).Emulator(sys.argv[1]); v = []
for i in range(400):
    m.run_frames(4, ["START"] if i % 20 == 0 else []); m.run_frames(16)
    if i % 40 == 39: v.append(int(m.frame.mean()))
print(v)
