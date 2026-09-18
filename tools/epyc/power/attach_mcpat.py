#!/usr/bin/env python3

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]

DEFAULT_MCPAT = ROOT / "tools" / "mcpat.py"
DEFAULT_CONFIG = ROOT / "configs" / "power" / "mcpat_epyc7763_compat.cfg"


POWER_RE = re.compile(
    r"^\s*(core|cache|cpu-side|dram|total)\s+"
    r"([0-9]+(?:\.[0-9]+)?)\s+W\b",
    re.MULTILINE,
)


def run_mcpat(results_dir, mcpat_script, config):
    cmd = [
        sys.executable,
        str(mcpat_script),
        "-d", str(results_dir),
        "-t", "total",
        "-c", str(config),
        "-o", "/tmp/epyc_mcpat_bridge.txt",
    ]

    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    if proc.returncode != 0:
        print(proc.stdout, file=sys.stderr)
        raise RuntimeError(
            f"McPAT failed with exit code {proc.returncode}"
        )

    powers = {}

    for name, value in POWER_RE.findall(proc.stdout):
        powers[name] = float(value)

    required = {"core", "cache", "cpu-side"}

    missing = required - powers.keys()

    if missing:
        print(proc.stdout, file=sys.stderr)
        raise RuntimeError(
            "McPAT output missing required fields: "
            + ", ".join(sorted(missing))
        )

    return powers, proc.stdout


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "characterization",
        type=Path,
        help="JSON produced by extract_characterization.py",
    )

    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Output JSON. Defaults to stdout.",
    )

    parser.add_argument(
        "--mcpat-script",
        type=Path,
        default=DEFAULT_MCPAT,
    )

    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
    )

    args = parser.parse_args()

    with args.characterization.open() as f:
        record = json.load(f)

    results_dir = Path(record["source"]["results_dir"])

    if not results_dir.exists():
        raise SystemExit(
            f"Sniper results directory does not exist: {results_dir}"
        )

    powers, console = run_mcpat(
        results_dir,
        args.mcpat_script,
        args.config,
    )

    record["mcpat"] = {
        "core_w": powers["core"],
        "cache_w": powers["cache"],
        "cpu_side_w": powers["cpu-side"],

        # Kept for provenance only. This is NOT part of the
        # calibrated CPU target.
        "legacy_dram_w": powers.get("dram"),

        "legacy_total_w": powers.get("total"),

        "technology_node_nm": 22,

        "status": "REFERENCE_ONLY",

        "calibrated": False,

        "note": (
            "McPAT compatibility/activity-to-power estimate. "
            "22 nm is used because McPAT 1.0 does not support "
            "the EPYC 7763 7 nm process. Legacy Sniper DRAM "
            "power is excluded from cpu_side_w."
        ),
    }

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)

        with args.output.open("w") as f:
            json.dump(record, f, indent=2, sort_keys=True)
            f.write("\n")

        print(f"Wrote {args.output}")
    else:
        json.dump(record, sys.stdout, indent=2, sort_keys=True)
        print()


if __name__ == "__main__":
    main()
