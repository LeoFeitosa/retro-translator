"""How far the current long step is, so the program's screen can show it while the step runs in a thread.
A step that cannot count its work leaves total at 0 and the screen shows it as busy."""
done = total = 0


def expect(steps):
    global done, total
    done, total = 0, steps


def tick():
    global done
    done += 1


frame = None  # the screen of the game the step is playing, shown as it plays


def show(img):
    global frame
    frame = img.copy()


def fraction():
    return min(1.0, done / total) if total else None


lines = []  # the latest texts translated, (original, translation), shown while the translation step runs


def said(original, translated):
    lines.append((original, translated))
    del lines[:-12]
