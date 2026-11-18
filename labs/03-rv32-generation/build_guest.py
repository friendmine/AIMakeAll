"""Build the RV32IM guest with the course linker script and freestanding C runtime."""

import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent


def build(folder, source=HERE / "generate.c", extra_cflags=()):
    gcc = os.environ.get("RISCV_CC", "riscv64-unknown-elf-gcc")
    objcopy = (
        os.environ.get("RISCV_OBJCOPY")
        or subprocess.check_output([gcc, "-print-prog-name=objcopy"], text=True).strip()
    )
    elf, image = folder / "generation.elf", folder / "generation.bin"
    lab01 = HERE.parent / "01-linear257"
    subprocess.run(
        [
            gcc,
            "-march=rv32im",
            "-mabi=ilp32",
            "-mcmodel=medany",
            "-msmall-data-limit=0",
            "-mno-relax",
            "-ffreestanding",
            "-nostdlib",
            "-ffp-contract=off",
            "-fno-math-errno",
            "-O2",
            "-I",
            folder,
            "-T",
            lab01 / "guest.ld",
            lab01 / "start.S",
            *extra_cflags,
            source,
            "-Wl,--gc-sections,--start-group",
            "-lm",
            "-lc",
            "-lgcc",
            "-lnosys",
            "-Wl,--end-group",
            "-o",
            elf,
        ],
        check=True,
    )
    subprocess.run([objcopy, "-O", "binary", elf, image], check=True)
    return elf, image
