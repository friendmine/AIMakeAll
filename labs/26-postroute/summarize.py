"""Extract measured routing, electrical limits and actual critical paths from both runs."""

import hashlib
import json
from pathlib import Path
import re
from route import OUT, ROOT


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def first_path(report, expected, netlist):
    raw = report.read_text()
    slack = float(re.search(r"([-\d.]+)\s+slack \(", raw)[1])
    assert abs(slack - expected) < 0.0001
    path = {"slack_ns": slack}
    for label, key in (("Startpoint", "start"), ("Endpoint", "end")):
        endpoint = re.search(rf"^{label}: (.+)$", raw, re.M)[1]
        instance = endpoint.split()[0]
        path[key] = endpoint
        # Post-route Verilog maps STA instance names back to logical registers.
        cell = re.search(r"\s" + re.escape(instance) + r"\s*\(([^;]+)\);", netlist)
        q = re.search(r"\.Q\(\s*([^)]*?)\s*\)", cell[1]) if cell else None
        if q:
            path[key + "_q_net"] = q[1].lstrip(chr(92))
    return path


def summarize(variant):
    folder = OUT / variant
    run = sorted((folder / "runs").glob("RUN_*"))[-1]
    (sta,) = run.glob("*-openroad-stapostpnr")
    assert (sta / "state_out.json").is_file()
    resolved = read(run / "resolved.json")
    m = read(run / "final/metrics.json")
    corners = resolved["STA_CORNERS"]
    assert len(corners) == 9
    (netlist_path,) = run.glob("final/nl/*.nl.v")
    netlist = netlist_path.read_text()
    timing = {}
    for part, mode in (("setup", "max"), ("hold", "min")):
        slacks = {
            corner: m[f"timing__{part}__ws__corner:{corner}"] for corner in corners
        }
        worst = min(corners, key=slacks.get)
        timing[part] = dict(
            corners_ns=slacks,
            worst_corner=worst,
            path=first_path(sta / worst / f"{mode}.rpt", slacks[worst], netlist),
        )
    (log,) = run.glob("*-openroad-globalrouting/openroad-globalrouting.log")
    table = log.read_text().split("Final congestion report:")[-1]
    traffic = {}
    for layer, supply, demand, usage, h, v, total in re.findall(
        r"^(li1|met\d+|Total)\s+(\d+)\s+(\d+)\s+([\d.]+)%\s+(\d+)\s*/\s*(\d+)\s*/\s*(\d+)",
        table,
        re.M,
    ):
        traffic[layer] = dict(
            resource=int(supply),
            demand=int(demand),
            usage_percent=float(usage),
            overflow=int(total),
        )
    assert set(traffic) == {"li1", "met1", "met2", "met3", "met4", "met5", "Total"}
    pdk = Path(resolved["PDK_ROOT"]) / resolved["PDK"]
    pdk_info = read(pdk / ".config/nodeinfo.json")
    hashes = {
        p.name: digest(p)
        for p in (
            folder / "timing.sdc",
            folder / "config.json",
            *sorted(folder.glob("*.sv")),
        )
    }
    libs = {
        Path(path).name: digest(Path(path))
        for paths in resolved["LIB"].values()
        for path in paths
    }
    return dict(
        input_hashes=hashes,
        librelane=resolved["meta"]["librelane_version"],
        pdk=pdk_info["commit"],
        liberty_sha256=libs,
        clock_ns=resolved["CLOCK_PERIOD"],
        die_um2=m["design__die__area"],
        stdcell_um2=m["design__instance__area__stdcell"],
        wire_um=m["route__wirelength"],
        congestion=traffic,
        detailed_route_errors=m["route__drc_errors"],
        timing=timing,
        hold_repair_margin_ns={
            k: resolved[k]
            for k in ("PL_RESIZER_HOLD_SLACK_MARGIN", "GRT_RESIZER_HOLD_SLACK_MARGIN")
        },
        electrical_limits_met=m["design__max_cap_violation__count"] == 0
        and m["design__max_slew_violation__count"] == 0,
        max_cap_violations=m["design__max_cap_violation__count"],
        max_slew_violations=m["design__max_slew_violation__count"],
    )


def main():
    # The archived winner keeps this physical experiment reproducible standalone.
    challenge = ROOT / "build/design-challenge/report.json"
    if not challenge.exists():
        challenge = ROOT / "labs/24-design-challenge/verified-run.json"
    winner = read(challenge)["selection"]
    designs = {v: summarize(v) for v in ("baseline", "word_dma")}
    for key in ("pdk", "liberty_sha256", "clock_ns", "die_um2"):
        assert designs["baseline"][key] == designs["word_dma"][key]
    for key in ("timing.sdc", "config.json", "projection_stream.sv", "mac_int8.sv"):
        assert (
            designs["baseline"]["input_hashes"][key]
            == designs["word_dma"]["input_hashes"][key]
        )
    selected_rtl = "word_dma" if winner in ("combined", "word_dma") else "baseline"
    for row in designs.values():
        row["route_and_timing_met"] = (
            row["detailed_route_errors"] == 0
            and row["congestion"]["Total"]["overflow"] == 0
            and all(
                row["timing"][mode]["path"]["slack_ns"] >= 0
                for mode in ("hold", "setup")
            )
        )
    result = dict(
        top="projection_mmio",
        selected_configuration=winner,
        selected_rtl=selected_rtl,
        variants=designs,
    )
    (OUT / "report.json").write_text(json.dumps(result, indent=2) + "\n")
    for name, d in designs.items():
        print(
            name,
            d["stdcell_um2"],
            d["wire_um"],
            d["congestion"]["Total"],
            d["max_cap_violations"],
            d["max_slew_violations"],
        )

    if not all(d["route_and_timing_met"] for d in designs.values()):
        raise SystemExit(
            "Route or timing target missed; see build/postroute/report.json for the measured paths"
        )


if __name__ == "__main__":
    main()
