#!/bin/sh
# SPDX-License-Identifier: MIT
# Usage: sh simulator/qemu-v0/build.sh /path/to/qemu-9.2.4.tar.xz
set -eu
here=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
root=$(cd "$here/../.." && pwd)
archive=${1:?Pass the official qemu-9.2.4.tar.xz archive}
sha=f3cc1c4eabfdb288218ac3e33763dbe9e276d8bc890b867a2335d58de2ddd39a
python3 - "$sha" "$archive" <<'PY'
import hashlib, sys
with open(sys.argv[2], 'rb') as f:
    h = hashlib.sha256()
    for block in iter(lambda: f.read(1024*1024), b''):
        h.update(block)
if h.hexdigest() != sys.argv[1]:
    sys.exit('Archive SHA-256 mismatch')
PY
base=${BUILD_QEMU_DIR:-"$root/build/qemu-course"}
mkdir -p "$base"
base=$(cd "$base" && pwd)
src="$base/qemu-9.2.4"
if [ ! -f "$src/.aim-course-patched" ]; then
    if [ -e "$src" ]; then
        echo "Existing source directory; use a fresh BUILD_QEMU_DIR" >&2
        exit 1
    fi
    tar -xf "$archive" -C "$base"
    patch -d "$src" -p1 < "$here/virt-9.2.4.patch"
    touch "$src/.aim-course-patched"
fi
cp "$here/aimakeall-npu.c" "$here/aimakeall-npu.h" "$src/hw/riscv/"
mkdir -p "$base/out"
cd "$base/out"
set -- --target-list=riscv32-softmmu --without-default-features --enable-tcg \
       --enable-fdt=system --disable-werror --disable-download
if [ "$(uname -s)" = Darwin ]; then
    dtcprefix=${DTC_PREFIX:-$(brew --prefix dtc)}
    set -- "$@" "--extra-cflags=-I$dtcprefix/include" "--extra-ldflags=-L$dtcprefix/lib"
fi
"$src/configure" "$@"
ninja -j "${JOBS:-4}" qemu-system-riscv32
