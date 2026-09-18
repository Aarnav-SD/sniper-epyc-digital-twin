#!/usr/bin/env python3

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np


CANDIDATES = {
    "constant": [],
    "gips": [
        "instruction_rate_gips",
    ],
    "gips_active_cores": [
        "instruction_rate_gips",
        "active_cores",
    ],
    "gips_l3_dram": [
        "instruction_rate_gips",
        "l3_accesses_per_kinst",
        "dram_accesses_per_kinst",
    ],
    "gips_active_l3_dram": [
        "instruction_rate_gips",
        "active_cores",
        "l3_accesses_per_kinst",
        "dram_accesses_per_kinst",
    ],
}


def load_rows(path):
    with path.open() as f:
        d = json.load(f)

    rows = []

    for r in d["records"]:
        rows.append({
            "run": r["source"]["results_dir"],
            "workload": r["source"]["workload"],
            "active_cores":
                float(r["execution"]["active_cores"]),
            "instruction_rate_gips":
                float(r["execution"]["instruction_rate_gips"]),
            "l3_accesses_per_kinst":
                float(r["cache"]["l3_accesses_per_kinst"]),
            "dram_accesses_per_kinst":
                float(r["memory"]["dram_accesses_per_kinst"]),
            "target":
                float(r["mcpat"]["cpu_side_w"]),
        })

    return rows


def design_matrix(rows, features):
    # Explicit intercept.
    return np.asarray([
        [1.0] + [r[f] for f in features]
        for r in rows
    ], dtype=float)


def targets(rows):
    return np.asarray(
        [r["target"] for r in rows],
        dtype=float
    )


def fit(rows, features):
    X = design_matrix(rows, features)
    y = targets(rows)

    beta, _, _, _ = np.linalg.lstsq(
        X, y, rcond=None
    )

    return beta


def predict(rows, features, beta):
    X = design_matrix(rows, features)
    return X @ beta


def metrics(actual, predicted):
    err = predicted - actual

    mae = float(np.mean(np.abs(err)))
    rmse = float(np.sqrt(np.mean(err ** 2)))

    mape = float(
        np.mean(
            np.abs(err / actual)
        ) * 100.0
    )

    return {
        "mae_w": mae,
        "rmse_w": rmse,
        "mape_pct": mape,
    }


def lofo(rows, features):
    families = sorted(
        set(r["workload"] for r in rows)
    )

    all_actual = []
    all_pred = []
    fold_results = []

    for family in families:
        train = [
            r for r in rows
            if r["workload"] != family
        ]

        test = [
            r for r in rows
            if r["workload"] == family
        ]

        beta = fit(train, features)
        pred = predict(test, features, beta)
        actual = targets(test)

        m = metrics(actual, pred)

        fold_results.append({
            "held_out": family,
            "n": len(test),
            **m,
        })

        all_actual.extend(actual.tolist())
        all_pred.extend(pred.tolist())

    overall = metrics(
        np.asarray(all_actual),
        np.asarray(all_pred),
    )

    return overall, fold_results


def training_metrics(rows, features):
    beta = fit(rows, features)
    pred = predict(rows, features, beta)

    return (
        beta,
        metrics(targets(rows), pred),
    )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "dataset",
        type=Path,
    )

    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path(
            "power-data/characterization_v1/"
            "model_selection.json"
        ),
    )

    args = parser.parse_args()

    rows = load_rows(args.dataset)

    print("=== REDUCED-ORDER MODEL SELECTION ===")
    print("observations :", len(rows))
    print(
        "families     :",
        len(set(r["workload"] for r in rows))
    )

    results = []

    for name, features in CANDIDATES.items():
        beta, train_m = training_metrics(
            rows, features
        )

        cv_m, folds = lofo(
            rows, features
        )

        entry = {
            "name": name,
            "features": features,
            "coefficients": beta.tolist(),
            "training": train_m,
            "lofo": cv_m,
            "folds": folds,
        }

        results.append(entry)

    print()
    print(
        f"{'model':24s} "
        f"{'k':>2s} "
        f"{'train MAE':>10s} "
        f"{'CV MAE':>9s} "
        f"{'CV RMSE':>9s} "
        f"{'CV MAPE':>9s}"
    )

    for x in results:
        print(
            f"{x['name']:24s} "
            f"{len(x['features']):2d} "
            f"{x['training']['mae_w']:10.3f} "
            f"{x['lofo']['mae_w']:9.3f} "
            f"{x['lofo']['rmse_w']:9.3f} "
            f"{x['lofo']['mape_pct']:8.3f}%"
        )

    print("\n=== FOLD DETAILS ===")

    for x in results:
        print(f"\n[{x['name']}]")

        for fold in x["folds"]:
            print(
                f"  {fold['held_out']:28s} "
                f"n={fold['n']:2d} "
                f"MAE={fold['mae_w']:7.3f} W "
                f"RMSE={fold['rmse_w']:7.3f} W "
                f"MAPE={fold['mape_pct']:6.3f}%"
            )

    print("\n=== FULL-DATA COEFFICIENTS ===")

    for x in results:
        labels = ["intercept"] + x["features"]

        print(f"\n[{x['name']}]")

        for label, value in zip(
            labels,
            x["coefficients"],
        ):
            print(
                f"  {label:28s} "
                f"{value: .8f}"
            )

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with args.output.open("w") as f:
        json.dump(
            {
                "schema_version": 1,
                "validation":
                    "leave-one-workload-family-out",
                "target":
                    "mcpat.cpu_side_w",
                "physical_calibrated": False,
                "models": results,
            },
            f,
            indent=2,
        )

    print()
    print("results:", args.output)


if __name__ == "__main__":
    main()
