import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "labs/10-language-model"))
from train import load
from models.deploy import quantize_rows
from replay import project


def synth(top, library, sta, out):
    paths = [ROOT / "hardware/rtl/mac_int8.sv", ROOT / f"hardware/rtl/{top}.sv"]
    bank = "chparam -set BANKED 1 projection_tile" if top == "projection_tile" else ""
    script = out / "synth.ys"
    script.write_text(f'''read_verilog -sv "{paths[0]}" "{paths[1]}"
{bank}
synth -top {top} -flatten
dfflibmap -liberty "{library}"
abc -liberty "{library}"
stat -liberty "{library}"
write_verilog -noattr -noexpr mapped.v
''')
    with (out / "synth.log").open("w") as log:
        subprocess.run(["yosys", "-s", script], cwd=out, stdout=log, check=True)
    tcl = out / "timing.tcl"
    tcl.write_text(f'''read_liberty "{library}"
read_verilog mapped.v
link_design {top}
create_clock -period 50 -name clk [get_ports clk]
set_input_delay 1.0 -clock clk [all_inputs -no_clocks]
set_output_delay 1.0 -clock clk [all_outputs]
report_checks -path_delay max
report_worst_slack -max
exit
''')
    run = subprocess.run(
        [sta, "-no_init", tcl],
        cwd=out,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=True,
    )
    (out / "timing.log").write_text(run.stdout)
    if re.search(r"^Error:", run.stdout, re.M):
        raise RuntimeError(run.stdout[-1500:])
    area = re.findall(
        r"Chip area for module.*?:\s+([0-9.]+)", (out / "synth.log").read_text()
    )
    slack = re.findall(r"worst slack max\s+([-\d.]+)", run.stdout)
    return dict(cell_area_um2=float(area[-1]), setup_slack_ns=float(slack[-1]))


def main():
    lib = Path(
        os.environ.get(
            "AIM_LIBERTY",
            Path.home()
            / "asic-lab/pdks/sky130A/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib",
        )
    ).resolve()
    sta = (
        os.environ.get("STA")
        or shutil.which("sta")
        or next(Path("/nix/store").glob("*-opensta/bin/sta"), None)
    )
    if not sta or not lib.is_file():
        raise SystemExit(
            "Set STA to OpenSTA and AIM_LIBERTY to the SKY130 HD timing library."
        )
    torch.set_num_threads(1)
    torch.set_grad_enabled(False)
    model = load(48)
    h = model.blocks[0].norm1(
        model.tokens(torch.tensor(list(b"The value")))
        + model.positions(torch.arange(9))
    )
    x, _ = quantize_rows(h)
    w, _ = quantize_rows(model.blocks[0].qkv.weight)
    base = ROOT / "build/array-design"
    base.mkdir(exist_ok=True)
    report = dict(
        liberty_sha256=hashlib.sha256(lib.read_bytes()).hexdigest(),
        clock_ns=50,
        input_output_delay_ns=1,
    )
    for top, tile in [
        ("projection_tile", ROOT / "build/projection/banked/Vprojection_tile"),
        ("projection_stream", base / "stream/Vprojection_stream"),
    ]:
        out = base / top
        out.mkdir(exist_ok=True)
        row = synth(top, lib, sta, out)
        for name, a in [("prefill", x), ("decode", x[:1])]:
            _, row[name] = project(tile, a.tolist(), w.tolist())
            project(
                tile,
                a[:1].tolist(),
                w[:3].tolist(),
                bubbles=True,
                trace=out / "bubble.vcd",
            )
        report[top] = row
    assert (
        report["projection_stream"]["decode"]["cycles"]
        < report["projection_tile"]["decode"]["cycles"]
    )
    (base / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(report)


if __name__ == "__main__":
    main()
