# Retro Translator

Play retro console games translated into your language, on any Windows PC. Offline, on the CPU, nothing to install.

Website: <https://leofeitosa.github.io/retro-translator/>

Retro Translator runs the game in its own emulator, learns the game's font by itself, finds the game's text in the ROM
and translates it, so the game draws the translation with its own font, colours and animations. No ROM is included:
you use your own.

## Consoles

| Console | Files | Status |
| --- | --- | --- |
| Mega Drive / Genesis | `.bin` `.md` `.gen` `.smd` | Supported |

New consoles plug in as isolated modules: see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#adding-a-console).

## Download and play (Windows 10/11)

1. Open [Releases](https://github.com/LeoFeitosa/retro-translator/releases/latest) and download `retro-translator.exe`.
2. Open it, pick a game, the language to translate into and the folder for the translated copy.

The exe is portable. The first time a game is opened, Retro Translator plays it by itself for a few minutes to learn
it; after that the game opens translated right away, and a translated copy of the same file type is saved for any
emulator. When a new version is published, the home screen offers it and updates in one click.

| Key | Button |
| --- | --- |
| Arrows | D-pad |
| Z / X / C | A / B / C |
| Enter | Start |
| F1 | Translation on/off |
| Esc | Quit |

## Languages

- Games in English, French, Spanish or Japanese (detected by itself).
- Translated into Portuguese (Brazil), Portuguese (Portugal), Spanish, English or French.

## How it works

- **Reading the font.** Latin text is treated as a substitution cipher: the glyphs on screen are matched to letters
  with a word-frequency dictionary and the order the font is stored in. A letter is used only when real words prove
  it; a game whose letters cannot be proven is not translated, and the program says so.
- **Translating inside the ROM.** Text found in the ROM is translated with rule-based machine translation
  ([Apertium](https://apertium.org)) and written back in place, fitted to the original space. Only whole messages are
  written. Japanese and Chinese are translated by an offline neural model.
- **Staying safe.** Before using a translated ROM, Retro Translator runs it next to the original and leaves out
  changes that would stop the game.
- **Everything else.** Text that cannot be found in the ROM is drawn over the screen while you play.

## Limitations

- Machine translation: most sentences read well, some come out literal or wrong.
- Graphic text (logos, title art) and games whose capital letters never appear on screen are translated only in part
  or not at all.
- Japanese: a kanji read wrong can change the meaning of a sentence.

## From source

```sh
python -m venv .venv
.venv/bin/pip install -e ".[japanese]"
python -m retro_translator [GAME] [pt|pt-PT|es|en|fr]
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the data the program needs outside git, the checks to run and the code
style, and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for how the code is organized.

## License

Retro Translator is free for **noncommercial** use under the
[PolyForm Noncommercial License 1.0.0](LICENSE.md): you may use, study, change and share it for personal, hobby,
study, research and other noncommercial purposes. Selling it, or using it in a commercial product or service, is not
allowed. Copyright LeoFeitosa.

The program bundles third-party software, each under its own license: see [THIRD_PARTY.md](THIRD_PARTY.md). The
sources those licenses require are attached to every release.
