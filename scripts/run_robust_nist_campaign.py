#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

from robust_test_catalog import TEST_CATALOG, TestConfig


FLOAT_RE = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?")
FLOAT_LINE_RE = re.compile(
    r"^\s*[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?(?:\s+[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)*\s*$"
)


def parse_args() -> argparse.Namespace:
    # repo_root is the project root (parent of Yash-New-Computer-Testsweeps/).
    # Default generator dir is auto-detected: pick the most recent
    # NIST_Bad_Generators_* folder under <project-root>/My-RNGs-Tests/, or
    # fall back to the directory itself if no timestamped subfolders exist.
    repo_root = Path(__file__).resolve().parent.parent.parent
    rngs_dir = repo_root / "My-RNGs-Tests"
    candidates = sorted(rngs_dir.glob("NIST_Bad_Generators_*"), reverse=True)
    default_generator_dir = candidates[0] if candidates else rngs_dir
    parser = argparse.ArgumentParser(
        description="Run organized robust sweeps against a NIST bad-generator directory, choose the best p=q per test, and generate paper charts."
    )
    parser.add_argument("--campaign", required=True, help="Short campaign tag, e.g. nist_100mb_apr12")
    parser.add_argument(
        "--generator-dir",
        type=Path,
        default=default_generator_dir,
        help="Directory containing bad-generator .bin files",
    )
    parser.add_argument(
        "--generator-glob",
        default="*.bin",
        help="Glob used inside generator-dir",
    )
    parser.add_argument(
        "--tests",
        nargs="+",
        type=int,
        default=[27, 28, 29, 30, 31],
        help="Test numbers to run",
    )
    parser.add_argument(
        "--etalon",
        type=Path,
        default=Path.home() / "Downloads" / "etal.bin",
        help="Path to etalon file",
    )
    parser.add_argument(
        "--rtest",
        type=Path,
        default=repo_root / "robust" / "rtest_fast",
        help="Path to rtest executable",
    )
    parser.add_argument(
        "--results-root",
        type=Path,
        default=repo_root / "My-robust-Test-Results" / "campaigns",
        help="Base directory for organized campaign results",
    )
    parser.add_argument(
        "--xor",
        action="store_true",
        help="Pass -x so the comparison side uses tested xor etalon",
    )
    parser.add_argument(
        "--max-generators",
        type=int,
        default=0,
        help="Optional cap for smoke tests; 0 means all generators",
    )
    parser.add_argument(
        "--p-values",
        nargs="*",
        default=[],
        help="Optional per-test p overrides like 27=5,10,20,40 28=5,10,15,20",
    )
    return parser.parse_args()


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
        numeric_lines = [line.strip() for line in stdout.splitlines() if FLOAT_LINE_RE.fullmatch(line)]
        if not numeric_lines:
            raise ValueError("expected numeric output line, got none")
        values = [float(x) for x in numeric_lines[-1].split()]
        if len(values) != cfg.dimension:
            raise ValueError(f"expected {cfg.dimension} floats, got {len(values)}")
        return values

    if cfg.parse_kind == "single_anyfloat":
        values = [float(x) for x in FLOAT_RE.findall(stdout)]
        if not values:
            raise ValueError("expected a float, got none")
        return [values[0]]

    if cfg.parse_kind == "single_lastline":
        numeric_lines = [line.strip() for line in stdout.splitlines() if FLOAT_LINE_RE.fullmatch(line)]
        if not numeric_lines:
            raise ValueError("expected numeric output line, got none")
        return [float(numeric_lines[-1])]

    raise ValueError(f"unknown parse kind: {cfg.parse_kind}")


def build_rtest_command(
    rtest: Path,
    tested: Path,
    etalon: Path,
    rel_output_dir: Path,
    cfg: TestConfig,
    p: int,
    use_xor: bool,
) -> list[str]:
    cmd = [
        str(rtest),
        "-f",
        str(tested),
        "-e",
        str(etalon),
        "-p",
        str(p),
        "-q",
        str(p),
        "-d",
        str(cfg.dimension),
        "-n",
        str(cfg.n_value),
        "-t",
        str(cfg.test_num),
        "-r",
        "1",
        "-o",
        str(rel_output_dir),
    ]
    if cfg.modifier is not None:
        cmd.extend(["-m", str(cfg.modifier)])
    if use_xor:
        cmd.insert(1, "-x")
    return cmd


def parse_p_value_overrides(raw_items: list[str]) -> dict[int, tuple[int, ...]]:
    overrides: dict[int, tuple[int, ...]] = {}
    for item in raw_items:
        if "=" not in item:
            raise ValueError(f"invalid --p-values item: {item}")
        test_str, values_str = item.split("=", 1)
        test_num = int(test_str)
        values = tuple(int(piece) for piece in values_str.split(",") if piece.strip())
        if not values:
            raise ValueError(f"no p-values provided for test {test_num}")
        overrides[test_num] = values
    return overrides


def run_one(
    repo_root: Path,
    rtest: Path,
    tested: Path,
    etalon: Path,
    rel_output_dir: Path,
    cfg: TestConfig,
    p: int,
    use_xor: bool,
) -> dict[str, object]:
    cmd = build_rtest_command(rtest, tested, etalon, rel_output_dir, cfg, p, use_xor)
    result = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True)
    record: dict[str, object] = {
        "test_num": cfg.test_num,
        "title": cfg.title,
        "p": p,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "output_dir": str(rel_output_dir),
    }
    if result.returncode != 0:
        record["status"] = "failed"
        return record
    try:
        values = parse_values(cfg, result.stdout)
    except ValueError as exc:
        record["status"] = "parse_error"
        record["parse_error"] = str(exc)
        return record
    record["status"] = "ok"
    record["values"] = values
    record["objective"] = min(values)
    record["min"] = min(values)
    record["median"] = sorted(values)[len(values) // 2]
    record["max"] = max(values)
    return record


def write_summary_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="ascii") as f:
        writer = csv.writer(f)
        writer.writerow(["p", "status", "objective", "min", "median", "max", "values", "output_dir"])
        for row in rows:
            writer.writerow(
                [
                    row.get("p", ""),
                    row.get("status", ""),
                    row.get("objective", ""),
                    row.get("min", ""),
                    row.get("median", ""),
                    row.get("max", ""),
                    " ".join(f"{v:.17g}" for v in row.get("values", [])),
                    row.get("output_dir", ""),
                ]
            )


def build_neighbor_ps(p_values: tuple[int, ...], best_p: int) -> list[int]:
    idx = p_values.index(best_p)
    selected = [best_p]
    if idx > 0:
        selected.insert(0, p_values[idx - 1])
    if idx + 1 < len(p_values):
        selected.append(p_values[idx + 1])
    return selected


def generate_chart(
    repo_root: Path,
    plot_script: Path,
    run_dir: Path,
    coord: int,
    out_file: Path,
    title: str,
) -> None:
    etal = run_dir / f"000000.etal.{coord:04d}"
    test = run_dir / f"000000.test.{coord:04d}"
    if not etal.is_file() or not test.is_file():
        raise FileNotFoundError(f"missing chart input for coord {coord}: {run_dir}")
    cmd = [
        sys.executable,
        str(plot_script),
        str(etal),
        str(test),
        "--out",
        str(out_file),
        "--title",
        title,
    ]
    result = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "chart generation failed")


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parent.parent.parent
    campaign_root = args.results_root.expanduser().resolve() / args.campaign
    sweep_root = campaign_root / "sweeps"
    charts_root = campaign_root / "charts"
    plot_script = (repo_root / "My-RNGs-Testers" / "scripts" / "plot_distribs_svg.py").resolve()
    generator_dir = args.generator_dir.expanduser().resolve()
    etalon = args.etalon.expanduser().resolve()
    rtest = args.rtest.expanduser().resolve()

    if not generator_dir.is_dir():
      print(f"generator-dir not found: {generator_dir}", file=sys.stderr)
      return 1
    if not etalon.is_file():
      print(f"etalon not found: {etalon}", file=sys.stderr)
      return 1
    if not rtest.is_file():
      print(f"rtest not found: {rtest}", file=sys.stderr)
      return 1

    selected_tests: list[TestConfig] = []
    try:
        p_value_overrides = parse_p_value_overrides(args.p_values)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    for test_num in args.tests:
        cfg = TEST_CATALOG.get(test_num)
        if cfg is None:
            print(f"unknown test number: {test_num}", file=sys.stderr)
            return 1
        override = p_value_overrides.get(test_num)
        if override is not None:
            cfg = TestConfig(
                test_num=cfg.test_num,
                title=cfg.title,
                dimension=cfg.dimension,
                n_value=cfg.n_value,
                modifier=cfg.modifier,
                p_values=override,
                parse_kind=cfg.parse_kind,
                chart_coords=cfg.chart_coords,
            )
        selected_tests.append(cfg)

    generators = sorted(generator_dir.glob(args.generator_glob))
    if args.max_generators > 0:
        generators = generators[: args.max_generators]
    if not generators:
        print("no generators matched", file=sys.stderr)
        return 1

    sweep_root.mkdir(parents=True, exist_ok=True)
    charts_root.mkdir(parents=True, exist_ok=True)

    manifest_rows: list[dict[str, object]] = []
    all_optimal_rows: list[dict[str, object]] = []

    for idx, tested in enumerate(generators, start=1):
        gen_code = generator_code(idx, tested)
        manifest_rows.append({"generator_code": gen_code, "filename": tested.name, "path": str(tested)})
        print(f"Running {gen_code}: {tested.name}")

        for cfg in selected_tests:
            test_dir = sweep_root / gen_code / f"t{cfg.test_num:02d}"
            test_dir.mkdir(parents=True, exist_ok=True)
            rows: list[dict[str, object]] = []

            for p in cfg.p_values:
                rel_output_dir = (test_dir / f"p{p:03d}").relative_to(repo_root)
                record = run_one(
                    repo_root=repo_root,
                    rtest=rtest,
                    tested=tested,
                    etalon=etalon,
                    rel_output_dir=rel_output_dir,
                    cfg=cfg,
                    p=p,
                    use_xor=args.xor,
                )
                rows.append(record)
                status = record["status"]
                tail = ""
                if status == "ok":
                    tail = f" objective={record['objective']:.6g}"
                print(f"  t{cfg.test_num:02d} p=q={p}: {status}{tail}")

            with (test_dir / "summary.json").open("w", encoding="ascii") as f:
                json.dump(rows, f, indent=2)
            write_summary_csv(test_dir / "summary.csv", rows)

            ok_rows = [row for row in rows if row.get("status") == "ok"]
            if not ok_rows:
                continue
            best_row = min(ok_rows, key=lambda row: float(row["objective"]))
            best_p = int(best_row["p"])
            chart_ps = build_neighbor_ps(cfg.p_values, best_p)

            chart_dir = charts_root / gen_code / f"t{cfg.test_num:02d}"
            chart_dir.mkdir(parents=True, exist_ok=True)
            generated_charts: list[str] = []

            for p in chart_ps:
                run_dir = repo_root / sweep_root.relative_to(repo_root) / gen_code / f"t{cfg.test_num:02d}" / f"p{p:03d}"
                for coord in cfg.chart_coords:
                    out_file = chart_dir / f"p{p:03d}_c{coord:04d}.svg"
                    generate_chart(
                        repo_root=repo_root,
                        plot_script=plot_script,
                        run_dir=run_dir,
                        coord=coord,
                        out_file=out_file,
                        title=f"{gen_code} t{cfg.test_num} p=q={p} coord={coord}",
                    )
                    generated_charts.append(str(out_file.relative_to(campaign_root)))

            optimal_row = {
                "generator_code": gen_code,
                "generator_file": tested.name,
                "test_num": cfg.test_num,
                "title": cfg.title,
                "best_p": best_p,
                "objective": best_row["objective"],
                "chart_ps": chart_ps,
                "chart_coords": list(cfg.chart_coords),
                "summary_csv": str((test_dir / "summary.csv").relative_to(campaign_root)),
                "charts": generated_charts,
            }
            all_optimal_rows.append(optimal_row)

    manifest_path = campaign_root / "generator_manifest.csv"
    with manifest_path.open("w", newline="", encoding="ascii") as f:
        writer = csv.DictWriter(f, fieldnames=["generator_code", "filename", "path"])
        writer.writeheader()
        writer.writerows(manifest_rows)

    optimal_csv = campaign_root / "optimal_p.csv"
    with optimal_csv.open("w", newline="", encoding="ascii") as f:
        writer = csv.writer(f)
        writer.writerow(["generator_code", "generator_file", "test_num", "title", "best_p", "objective", "chart_ps", "chart_coords", "summary_csv"])
        for row in all_optimal_rows:
            writer.writerow(
                [
                    row["generator_code"],
                    row["generator_file"],
                    row["test_num"],
                    row["title"],
                    row["best_p"],
                    row["objective"],
                    " ".join(str(x) for x in row["chart_ps"]),
                    " ".join(str(x) for x in row["chart_coords"]),
                    row["summary_csv"],
                ]
            )

    campaign_meta = {
        "campaign": args.campaign,
        "generator_dir": str(generator_dir),
        "generator_glob": args.generator_glob,
        "etalon": str(etalon),
        "rtest": str(rtest),
        "xor": args.xor,
        "tests": [asdict(cfg) for cfg in selected_tests],
        "results_root": str(campaign_root),
    }
    with (campaign_root / "campaign.json").open("w", encoding="ascii") as f:
        json.dump(campaign_meta, f, indent=2)

    print(f"Wrote {campaign_root}")
    print(f"Wrote {optimal_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
