"""Read-only local EDA inventory; never installs tools or runs design flows."""

import argparse
from datetime import datetime
import glob
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys


# Explicit variants prevent PATH from silently merging incompatible environments.
PROBES = [
    ("python", "baseline", "python3", ["--version"]),
    ("clang", "baseline", "clang", ["--version"]),
    ("make", "baseline", "make", ["--version"]),
    ("iverilog", "rtl", "iverilog", ["-V"]),
    ("verilator-base", "rtl", "verilator", ["--version"]),
    ("verilator-uvm", "uvm", "{lab}/tools/uvm-env/verilator/bin/verilator", ["--version"]),
    ("verible", "verification", "{lab}/tools/verible/bin/verible-verilog-lint", ["--version"]),
    ("yosys-path", "rtl", "yosys", ["-V"]),
    ("yosys-pinned", "verification", "/nix/store/*-yosys-with-plugins-0.62-python3-*-env/bin/yosys", ["-V"]),
    ("sby", "verification", "/nix/store/*-yosys-with-plugins-0.62-python3-*-env/bin/sby", ["--version"]),
    ("eqy", "verification", "/nix/store/*-yosys-with-plugins-0.62-python3-*-env/bin/eqy", ["--version"]),
    ("z3", "verification", "z3", ["--version"]),
    ("surfer", "viewer", "surfer", ["--version"]),
    ("riscv-gcc", "firmware", "riscv64-unknown-elf-gcc", ["--version"]),
    ("nix", "physical", "/nix/var/nix/profiles/default/bin/nix", ["--version"]),
    ("librelane", "physical", "{lab}/toolchain/bin/librelane", ["--version"]),
    ("openroad", "physical", "/nix/store/*-openroad-2026-02-17/bin/openroad", ["-version"]),
    ("opensta", "physical", "/nix/store/*-opensta/bin/sta", ["-version"]),
    ("magic-base", "physical", "/nix/store/*-magic-vlsi-8.3.623/bin/magic", ["--version"]),
    ("magic-rc", "sram", "{lab}/tools/magic-rc/bin/magic", ["--version"]),
    ("netgen", "physical", "/nix/store/*-netgen-1.5.316/bin/netgen", None),
    ("klayout", "viewer", "/nix/store/*-klayout-0.30.7/bin/klayout", None),
    ("ngspice", "analog", "ngspice", ["--version"]),
    ("xschem", "analog", "{lab}/tools/xschem/bin/xschem", ["--version"]),
    ("qemu-rv32", "simulator", "qemu-system-riscv32", ["--version"]),
    ("qemu-rv64", "simulator", "qemu-system-riscv64", ["--version"]),
]

EVIDENCE = [
    "logs/status.json", "logs/verification-status.json", "logs/analog-status.json",
    "preparation/status.json", "results/uvm_cdc/results.json",
    "results/mixed_signal/results.json", "results/openram_generic/results.json",
    "results/openram_pex/acceptance.json", "results/openram_pex/extraction.json",
]
LOCKS = [
    "tools/librelane-3.0.17/flake.lock",
    "tools/verification-requirements.lock",
    "tools/openram-env/requirements.lock.txt",
    "tools/openram-env/sources/openram.lock.json",
    "tools/openram-env/sources/cells.lock.json",
    "tools/openram-env/sources/pdk.lock.json",
    "tools/uvm-env/sources/sources.lock.json",
    "preparation/sources/downloads.lock.json",
    "preparation/ip/picorv32/SOURCE.json",
    "tools/uvm-env/macos-dpi.patch",
    "tools/openram-env/ngspice-runtime.patch",
    "verification-env.sh", "uvm-env.sh", "openram-env.sh",
]


def locate(spec, lab):
    expanded = spec.replace("{lab}", str(lab))
    if "/" not in expanded:
        match = shutil.which(expanded)
        return [match] if match else []
    return sorted(p for p in glob.glob(expanded) if os.path.isfile(p) and os.access(p, os.X_OK))


def execute(command, env):
    try:
        p = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, text=True, errors="replace",
                           timeout=10, env=env)
        return {"status": "version_ok" if p.returncode == 0 else "probe_failed",
                "exit_code": p.returncode, "output": p.stdout.strip()[:1200]}
    except subprocess.TimeoutExpired:
        return {"status": "timeout"}
    except OSError as error:
        return {"status": "probe_failed", "error": str(error)}


def probe(name, category, spec, args, lab):
    paths = locate(spec, lab)
    item = {"name": name, "category": category, "candidates": paths}
    if not paths:
        return dict(item, status="not_found_in_checked_locations")
    if len(paths) > 1:
        return dict(item, status="ambiguous_requires_selection")
    item["path"] = paths[0]
    if args is None:
        return dict(item, status="file_present_not_executed")
    env = dict(os.environ)
    # Match the original uvm-env.sh without sourcing arbitrary external scripts.
    if name == "verilator-uvm":
        env["VERILATOR_ROOT"] = str(lab / "tools/uvm-env/verilator/share/verilator")
        env["VERILATOR_BIN"] = str(lab / "tools/uvm-env/verilator/bin/verilator_bin")
    elif name == "verilator-base":
        env.pop("VERILATOR_ROOT", None)
        env.pop("VERILATOR_BIN", None)
    item.update(execute([paths[0], *args], env))
    return item


def read_record(lab, relative, summary=False):
    path = lab / relative
    if not path.is_file():
        return {"path": relative, "status": "not_found"}
    raw = path.read_bytes()
    item = {"path": relative, "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw), "status": "recorded_not_rerun"}
    if summary:
        try:
            data = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            return dict(item, status="unreadable_json_snapshot")
        keys = ("status", "updated", "date", "scope", "characterization_ready",
                "pdk_revision", "cpu_commit", "run_count", "limitations",
                "checks", "macro_um", "counts", "magic_version", "pdk")
        item["summary"] = {k: data[k] for k in keys if k in data}
        if "gates" in data:
            item["summary"]["gates"] = [{"name": g["name"], "status": g["status"]}
                                         for g in data["gates"]]
    return item


def python_packages(name, interpreter):
    if not interpreter.is_file():
        return {"name": name, "status": "not_found"}
    code = ("import sys,json,importlib.metadata as m; "
            "names=('numpy','scipy','cocotb','pytest','cocotbext-axi','ciel','torch'); "
            "found={d.metadata['Name'].lower():d.version for d in m.distributions()}; "
            "print(json.dumps({'python':sys.version.split()[0], "
            "'packages':{n:found.get(n) for n in names}}))")
    result = execute([str(interpreter), "-c", code], dict(os.environ))
    if result.get("exit_code") == 0:
        result["metadata"] = json.loads(result.pop("output"))
    return dict(result, name=name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asic-lab", type=Path,
                        default=Path(os.environ.get("ASIC_LAB_ROOT", str(Path.home() / "asic-lab"))))
    parser.add_argument("--output", type=Path, help="Optional JSON snapshot; otherwise print JSON")
    options = parser.parse_args()
    # Do not resolve the symlink: some Perl/Tcl EDA launchers break on spaces.
    lab = options.asic_lab.expanduser().absolute()
    report = {
        "schema_version": 1,
        "observed_at": datetime.now().astimezone().isoformat(),
        "scope": "Version/file probes and historical report snapshots; not flow acceptance",
        "host": {"system": platform.system(), "machine": platform.machine(),
                 "macos": platform.mac_ver()[0]},
        "asic_lab": str(lab), "asic_lab_exists": lab.is_dir(),
        "tools": [probe(*entry, lab) for entry in PROBES],
        "python_environments": [
            python_packages("current", Path(sys.executable)),
            python_packages("verification", lab / "tools/verification-env/bin/python"),
            python_packages("openram", lab / "tools/openram-env/venv/bin/python"),
        ],
        "locks_and_environment_files": [read_record(lab, p) for p in LOCKS],
        "historical_evidence": [read_record(lab, p, summary=True) for p in EVIDENCE],
    }
    payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if options.output:
        options.output.parent.mkdir(parents=True, exist_ok=True)
        options.output.write_text(payload)
        for tool in report["tools"]:
            print(f"{tool['name']:20} {tool['status']}")
        print(f"Saved {options.output}; inventory only, no acceptance claim.")
    else:
        print(payload, end="")


if __name__ == "__main__":
    main()
