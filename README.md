# md-translator

Play Mega Drive / Genesis games translated automatically, on any Windows PC.

md-translator runs the game in its own emulator, learns the game's font by itself, finds the game's text and
translates it while you play. It works offline, runs on the CPU only, and needs no installation. No ROM is included:
you use your own.

## Download and play (Windows 10/11)

1. Open [Releases](../../releases/latest) and download `md-translator.exe`.
2. Open it, pick a ROM (`.bin`, `.md`, `.gen` or `.smd`) and the language to translate into.

Nothing to install or extract: the exe is portable. The first time you open a game, md-translator plays it by itself
for a few minutes to learn its font and text. After that, the game starts translated, and the next time it opens right
away. A new version clears what an older one learned by itself, so updating is just downloading the new exe.

| Key | Button |
| --- | --- |
| Arrows | D-pad |
| Z / X / C | A / B / C |
| Enter | Start |
| F1 | Translation on/off |
| Esc | Quit |

## Languages

- Games in English, French, Spanish or Japanese (detected by itself).
- Translated into Portuguese (Brazil), Portuguese (Portugal) or Spanish.

## How it works

- **Reading the font.** Latin text is treated as a substitution cipher: the glyphs on screen are matched to letters
  with a word-frequency dictionary and the order the font is stored in. Japanese kana are placed exactly by the order
  of the font; kanji are read by shape.
- **Translating inside the ROM.** Text found in the ROM is translated with rule-based machine translation
  ([Apertium](https://apertium.org)) and written back in place, fitted to the original space, so the game draws it with
  its own font, colours and animations. Japanese is translated by an offline neural model on the CPU.
- **Staying safe.** Before using a translated ROM, md-translator runs it next to the original and leaves out changes
  that would stop the game.
- **Everything else.** Text that cannot be found in the ROM is redrawn on top of the screen.

## Limitations

- Most sentences read well; some come out literal or wrong.
- Graphic text (logos, title art) is not translated.
- Japanese: a kanji read wrong can change the meaning of a sentence.

## Licenses

The program bundles third-party software, each under its own license: see [THIRD_PARTY.md](THIRD_PARTY.md). The
sources required by those licenses are attached to every release.
