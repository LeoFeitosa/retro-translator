# Third-party software

The Windows package bundles the following software. Each keeps its own license.

## Genesis Plus GX

Mega Drive emulator core, libretro port, commit `f27655b592ef43f317272d79883bcaa10d3ac8ad` of
<https://github.com/libretro/Genesis-Plus-GX>, with one function added
(read access to the emulated memory).

Copyright (c) 1998-2003 Charles MacDonald, (c) 2007-2026 Eke-Eke, some portions copyright Nicola Salmoria and the MAME
team. Redistributions may not be sold, nor may they be used in a commercial product or activity. The complete source
code of the modified core is attached to every release as `genesis-plus-gx-source.zip`, with its full license in
`LICENSE.txt`.

## Apertium

Machine translation programs (lttoolbox, apertium, apertium-lex-tools; official Windows build from
<https://apertium.projectjj.com/windows/nightly/>) and the language pairs
[apertium-en-es](https://github.com/apertium/apertium-en-es), [apertium-fr-es](https://github.com/apertium/apertium-fr-es) and
[apertium-es-pt](https://github.com/apertium/apertium-es-pt),
compiled for this package. GNU General Public License (version 2 for the language pairs). The source of the language pairs used is attached to every release as `apertium-pairs-source.zip`; the
programs' source is at <https://github.com/apertium>.

## Python and libraries

- Python (PSF License), packaged with PyInstaller (GPL with bootloader exception).
- NumPy (BSD), Pillow (MIT-CMU), pygame (LGPL 2.1, with SDL 2 under the zlib license).
- wordfreq (Apache 2.0); its word frequency data is CC BY-SA 4.0, by Robyn Speer and contributors, built from
  sources listed at <https://github.com/rspeer/wordfreq>.

## Japanese and Chinese

- Kana to kanji conversion data (`kanji/`) from the [Mozc](https://github.com/google/mozc) open-source dictionary
  (BSD 3-Clause), which is based on IPAdic (mecab-ipadic-2.7.0; IPAdic license) and the Okinawa dictionary; their
  license texts are in Mozc's `src/data/dictionary_oss/README.txt`.
- Offline neural translation: [M2M100 418M](https://huggingface.co/facebook/m2m100_418M) (MIT license), converted
  to [CTranslate2](https://github.com/OpenNMT/CTranslate2) (MIT); SentencePiece (Apache 2.0).
- Glyph shapes for reading Japanese and Chinese text: [GNU Unifont](https://unifoundry.com/unifont/) (GPL 2+ with
  font embedding exception, or SIL OFL 1.1).
- Glyph shapes: Shinonome 16-dot font (public domain), from the Electronic Font Open Laboratory.
