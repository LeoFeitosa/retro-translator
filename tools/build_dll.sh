#!/bin/bash
# Builds gpgx/ for 64-bit Windows (retro_translator/consoles/megadrive/lib/genesis_plus_gx_libretro.dll; gpgx/ is the source tree, not versioned) with Ubuntu's MinGW extracted without sudo
# into ~/mingw (apt-get download gcc-mingw-w64-x86-64-win32 gcc-mingw-w64-base binutils-mingw-w64-x86-64
# mingw-w64-x86-64-dev mingw-w64-common; dpkg -x into ~/mingw/root).
set -e
cd "$(dirname "$0")/.."  # the repository root
export PATH=~/mingw/root/usr/bin:$PATH
B=$(mktemp -d)
cp -r gpgx/core gpgx/libretro gpgx/Makefile.libretro "$B"/
find "$B" -name "*.o" -delete  # objects from the Linux build do not work here
( cd "$B" && nice make -f Makefile.libretro platform=win CC=x86_64-w64-mingw32-gcc-10-win32 \
    CXX=x86_64-w64-mingw32-g++-win32 AR=x86_64-w64-mingw32-ar -j4 > build.log 2>&1 || tail -20 build.log )
L=retro_translator/consoles/megadrive/lib; mkdir -p $L && cp "$B"/genesis_plus_gx_libretro.dll $L/
rm -rf "$B"
ls -la $L/
