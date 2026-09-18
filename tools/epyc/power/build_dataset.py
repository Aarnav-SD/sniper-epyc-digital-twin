#!/usr/bin/env python3

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]

EXTRACTOR = ROOT / "tools" / "epyc" / "power" / "extract_characterization.py"
ATTACH_MCPAT = ROOT / "tools" / "epyc" / "power" / "attach_mcpat.py"


def run_command(cmd):
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    return proc.returncode, proc.stdout, proc.stderr


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "configs" / "power" / "characterization_v1.json",
    )

    parser.add_argument(
        "--compatibility",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "power-data" / "characterization_v1",
    )

    args = parser.parse_args()

    with args.manifest.open() as f:
        manifest = json.load(f)

    with args.compatibility.open() as f:
        compatibility = json.load(f)

    compat_index = {
        r["run"]: r
        for r in compatibility["runs"]
    }

    args.output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    records_dir = args.output_dir / "records"
    records_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    dataset_records = []
    failures = []

    print("=== BUILD CHARACTERIZATION DATASET ===")
    print("manifest :", args.manifest)
    print("runs     :", len(manifest["runs"]))
    print()

    for i, spec in enumerate(manifest["runs"], 1):
        name = spec["run"]
        workload = spec["workload"]
        active_cores = spec["active_cores"]
        expected_tier = spec["tier"]

        prefix = (
            f"[{i:02d}/{len(manifest['runs']):02d}] "
            f"{name}"
        )

        if name not in compat_index:
            message = "run absent from compatibility inventory"
            print(f"{prefix}: FAIL ({message})")
            failures.append({
                "run": name,
                "stage": "compatibility",
                "error": message,
            })
            continue

        compat = compat_index[name]

        if compat["tier"] != expected_tier:
            message = (
                f"tier mismatch: manifest={expected_tier}, "
                f"classifier={compat['tier']}"
            )

            print(f"{prefix}: FAIL ({message})")

            failures.append({
                "run": name,
                "stage": "compatibility",
                "error": message,
            })
            continue

        results_dir = Path(compat["results_dir"])

        raw_path = records_dir / f"{name}.raw.json"
        final_path = records_dir / f"{name}.json"

        extract_cmd = [
            sys.executable,
            str(EXTRACTOR),
            str(results_dir),
            "--workload", workload,
            "--active-cores", str(active_cores),
            "--pretty",
        ]

        rc, stdout, stderr = run_command(extract_cmd)

        if rc != 0:
            message = (
                stderr.strip()
                or stdout.strip()
                or f"extractor exit code {rc}"
            )

            print(f"{prefix}: FAIL (extract)")

            failures.append({
                "run": name,
                "stage": "extract",
                "error": message,
            })
            continue

        try:
            raw_record = json.loads(stdout)
        except json.JSONDecodeError as e:
            print(f"{prefix}: FAIL (invalid extractor JSON)")

            failures.append({
                "run": name,
                "stage": "extract-json",
                "error": str(e),
            })
            continue

        # Add dataset provenance before McPAT enrichment.
        raw_record["dataset"] = {
            "manifest": args.manifest.name,
            "compatibility_tier": compat["tier"],
            "power_baseline_compatible":
                compat["power_baseline_compatible"],
            "final_nps4_compatible":
                compat["final_nps4_compatible"],
        }

        with raw_path.open("w") as f:
            json.dump(
                raw_record,
                f,
                indent=2,
                sort_keys=True,
            )
            f.write("\n")

        mcpat_cmd = [
            sys.executable,
            str(ATTACH_MCPAT),
            str(raw_path),
            "-o", str(final_path),
        ]

        rc, stdout, stderr = run_command(mcpat_cmd)

        if rc != 0:
            message = (
                stderr.strip()
                or stdout.strip()
                or f"McPAT bridge exit code {rc}"
            )

            print(f"{prefix}: FAIL (McPAT)")

            failures.append({
                "run": name,
                "stage": "mcpat",
                "error": message,
            })
            continue

        try:
            with final_path.open() as f:
                final_record = json.load(f)
        except Exception as e:
            print(f"{prefix}: FAIL (read final record)")

            failures.append({
                "run": name,
                "stage": "final-json",
                "error": str(e),
            })
            continue

        dataset_records.append(final_record)

        cpu_w = final_record["mcpat"]["cpu_side_w"]
        l3 = final_record["cache"]["l3_accesses_per_kinst"]
        dram = final_record["memory"]["dram_accesses_per_kinst"]

        def fmt(x):
            return "NA" if x is None else f"{x:.3f}"

        print(
            f"{prefix}: PASS "
            f"cores={active_cores:3d} "
            f"cpu={cpu_w:7.2f}W "
            f"L3/kI={fmt(l3):>9s} "
            f"DRAM/kI={fmt(dram):>9s}"
        )

    dataset = {
        "schema_version": 1,

        "description": manifest.get(
            "description",
            "EPYC 7763 power characterization dataset",
        ),

        "source_manifest": str(args.manifest),

        "reference_run": compatibility.get(
            "reference_run"
        ),

        "mcpat_target": {
            "field": "mcpat.cpu_side_w",
            "technology_node_nm": 22,
            "status": "REFERENCE_ONLY",
            "physical_calibrated": False,
            "legacy_dram_excluded": True,
        },

        "records": dataset_records,

        "failures": failures,

        "summary": {
            "requested": len(manifest["runs"]),
            "successful": len(dataset_records),
            "failed": len(failures),
        },
    }

    dataset_path = args.output_dir / "dataset.json"

    with dataset_path.open("w") as f:
        json.dump(
            dataset,
            f,
            indent=2,
            sort_keys=True,
        )
        f.write("\n")

    failures_path = args.output_dir / "failures.json"

    with failures_path.open("w") as f:
        json.dump(
            failures,
            f,
            indent=2,
            sort_keys=True,
        )
        f.write("\n")

    print()
    print("=== DATASET SUMMARY ===")
    print("requested :", len(manifest["runs"]))
    print("successful:", len(dataset_records))
    print("failed    :", len(failures))
    print("dataset   :", dataset_path)
    print("failures  :", failures_path)

    if not dataset_records:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
