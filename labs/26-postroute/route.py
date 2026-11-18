"""Run the open SKY130HD digital flow on the NPU including its MMIO/DMA controller."""

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / "build/postroute"


def route(variant, default_margin=False):
    out = OUT / variant
    out.mkdir(parents=True, exist_ok=True)
    rtl = ROOT / "hardware/rtl"
    # Set macros in the compilation unit that consumes them, including for lint.
    for name in ("mac_int8", "projection_stream", "projection_mmio"):
        source = (rtl / f"{name}.sv").read_text()
        if name == "projection_mmio":
            defines = "`define AIM_STREAM_SOC\n"
            if variant == "word_dma":
                defines += "`define AIM_WORD_DMA\n"
            source = defines + source
        (out / f"{name}.sv").write_text(source)
    shutil.copyfile(HERE / "timing.sdc", out / "timing.sdc")
    config = dict(
        DESIGN_NAME="projection_mmio",
        PDK="sky130A",
        STD_CELL_LIBRARY="sky130_fd_sc_hd",
        VERILOG_FILES=[
            f"dir::{name}.sv"
            for name in ("mac_int8", "projection_stream", "projection_mmio")
        ],
        CLOCK_PORT="clk",
        CLOCK_PERIOD=50,
        FP_SIZING="absolute",
        DIE_AREA=[0, 0, 650, 650],
        FALLBACK_SDC="dir::timing.sdc",
        PNR_SDC_FILE="dir::timing.sdc",
        SIGNOFF_SDC_FILE="dir::timing.sdc",
    )
    if not default_margin:
        config.update(
            PL_RESIZER_HOLD_SLACK_MARGIN=0.4, GRT_RESIZER_HOLD_SLACK_MARGIN=0.45
        )
    (out / "config.json").write_text(json.dumps(config, indent=2) + "\n")
    pdk = Path(os.environ.get("PDK_ROOT", Path.home() / "asic-lab/pdks"))
    tool = (
        os.environ.get("LIBRELANE")
        or shutil.which("librelane")
        or str(Path.home() / "asic-lab/toolchain/bin/librelane")
    )
    cmd = [
        tool,
        "--manual-pdk",
        "--pdk-root",
        str(pdk),
        "--to",
        "OpenROAD.STAPostPNR",
        str(out / "config.json"),
    ]
    with (out / "console.log").open("w") as log:
        subprocess.run(cmd, cwd=out, stdout=log, stderr=subprocess.STDOUT, check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("variant", choices=("baseline", "word_dma"))
    parser.add_argument(
        "--default-margin",
        action="store_true",
        help="Reproduce the initial reset removal violation",
    )
    args = parser.parse_args()
    route(args.variant, args.default_margin)
