#!/usr/bin/env python3
"""
Maximal-p sweep: for each (generator, test) pair, find the largest p=q the file
can support before EOF, then run once at that p and report whether the result
beats the 1e-10 "real claim" threshold.

Strategy:
  Phase 1 (Doubling)   - start at the catalog's smallest p (overridable),
                         double until rtest fails or the run yields p-value 0
                         (treated as an EOF artifact, not a statistical signal).
  Phase 2 (Bisection)  - binary-search between the last good p and the first
                         bad p to pin the file's true ceiling.
  Phase 3 (Final run)  - re-run rtest at the located max_p into a clean dir
                         and check the objective against --threshold.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path

from robust_test_catalog import TEST_CATALOG, TestConfig


FLOAT_RE = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?")
FLOAT_LINE_RE = re.compile(
    r"^\s*[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?(?:\s+[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)*\s*$"
)


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--campaign", required=True, help="Short campaign tag, e.g. nist_max_20260502")
    parser.add_argument(
        "--generator-dir",
        type=Path,
        required=True,
        help="Directory containing the generator .bin files to test",
    )
    parser.add_argument("--generator-glob", default="*.bin")
    parser.add_argument("--tests", nargs="+", type=int, default=sorted(TEST_CATALOG.keys()),
                        help="Test numbers to run (default: all in catalog)")
    parser.add_argument("--etalon", type=Path, required=True,
                        help="Fixed reference file, at least as large as the generator files")
    parser.add_argument("--rtest", type=Path, default=repo_root / "robust" / "rtest")
    parser.add_argument("--results-root", type=Path, default=Path("sweep_results"),
                        help="Where to write results (default: ./sweep_results)")
    parser.add_argument("--xor", action=argparse.BooleanOptionalAction, default=True,
                        help="Pass -x so comparison side uses tested xor etalon (default on)")
    parser.add_argument("--max-generators", type=int, default=0, help="Cap for smoke testing; 0 = all")
    parser.add_argument("--start-p", nargs="*", default=[],
                        help="Per-test starting p overrides like 27=10 22=4")
    parser.add_argument("--max-p", type=int, default=10_000,
                        help="Safety cap on doubling phase (default 10,000 = rtest's SAMPLE_SIZE_BOUND)")
    parser.add_argument("--threshold", type=float, default=1e-10,
                        help="Objective threshold for a 'real claim' (default 1e-10)")
    parser.add_argument("--charts", action=argparse.BooleanOptionalAction, default=True,
                        help="Generate SVG ECDF chart at the final max_p (default on)")
    return parser.parse_args()


def parse_start_p_overrides(items: list[str]) -> dict[int, int]:
    out: dict[int, int] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"invalid --start-p item: {item}")
        t, p = item.split("=", 1)
        out[int(t)] = int(p)
    return out


def generator_code(index: int, path: Path) -> str:
    stem = path.stem.replace("bad_", "").replace("-", "_")
    parts = [piece for piece in re.split(r"[^A-Za-z0-9]+", stem) if piece]
    short = "_".join(parts[:3]).lower()
    return f"g{index:02d}_{short}"[:32]


def parse_values(cfg: TestConfig, stdout: str) -> list[float]:
    if cfg.parse_kind == "vector_anyfloat":
        values = [float(x) for x in FLOAT_RE.findall(stdout)]
        if len(values) < cfg.dimension:
            raise ValueError(f"expected at least {cfg.dimension} floats, got {len(values)}")
        return values[: cfg.dimension]
    if cfg.parse_kind == "vector_lastline":
        lines = [line.strip() for line in stdout.splitlines() if FLOAT_LINE_RE.fullmatch(line)]
        if not lines:
            raise ValueError("expected numeric output line, got none")
        values = [float(x) for x in lines[-1].split()]
        if len(values) != cfg.dimension:
            raise ValueError(f"expected {cfg.dimension} floats, got {len(values)}")
        return values
    if cfg.parse_kind == "single_anyfloat":
        values = [float(x) for x in FLOAT_RE.findall(stdout)]
        if not values:
            raise ValueError("expected a float, got none")
        return [values[0]]
    if cfg.parse_kind == "single_lastline":
        lines = [line.strip() for line in stdout.splitlines() if FLOAT_LINE_RE.fullmatch(line)]
        if not lines:
            raise ValueError("expected numeric output line, got none")
        return [float(lines[-1])]
    raise ValueError(f"unknown parse kind: {cfg.parse_kind}")


def build_cmd(rtest: Path, tested: Path, etalon: Path, rel_out_dir: Path,
              cfg: TestConfig, p: int, use_xor: bool) -> list[str]:
    cmd = [str(rtest)]
    if use_xor:
        cmd.append("-x")
    cmd += [
        "-f", str(tested),
        "-e", str(etalon),
        "-p", str(p),
        "-q", str(p),
        "-d", str(cfg.dimension),
        "-n", str(cfg.n_value),
        "-t", str(cfg.test_num),
        "-r", "1",
        "-o", str(rel_out_dir),
    ]
    if cfg.modifier is not None:
        cmd += ["-m", str(cfg.modifier)]
    return cmd


def run_one(rtest: Path, tested: Path, etalon: Path, cwd: Path, rel_out_dir: Path,
            cfg: TestConfig, p: int, use_xor: bool) -> dict:
    # rtest enforces strlen(output_directory) < 128 and does its own mkdir,
    # so we run with cwd=campaign_root and pass a short relative -o path,
    # creating the parent ourselves but letting rtest create the leaf.
    abs_out = (cwd / rel_out_dir).resolve()
    abs_out.parent.mkdir(parents=True, exist_ok=True)
    if abs_out.exists():
        for child in abs_out.iterdir():
            child.unlink()
        abs_out.rmdir()
    if len(str(rel_out_dir)) >= 128:
        return {"p": p, "returncode": -1, "elapsed_s": 0.0,
                "output_dir": str(abs_out),
                "stderr_tail": [f"rel out path too long: {len(str(rel_out_dir))} chars"],
                "status": "rtest_failed"}
    cmd = build_cmd(rtest, tested, etalon, rel_out_dir, cfg, p, use_xor)
    t0 = time.monotonic()
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    elapsed = time.monotonic() - t0
    record: dict = {
        "p": p,
        "returncode": result.returncode,
        "elapsed_s": round(elapsed, 3),
        "output_dir": str(abs_out),
        "stderr_tail": result.stderr.strip().splitlines()[-3:] if result.stderr.strip() else [],
    }
    if result.returncode != 0:
        record["status"] = "rtest_failed"
        return record
    try:
        values = parse_values(cfg, result.stdout)
    except ValueError as exc:
        record["status"] = "parse_error"
        record["parse_error"] = str(exc)
        return record
    record["values"] = values
    record["objective"] = min(values)
    record["status"] = "ok" if record["objective"] > 0.0 else "eof_zero"
    return record


def is_good(record: dict) -> bool:
    return record.get("status") == "ok"


def find_maximal_p(start_p: int, max_p: int, run_fn) -> tuple[int | None, dict | None, list[dict]]:
    cache: dict[int, dict] = {}
    history: list[dict] = []

    def evaluate(p: int, phase: str) -> dict:
        if p in cache:
            cached = dict(cache[p])
            cached["phase"] = f"{cached.get('phase', phase)}+cache"
            return cached
        rec = run_fn(p)
        rec["phase"] = phase
        cache[p] = rec
        history.append(rec)
        return rec

    rec0 = evaluate(start_p, "double")
    if not is_good(rec0):
        return None, rec0, history

    last_good_p = start_p
    p = start_p * 2
    first_bad_p: int | None = None
    while p <= max_p:
        rec = evaluate(p, "double")
        if is_good(rec):
            last_good_p = p
            p *= 2
        else:
            first_bad_p = p
            break

    if first_bad_p is None:
        # doubling overshot the cap without failing; probe max_p itself
        # so we don't silently stop at the largest doubled value (e.g. 5120
        # when the true ceiling is 10000).
        if last_good_p >= max_p:
            return last_good_p, cache[last_good_p], history
        rec = evaluate(max_p, "ceil_probe")
        if is_good(rec):
            return max_p, cache[max_p], history
        first_bad_p = max_p

    lo, hi = last_good_p, first_bad_p
    while hi - lo > 1:
        mid = (lo + hi) // 2
        rec = evaluate(mid, "bisect")
        if is_good(rec):
            lo = mid
        else:
            hi = mid

    return lo, cache[lo], history


def write_history(test_dir: Path, history: list[dict]) -> None:
    rows = sorted(history, key=lambda r: (r["p"], r.get("phase", "")))
    with (test_dir / "history.csv").open("w", newline="", encoding="ascii") as f:
        w = csv.writer(f)
        w.writerow(["phase", "p", "status", "returncode", "objective", "elapsed_s", "values", "output_dir"])
        for r in rows:
            w.writerow([
                r.get("phase", ""),
                r["p"],
                r.get("status", ""),
                r.get("returncode", ""),
                r.get("objective", ""),
                r.get("elapsed_s", ""),
                " ".join(f"{v:.17g}" for v in r.get("values", [])),
                r.get("output_dir", ""),
            ])
    with (test_dir / "history.json").open("w", encoding="ascii") as f:
        json.dump(rows, f, indent=2)


def generate_chart(plot_script: Path, run_dir: Path, coord: int, out_file: Path, title: str) -> None:
    etal = run_dir / f"000000.etal.{coord:04d}"
    test = run_dir / f"000000.test.{coord:04d}"
    if not etal.is_file() or not test.is_file():
        raise FileNotFoundError(f"chart inputs missing for coord {coord}: {run_dir}")
    cmd = [sys.executable, str(plot_script), str(etal), str(test),
           "--out", str(out_file), "--title", title]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(res.stderr.strip() or "chart generation failed")


def main() -> int:
    args = parse_args()
    plot_script = (Path(__file__).resolve().parent / "plot_distribs_svg.py").resolve()

    try:
        start_overrides = parse_start_p_overrides(args.start_p)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    rtest = args.rtest.expanduser().resolve()
    etalon = args.etalon.expanduser().resolve()
    generator_dir = args.generator_dir.expanduser().resolve()
    campaign_root = args.results_root.expanduser().resolve() / args.campaign
    sweep_root = campaign_root / "sweeps"
    charts_root = campaign_root / "charts"

    for label, path, kind in [("rtest", rtest, "file"), ("etalon", etalon, "file"),
                              ("generator-dir", generator_dir, "dir")]:
        ok = path.is_file() if kind == "file" else path.is_dir()
        if not ok:
            print(f"{label} not found: {path}", file=sys.stderr)
            return 1

    selected: list[tuple[TestConfig, int]] = []
    for tnum in args.tests:
        cfg = TEST_CATALOG.get(tnum)
        if cfg is None:
            print(f"unknown test number: {tnum}", file=sys.stderr)
            return 1
        start_p = start_overrides.get(tnum, cfg.p_values[0])
        selected.append((cfg, start_p))

    generators = sorted(generator_dir.glob(args.generator_glob))
    if args.max_generators > 0:
        generators = generators[: args.max_generators]
    if not generators:
        print(f"no generators matched {args.generator_glob} in {generator_dir}", file=sys.stderr)
        return 1

    sweep_root.mkdir(parents=True, exist_ok=True)
    if args.charts:
        charts_root.mkdir(parents=True, exist_ok=True)

    manifest_rows: list[dict] = []
    summary_rows: list[dict] = []
    t_start = time.monotonic()

    for idx, tested in enumerate(generators, start=1):
        gen_code = generator_code(idx, tested)
        manifest_rows.append({"generator_code": gen_code, "filename": tested.name, "path": str(tested)})
        print(f"\n=== {gen_code}: {tested.name} ===")

        for cfg, start_p in selected:
            rel_test_dir = Path("sweeps") / gen_code / f"t{cfg.test_num:02d}"
            test_dir = campaign_root / rel_test_dir
            probes_rel = rel_test_dir / "probes"
            (campaign_root / probes_rel).mkdir(parents=True, exist_ok=True)
            print(f"  t{cfg.test_num:02d} {cfg.title}  start_p={start_p}  cap={args.max_p}")

            def run_fn(p: int, _cfg=cfg, _probes_rel=probes_rel, _tested=tested) -> dict:
                rec = run_one(rtest, _tested, etalon, campaign_root,
                              _probes_rel / f"p{p:06d}", _cfg, p, args.xor)
                obj = rec.get("objective", "n/a")
                obj_str = f"{obj:.6g}" if isinstance(obj, float) else obj
                print(f"    p={p:>7}  {rec.get('status','?'):<12}  obj={obj_str}  ({rec.get('elapsed_s','?')}s)")
                return rec

            max_p, max_record, history = find_maximal_p(start_p, args.max_p, run_fn)
            write_history(test_dir, history)

            if max_p is None:
                print(f"    !! start_p={start_p} already bad ({max_record.get('status') if max_record else 'unknown'}); skipping")
                summary_rows.append({
                    "generator_code": gen_code, "generator_file": tested.name,
                    "test_num": cfg.test_num, "title": cfg.title,
                    "start_p": start_p, "max_p": "", "final_objective": "",
                    "beats_threshold": "", "bad_reason_at_ceiling": max_record.get("status", "") if max_record else "",
                    "n_probes": len(history),
                })
                continue

            final_rel = rel_test_dir / f"final_p{max_p:06d}"
            final_dir = campaign_root / final_rel
            final_record = run_one(rtest, tested, etalon, campaign_root, final_rel, cfg, max_p, args.xor)
            final_obj = final_record.get("objective")
            beats = isinstance(final_obj, float) and final_obj <= args.threshold
            # Best objective across the entire sweep (per CiE submission §4):
            # the paper records both the ceiling objective and the best one
            # seen during the sweep, since the KS signal can peak mid-p and
            # degrade at the ceiling for tests like t29/t30/t31.
            good_objs = [r["objective"] for r in history
                         if is_good(r) and isinstance(r.get("objective"), float)]
            # Also include the final ceiling run (which is run separately).
            if isinstance(final_obj, float):
                good_objs.append(final_obj)
            best_obj = min(good_objs) if good_objs else None
            best_obj_p = None
            if best_obj is not None:
                # Find the smallest p that achieved best_obj (prefer earlier probes on ties).
                cands = [r for r in history
                         if is_good(r) and isinstance(r.get("objective"), float)
                         and r["objective"] == best_obj]
                if isinstance(final_obj, float) and final_obj == best_obj:
                    cands.append({"p": max_p})
                if cands:
                    best_obj_p = min(c["p"] for c in cands)
            best_beats = isinstance(best_obj, float) and best_obj <= args.threshold

            print(f"    -> max_p={max_p}  final_objective={final_obj}  beats_{args.threshold:g}={beats}")
            if best_obj is not None and (not isinstance(final_obj, float)
                                         or best_obj < final_obj):
                print(f"       best_obj_in_sweep={best_obj} at p={best_obj_p}  beats={best_beats}")

            # find the bad-reason at the ceiling (first bad p > max_p in history, if any)
            bads_above = [r for r in history if r["p"] > max_p and not is_good(r)]
            ceiling_reason = bads_above[0].get("status", "") if bads_above else "uncapped"

            summary_rows.append({
                "generator_code": gen_code, "generator_file": tested.name,
                "test_num": cfg.test_num, "title": cfg.title,
                "start_p": start_p, "max_p": max_p,
                "final_objective": f"{final_obj:.17g}" if isinstance(final_obj, float) else "",
                "beats_threshold": "yes" if beats else "no",
                "best_obj_in_sweep": f"{best_obj:.17g}" if isinstance(best_obj, float) else "",
                "best_obj_p": best_obj_p if best_obj_p is not None else "",
                "best_obj_beats_threshold": "yes" if best_beats else ("no" if best_obj is not None else ""),
                "bad_reason_at_ceiling": ceiling_reason,
                "n_probes": len(history),
            })

            if args.charts and final_record.get("status") == "ok":
                chart_dir = charts_root / gen_code / f"t{cfg.test_num:02d}"
                chart_dir.mkdir(parents=True, exist_ok=True)
                for coord in cfg.chart_coords:
                    out_svg = chart_dir / f"max_p{max_p:06d}_c{coord:04d}.svg"
                    try:
                        generate_chart(plot_script, final_dir, coord,
                                       out_svg, f"{gen_code} t{cfg.test_num} max p=q={max_p} coord={coord}")
                        print(f"    chart: {out_svg.relative_to(campaign_root)}")
                    except (FileNotFoundError, RuntimeError) as exc:
                        print(f"    chart skipped (coord {coord}): {exc}")

    manifest_path = campaign_root / "generator_manifest.csv"
    with manifest_path.open("w", newline="", encoding="ascii") as f:
        w = csv.DictWriter(f, fieldnames=["generator_code", "filename", "path"])
        w.writeheader()
        w.writerows(manifest_rows)

    summary_csv = campaign_root / "maximal_p.csv"
    with summary_csv.open("w", newline="", encoding="ascii") as f:
        cols = ["generator_code", "generator_file", "test_num", "title", "start_p",
                "max_p", "final_objective", "beats_threshold",
                "best_obj_in_sweep", "best_obj_p", "best_obj_beats_threshold",
                "bad_reason_at_ceiling", "n_probes"]
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(summary_rows)

    meta = {
        "campaign": args.campaign,
        "generator_dir": str(generator_dir),
        "generator_glob": args.generator_glob,
        "etalon": str(etalon),
        "rtest": str(rtest),
        "xor": args.xor,
        "max_p_cap": args.max_p,
        "threshold": args.threshold,
        "charts_enabled": args.charts,
        "tests": [
            {**asdict(cfg), "start_p": start_p}
            for cfg, start_p in selected
        ],
        "elapsed_s": round(time.monotonic() - t_start, 1),
    }
    with (campaign_root / "campaign.json").open("w", encoding="ascii") as f:
        json.dump(meta, f, indent=2)

    print(f"\nWrote {summary_csv}")
    print(f"Wrote {campaign_root / 'campaign.json'}")
    print(f"Wrote {manifest_path}")
    print(f"Total elapsed: {meta['elapsed_s']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
