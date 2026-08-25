#!/usr/bin/env python3

import argparse
import configparser
import os
import re
import sqlite3
import sys
from collections import defaultdict


def parse_args():
    p = argparse.ArgumentParser(
        description="Validate EPYC NUMA/DRAM behavior from a Sniper run directory."
    )
    p.add_argument("run_dir", help="Sniper run directory")
    p.add_argument(
        "--bandwidth",
        type=float,
        default=None,
        help="Measured application bandwidth in GB/s, if known"
    )
    return p.parse_args()


def load_config(path):
    cfg = configparser.ConfigParser(
        interpolation=None,
        strict=False
    )
    cfg.read(path)
    return cfg


def cfg_int(cfg, section, key, default):
    try:
        return cfg.getint(section, key)
    except Exception:
        return default


def cfg_float(cfg, section, key, default):
    try:
        return cfg.getfloat(section, key)
    except Exception:
        return default


def cfg_bool(cfg, section, key, default):
    try:
        value = cfg.get(section, key).strip().strip('"').strip("'").lower()

        if value in ("true", "yes", "on", "1"):
            return True

        if value in ("false", "no", "off", "0"):
            return False

        return default
    except Exception:
        return default


def cfg_string(cfg, section, key, default):
    try:
        return cfg.get(section, key).strip('"')
    except Exception:
        return default


def get_stop_metrics(conn, object_names):
    placeholders = ",".join("?" for _ in object_names)

    sql = f"""
    SELECT
        n.objectname,
        v.core,
        n.metricname,
        v.value
    FROM "values" v
    JOIN names n
      ON n.nameid = v.nameid
    JOIN prefixes p
      ON p.prefixid = v.prefixid
    WHERE p.prefixname = 'stop'
      AND n.objectname IN ({placeholders})
    """

    rows = conn.execute(sql, object_names).fetchall()
    return rows


def parse_stream_result(run_dir):
    """
    Try to recover STREAM RESULT from common run-output locations.
    This is optional: Sniper's SQLite stats do not contain the application's
    internally measured stream makespan.
    """
    candidates = [
        os.path.join(run_dir, "simulation", "sim.out"),
        os.path.join(run_dir, "sim.out"),
    ]

    pattern = re.compile(
        r"STREAM RESULT .*?"
        r"threads=(\d+).*?"
        r"mode=(\S+).*?"
        r"bytes=(\d+).*?"
        r"duration_fs=(\d+).*?"
        r"bandwidth_GBps=([0-9.]+)"
    )

    for path in candidates:
        if not os.path.isfile(path):
            continue

        try:
            with open(path, "r", errors="replace") as f:
                for line in f:
                    m = pattern.search(line)
                    if m:
                        return {
                            "threads": int(m.group(1)),
                            "mode": m.group(2),
                            "bytes": int(m.group(3)),
                            "duration_fs": int(m.group(4)),
                            "bandwidth_GBps": float(m.group(5)),
                        }
        except OSError:
            pass

    return None


def pct(a, b):
    if b == 0:
        return 0.0
    return 100.0 * a / b


def status(ok):
    return "PASS" if ok else "FAIL"


def main():
    args = parse_args()

    run_dir = os.path.abspath(args.run_dir)
    db_path = os.path.join(
        run_dir, "simulation", "sim.stats.sqlite3"
    )
    cfg_path = os.path.join(
        run_dir, "simulation", "sim.cfg"
    )

    if not os.path.isfile(db_path):
        print(f"ERROR: database not found: {db_path}", file=sys.stderr)
        return 1

    if not os.path.isfile(cfg_path):
        print(f"ERROR: config not found: {cfg_path}", file=sys.stderr)
        return 1

    cfg = load_config(cfg_path)

    dram_section = "perf_model/dram"
    numa_section = "perf_model/dram/numa"

    num_controllers = cfg_int(
        cfg, dram_section, "num_controllers", 0
    )

    controller_string = cfg_string(
        cfg, dram_section, "controller_positions", ""
    )

    controllers = [
        int(x.strip())
        for x in controller_string.split(",")
        if x.strip()
    ]

    if not controllers and num_controllers:
        controllers = list(range(num_controllers))

    bw_per_controller = cfg_float(
        cfg, dram_section, "per_controller_bandwidth", 0.0
    )

    numa_enabled = cfg_bool(
        cfg, numa_section, "enabled", False
    )

    num_nodes = cfg_int(
        cfg, numa_section, "num_nodes", 1
    )

    cores_per_node = cfg_int(
        cfg, numa_section, "cores_per_node", 0
    )

    remote_latency_ns = cfg_int(
        cfg, numa_section, "remote_latency_ns", 0
    )

    controllers_per_node = (
        len(controllers) // num_nodes
        if num_nodes > 0 else 0
    )

    socket_peak = (
        controllers_per_node * bw_per_controller
    )

    node_peak = (
        len(controllers) * bw_per_controller
    )

    conn = sqlite3.connect(db_path)

    rows = get_stop_metrics(
        conn,
        ["dram", "dram-numa1", "L1-D", "performance_model", "barrier"]
    )

    metrics = defaultdict(dict)

    for obj, core, metric, value in rows:
        metrics[(obj, core)][metric] = value

    #
    # Controller statistics
    #
    controller_rows = []

    for controller in controllers:
        base = metrics.get(("dram", controller), {})
        numa1 = metrics.get(("dram-numa1", controller), {})

        accesses = (
            base.get("total-accesses-data", 0)
            + numa1.get("total-accesses-data", 0)
        )

        latency_fs = (
            base.get("total-access-latency-data", 0)
            + numa1.get("total-access-latency-data", 0)
        )

        avg_latency_ns = (
            latency_fs / accesses / 1.0e6
            if accesses else 0.0
        )

        controller_rows.append({
            "controller": controller,
            "accesses": accesses,
            "latency_fs": latency_fs,
            "avg_latency_ns": avg_latency_ns,
        })

    #
    # NUMA statistics
    #
    numa_stats = {}

    for node in range(num_nodes):
        local_name = f"numa_node{node}_local_accesses"
        remote_name = f"numa_node{node}_remote_accesses"
        read_name = f"numa_node{node}_reads"
        write_name = f"numa_node{node}_writes"
        latency_name = f"numa_node{node}_total_latency"

        local = remote = reads = writes = latency = 0

        for controller in controllers:
            d = metrics.get(("dram", controller), {})

            local += d.get(local_name, 0)
            remote += d.get(remote_name, 0)
            reads += d.get(read_name, 0)
            writes += d.get(write_name, 0)
            latency += d.get(latency_name, 0)

        total = local + remote

        numa_stats[node] = {
            "local": local,
            "remote": remote,
            "reads": reads,
            "writes": writes,
            "latency_fs": latency,
            "total": total,
            "remote_fraction_pct": pct(remote, total),
            "effective_avg_latency_ns":
                latency / total / 1.0e6 if total else 0.0,
        }

    #
    # Controller grouping
    #
    node_controller_groups = {}

    for node in range(num_nodes):
        start = node * controllers_per_node
        end = start + controllers_per_node
        node_controller_groups[node] = controllers[start:end]

    controller_access_map = {
        x["controller"]: x["accesses"]
        for x in controller_rows
    }

    node_controller_accesses = {}

    for node, group in node_controller_groups.items():
        node_controller_accesses[node] = sum(
            controller_access_map.get(c, 0)
            for c in group
        )

    routing_leakage = {}

    for node in range(num_nodes):
        expected_group = set(node_controller_groups[node])

        correct = 0
        leaked = 0

        local_metric = f"numa_node{node}_local_accesses"
        remote_metric = f"numa_node{node}_remote_accesses"

        for controller in controllers:
            d = metrics.get(("dram", controller), {})

            accesses = (
                d.get(local_metric, 0) +
                d.get(remote_metric, 0)
            )

            if controller in expected_group:
                correct += accesses
            else:
                leaked += accesses

        total = correct + leaked

        routing_leakage[node] = {
            "correct": correct,
            "leaked": leaked,
            "leak_pct": pct(leaked, total),
        }

    controller_balance = {}

    for node, group in node_controller_groups.items():
        values = [
            controller_access_map.get(c, 0)
            for c in group
        ]

        mean = sum(values) / len(values) if values else 0

        if mean > 0:
            deviations = [
                abs(v - mean) / mean * 100.0
                for v in values
            ]

            max_deviation = max(deviations)
        else:
            max_deviation = 0.0

        controller_balance[node] = max_deviation

    #
    # Optional benchmark result
    #
    stream = parse_stream_result(run_dir)

    measured_bw = args.bandwidth

    if measured_bw is None and stream is not None:
        measured_bw = stream["bandwidth_GBps"]

    critical_checks = []
    #
    # Output
    #
    print("=" * 72)
    print("EPYC MEMORY VALIDATION REPORT")
    print("=" * 72)
    print(f"Run directory:              {run_dir}")
    print()

    print("CONFIGURATION")
    print("-" * 72)
    print(f"NUMA enabled:               {numa_enabled}")
    print(f"NUMA nodes:                 {num_nodes}")
    print(f"Cores per node:             {cores_per_node}")
    print(f"DRAM controllers:           {len(controllers)}")
    print(f"Controller positions:       {controllers}")
    print(f"Controllers per node:       {controllers_per_node}")
    print(f"Bandwidth/controller:       {bw_per_controller:.3f} GB/s")
    print(f"Theoretical socket peak:    {socket_peak:.3f} GB/s")
    print(f"Theoretical node peak:      {node_peak:.3f} GB/s")
    print(f"Remote NUMA penalty:        {remote_latency_ns} ns")
    print("Statistics scope:           cumulative through STOP")
    print("Bandwidth scope:            benchmark stream interval")
    print()

    print("NUMA TRAFFIC")
    print("-" * 72)

    for node in range(num_nodes):
        s = numa_stats[node]

        print(
            f"Node {node}: "
            f"local={s['local']:,}  "
            f"remote={s['remote']:,}  "
            f"remote_fraction={s['remote_fraction_pct']:.4f}%  "
            f"reads={s['reads']:,}  "
            f"writes={s['writes']:,}  "
            f"effective_loaded_latency={s['effective_avg_latency_ns']:.3f} ns"
        )

    print()
    print("DRAM CONTROLLERS")
    print("-" * 72)
    print(
        f"{'Controller':>10} "
        f"{'Node':>6} "
        f"{'Accesses':>16} "
        f"{'Loaded avg latency (ns)':>18}"
    )

    for row in controller_rows:
        controller = row["controller"]

        owner = None
        for node, group in node_controller_groups.items():
            if controller in group:
                owner = node
                break

        print(
            f"{controller:>10} "
            f"{str(owner):>6} "
            f"{row['accesses']:>16,} "
            f"{row['avg_latency_ns']:>18.3f}"
        )

    for node in range(num_nodes):
        print(
            f"Node {node} max controller deviation: "
            f"{controller_balance[node]:.2f}%"
        )

    print()

    if measured_bw is not None:
        print("BANDWIDTH")
        print("-" * 72)

        peak = node_peak

        bandwidth_ceiling_ok = measured_bw <= peak * 1.01
        critical_checks.append(bandwidth_ceiling_ok)

        print(
            f"Configured bandwidth ceiling: "
            f"{status(bandwidth_ceiling_ok)} "
            f"({measured_bw:.3f}/{peak:.3f} GB/s)"
        )

        if stream:
            mode = stream["mode"]

            if mode in ("socket0", "socket1"):
                peak = socket_peak

            print(f"Benchmark mode:             {mode}")
            print(f"Benchmark threads:          {stream['threads']}")
            print(f"Stream bytes:               {stream['bytes']:,}")
            print(
                f"Stream duration:            "
                f"{stream['duration_fs'] / 1.0e9:.3f} us"
            )

        print(f"Measured bandwidth:         {measured_bw:.3f} GB/s")
        print(f"Applicable peak:            {peak:.3f} GB/s")
        print(
            f"Peak utilization:           "
            f"{pct(measured_bw, peak):.2f}%"
        )
        print()

    #
    # Basic structural validation
    #
    print("VALIDATION")
    print("-" * 72)

    for node in range(num_nodes):
        r = routing_leakage[node]

        routing_ok = r["leak_pct"] < 0.1
        critical_checks.append(routing_ok)

        print(
            f"NUMA node {node} controller ownership: "
            f"{status(routing_ok)} "
            f"(leakage={r['leak_pct']:.4f}%)"
        )

    controller_count_ok = (
        num_nodes > 0
        and len(controllers) > 0
        and len(controllers) % num_nodes == 0
    )
    critical_checks.append(controller_count_ok)
    print(
        f"Controller/node divisibility: "
        f"{status(controller_count_ok)}"
    )

    all_controllers_active = all(
        controller_access_map.get(c, 0) > 0
        for c in controllers
    )
    critical_checks.append(all_controllers_active)
    print(
        f"Configured controllers active: "
        f"{status(all_controllers_active)}"
    )

    if num_nodes == 2:
        a0 = node_controller_accesses.get(0, 0)
        a1 = node_controller_accesses.get(1, 0)

        if max(a0, a1) > 0:
            symmetry_error = abs(a0 - a1) / max(a0, a1) * 100.0
        else:
            symmetry_error = 0.0

        socket_balance_ok = symmetry_error < 5.0
        critical_checks.append(socket_balance_ok)

        print(
            f"Socket controller traffic balance: "
            f"{status(socket_balance_ok)} "
            f"(difference={symmetry_error:.3f}%)"
        )

    total_local = sum(
        s["local"] for s in numa_stats.values()
    )

    total_remote = sum(
        s["remote"] for s in numa_stats.values()
    )

    total_numa = total_local + total_remote

    remote_fraction = pct(total_remote, total_numa)

    print(
        f"Aggregate remote fraction:  "
        f"{remote_fraction:.4f}%"
    )

    #
    # For a 'both' bandwidth benchmark, almost all traffic should be local
    # because each worker first-touches and then accesses its own pages.
    #
    if stream and stream["mode"] == "both":
        locality_ok = remote_fraction < 1.0
        critical_checks.append(locality_ok)

        print(
            f"Dual-socket local placement: "
            f"{status(locality_ok)}"
        )

    print()
    overall_ok = all(critical_checks)

    print()
    print(
        f"OVERALL STRUCTURAL VALIDATION: "
        f"{status(overall_ok)}"
    )


    print("=" * 72)

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())