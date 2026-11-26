#!/bin/bash
# Builds the portable Windows executable (a single retro-translator.exe) in the Windows Downloads folder (from WSL).
# Uses the portable Windows Python in ~/retro-win/python (numpy, pillow, pygame, wordfreq, ctranslate2, sentencepiece,
# pyinstaller), the built data in retro_translator/data (tables/, neural/ from tools/neural.sh), each console's core
# in retro_translator/consoles/<console>/lib (tools/build_dll.sh) and Apertium (~/apertium-win/bin + data2,
# tools/build_pairs.sh).
set -e
cd "$(dirname "$0")/.."  # the repository root
PROFILE=$(wslpath "$(cmd.exe /c 'echo %USERPROFILE%' 2>/dev/null | tr -d '\r')")
WIN="$PROFILE/AppData/Local/Temp/retro-translator-build"
FINAL="${RT_OUTPUT:-$PROFILE/Downloads/retro-translator.exe}"
rm -rf "$WIN" && mkdir -p "$WIN/src"
# the package as it is (links followed), without what only runs on Linux or in development
cp -rL retro_translator "$WIN/src/"
find "$WIN/src" \( -name "__pycache__" -o -name "*.so" -o -name "core_patch" \) -prune -exec rm -rf {} +
A="$WIN/src/retro_translator/data/apertium"; mkdir -p "$A/bin" "$A/data"
# only the programs translation.py runs (and every DLL: all of them are needed by those)
for e in lt-proc apertium-tagger apertium-pretransfer apertium-transfer apertium-interchunk apertium-postchunk \
         lrx-proc apertium-destxt apertium-retxt; do cp ~/apertium-win/bin/$e.exe "$A/bin/"; done
cp ~/apertium-win/bin/*.dll "$A/bin/"
# word frequencies only of the languages read or written (wordfreq ships about 40)
WF=~/retro-win/python/Lib/site-packages/wordfreq/data; mkdir -p "$WIN/src/wf"
for l in en fr es pt ja zh; do cp $WF/large_$l.msgpack.gz $WF/small_$l.msgpack.gz "$WIN/src/wf/"; done
cp $WF/_chinese_mapping.msgpack.gz "$WIN/src/wf/"
cp ~/apertium-win/data2/* "$A/data/"
# the translation model (two thirds of the program) travels as a zip after the executable's own files: PyInstaller
# would unpack it on every start; the program unpacks it once (core/translating/neural.py)
( cd "$WIN/src/retro_translator/data" && python3 -c "import shutil; shutil.make_archive('../../../neural', 'zip', '.', 'neural')" )
rm -rf "$WIN/src/retro_translator/data/neural"
cd "$WIN/src"
~/retro-win/python/python.exe -m PyInstaller --noconfirm --onefile --windowed --name retro-translator \
  --distpath ../dist --workpath ../build \
  --paths . --add-data "retro_translator/data;retro_translator/data" --add-data "wf;wordfreq/data" \
  --add-data "retro_translator/consoles;retro_translator/consoles" --collect-submodules retro_translator \
  --collect-all ctranslate2 --collect-all sentencepiece \
  retro_translator/__main__.py > ../pyinstaller.log 2>&1 || { tail -30 ../pyinstaller.log; exit 1; }
cat ../dist/retro-translator.exe ../neural.zip > "$FINAL"
du -sh "$FINAL"
