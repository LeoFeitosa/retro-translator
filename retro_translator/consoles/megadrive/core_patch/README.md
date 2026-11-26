# Genesis Plus GX core with video memory access

Retro Translator uses Genesis Plus GX (libretro), kept in `gpgx/` (not versioned). Add the contents of
`retro_memory_view.c` to `gpgx/libretro/libretro.c`, right before `void retro_run(void)`. The `retro_` prefix is
required: `libretro/link.T` only exports functions with it. Windows has no symbol table, hence the function.

- Linux: `make -f Makefile.libretro -j4` in a copy, then `mv` the `.so` into `../lib/` (running processes keep the old one).
- Windows: `tools/build_dll.sh` (MinGW).
