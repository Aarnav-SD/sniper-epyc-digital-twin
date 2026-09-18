#!/usr/bin/env python3

import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "model",
        type=Path,
    )

    parser.add_argument(
        "--instruction-rate-gips",
        type=float,
        required=True,
    )

    args = parser.parse_args()

    with args.model.open() as f:
        model = json.load(f)

    rate = args.instruction_rate_gips

    domain = model["training_domain"]
    lo = domain["instruction_rate_gips_min"]
    hi = domain["instruction_rate_gips_max"]

    eq = model["equation"]

    power = (
        eq["intercept_w"]
        + eq["instruction_rate_gips_coefficient"]
        * rate
    )

    in_domain = lo <= rate <= hi

    result = {
        "model_id": model["model_id"],
        "instruction_rate_gips": rate,
        "cpu_power_w": power,
        "status": model["target"]["status"],
        "physical_calibrated":
            model["target"]["physical_calibrated"],
        "in_training_domain": in_domain,
        "training_domain_gips": [lo, hi],
    }

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
