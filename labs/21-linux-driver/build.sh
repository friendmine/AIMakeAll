#!/bin/sh
set -eu
root=$(pwd)
base=build/linux-qemu
src=$base/source
out=$base/out
stock=${QEMU_SOURCE:-build/qemu-course/qemu-9.2.4}
if [ ! -f "$src/VERSION" ]; then
    mkdir -p "$base"
    cp -R "$stock" "$src"
fi
test "$(cat "$src/VERSION")" = "9.2.4"
if ! cmp -s labs/21-linux-driver/aim-pcie.c "$src/hw/misc/aim-pcie.c"; then
    cp labs/21-linux-driver/aim-pcie.c "$src/hw/misc/aim-pcie.c"
fi
if ! grep -q aim-pcie.c "$src/hw/misc/meson.build"; then
    echo "system_ss.add(when: 'CONFIG_EDU', if_true: files('aim-pcie.c'))" >> "$src/hw/misc/meson.build"
fi
mkdir -p "$out"
if [ ! -f "$out/build.ninja" ]; then
    (cd "$out" && "$root/$src/configure" --target-list=x86_64-softmmu --without-default-features --enable-tcg --disable-werror --disable-download)
fi
ninja -C "$out" -j6 qemu-system-x86_64
