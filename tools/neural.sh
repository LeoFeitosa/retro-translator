#!/bin/bash
# Development: converts the offline translation model (M2M100 418M, MIT license) to CTranslate2 int8 in retro_translator/data/neural/m2m418.
# Needs a Python with ctranslate2, transformers, sentencepiece and torch (CPU) for the conversion only.
set -e
cd "$(dirname "$0")/.."  # the repository root
PY=${CONVERTER_PY:?set CONVERTER_PY to the converter Python}
"$(dirname "$PY")/ct2-transformers-converter" --model facebook/m2m100_418M --output_dir retro_translator/data/neural/m2m418 \
  --quantization int8 --copy_files sentencepiece.bpe.model --force
