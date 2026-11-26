#!/bin/bash
# Resumes the bulk evaluation where it stopped (results.jsonl keeps every finished game).
# Safe to run any number of times: if it is already running, it does not start another one.
# ROM folder: $RT_ROMS, or the first line of .roms (not versioned).
cd "$(dirname "$0")/.."  # the repository root
ROMS="${RT_ROMS:-$(head -1 .roms 2>/dev/null)}"
if pgrep -f "^.venv/bin/python -m tools.evaluate [^-]" >/dev/null; then echo "evaluation already running"; else
  setsid nohup .venv/bin/python -m tools.evaluate "$ROMS" >> evaluation.log 2>&1 < /dev/null &
echo "resumed; done: $(wc -l < results.jsonl 2>/dev/null || echo 0)"
fi
if ! pgrep -f "^.venv/bin/python -m tools.evaluate --collect" >/dev/null; then
  setsid nohup .venv/bin/python -m tools.evaluate --collect "$ROMS" >> collection.log 2>&1 < /dev/null &
fi
# translation training material (development): same model as the evaluation, no model swap on the GPU
if ! pgrep -f "^.venv/bin/python -m tools.learn_translation" >/dev/null; then
  setsid nohup .venv/bin/python -m tools.learn_translation pt >> translation.log 2>&1 < /dev/null &
fi
echo "collected: $(ls captures 2>/dev/null | wc -l) | sentences translated: $(.venv/bin/python -c 'import json;print(len(json.load(open("memory/pt.json"))))' 2>/dev/null || echo 0)"
