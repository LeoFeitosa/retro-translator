# Contributing

Thank you for helping. Read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) first: its layout and rules apply to every
change. By contributing you agree that your contribution is licensed under the project's license
([LICENSE.md](LICENSE.md)).

## Setting up

Python 3.10 or newer, from the repository root:

```sh
python -m venv .venv
.venv/bin/pip install -e ".[japanese]"
```

The program also needs, outside git: the emulator core in `retro_translator/consoles/megadrive/lib/`
(see `retro_translator/consoles/megadrive/core_patch/README.md`), the font library in `retro_translator/data/tables/`
and, for Japanese and Chinese, the neural model (`tools/neural.sh`).

## Running

```sh
python -m retro_translator [GAME] [pt|pt-PT|es|en|fr]     the program
python -m retro_translator --test GAME pt                  no window: plays by itself, screens saved to output/
python -m tools.selfcheck                                  quick checks with no ROM
python -m tools.find_text --translate GAME pt              what was written into the ROM and why the rest was not
```

## Code style

- Follow the code around you: same naming, same comment style, same size of functions.
- Comments say *why*, with the game that showed the problem when there is one ("Phantasy Star II: capitals at 0x0B").
- English only. No per-game lists. No new dependency without a measured reason.
- Lint before every commit: `ruff check retro_translator tools` (configured in `pyproject.toml`).

## Checking a change

A change is done when it was seen working, not when it compiles:

1. `python -m tools.selfcheck`.
2. For reading or rewriting changes: run the program on several different games (menus, long dialog, a game whose
   letters cannot be read) and compare the original and translated screens (`python -m tools.check`).
3. For the window: build the executable (`tools/package.sh`) and open it on Windows.

## Commits and pull requests

- One subject per commit, written as what the change does ("Write only whole messages into the ROM").
- A pull request says what changed, why, and how it was checked (games and results).
