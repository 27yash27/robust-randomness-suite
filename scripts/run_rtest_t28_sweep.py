#!/usr/bin/env python3

import argparse
import csv
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path


TEST_NUM = 28
DIMENSION = 2
N_VALUE = 0
FLOAT_LINE_RE = re.compile(
    r"^\s*[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
    r"(?:\s+[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)*\s*$"
)


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parent.parent.parent
    default_results_root = repo_root / "My-robust-Test-Results" / "manual_sweeps"
    parser = argparse.ArgumentParser(
        description="Sweep rtest -t 28 (Diehard Craps)."
    )
    parser.add_argument("--tested", required=True, type=Path, help="Path to the tested binary")
    parser.add_argument(
        "--etalon",
        default=Path.home() / "Downloads" / "etal.bin",
        type=Path,
        help="Path to the etalon file. Default: ~/Downloads/etal.bin",
    )
    parser.add_argument(
        "--rtest",
        default=repo_root / "robust" / "rtest",
        type=Path,
        help="Path to the robust/rtest executable",
    )
    parser.add_argument(
        "--output-root",
        default=default_results_root / "sweeps_t28",
        type=Path,
        help="Directory where per-run outputs and summaries are written",
    )
    parser.add_argument(
        "--p-values",
        nargs="+",
        type=int,
        default=[5, 10, 15],
        help="List of p=q sample counts to try",
    )
    parser.add_argument("--xor", action="store_true", help="Pass -x so the comparison side uses tested xor etalon")
    parser.add_argument("--keep-going", action="store_true", help="Continue even if one sweep point fails")
    return parser.parse_args()


def parse_pvalues(stdout: str) -> list[float]:
    numeric_lines = [line.strip() for line in stdout.splitlines() if FLOAT_LINE_RE.fullmatch(line)]
    if not numeric_lines:
        raise ValueError("Expected a numeric output line, got none")
    floats = [float(x) for x in numeric_lines[-1].split()]
    if len(floats) != DIMENSION:
        raise ValueError(f"Expected {DIMENSION} p-values, got {len(floats)}")
    return floats


def summarize(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    return {"min": ordered[0], "median": ordered[len(ordered) // 2], "max": ordered[-1]}


def run_one(rtest: Path, tested: Path, etalon: Path, output_dir: Path, p: int, use_xor: bool) -> dict[str, object]:
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
        str(DIMENSION),
        "-n",
        str(N_VALUE),
        "-t",
        str(TEST_NUM),
        "-r",
        "1",
        "-o",
        str(output_dir),
    ]
    if use_xor:
        cmd.insert(1, "-x")

    result = subprocess.run(cmd, capture_output=True, text=True)
    record: dict[str, object] = {
        "command": cmd,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "p": p,
        "output_dir": str(output_dir),
    }
    if result.returncode == 0:
        try:
            values = parse_pvalues(result.stdout)
        except ValueError as exc:
            record["returncode"] = 2
            record["parse_error"] = str(exc)
        else:
            record["pvalues"] = values
            record.update(summarize(values))
    return record


def main() -> int:
    args = parse_args()
    tested = args.tested.expanduser().resolve()
    etalon = args.etalon.expanduser().resolve()
    rtest = args.rtest.expanduser().resolve()
    output_root = args.output_root.expanduser().resolve()

    if not rtest.is_file():
        print(f"rtest not found: {rtest}", file=sys.stderr)
        return 1
    if not tested.is_file():
        print(f"tested file not found: {tested}", file=sys.stderr)
        return 1
    if not etalon.is_file():
        print(f"etalon file not found: {etalon}", file=sys.stderr)
        return 1

    output_root.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []

    print("Python is driving rtest for test 28.")
    print("For -t 28, the script fixes the required settings: -d 2 -n 0.")
    print()

    for p in args.p_values:
        run_dir = output_root / f"t28_p{p:03d}"
        if run_dir.exists():
            print(f"Skipping existing output directory: {run_dir}")
            continue

        record = run_one(rtest, tested, etalon, run_dir, p, args.xor)
        records.append(record)

        cmd_text = " ".join(shlex.quote(part) for part in record["command"])
        print(f"p=q={p}")
        print(f"command: {cmd_text}")
        print(f"returncode: {record['returncode']}")
        if record["returncode"] == 0:
            print(
                "summary: "
                f"min={record['min']:.6g} "
                f"median={record['median']:.6g} "
                f"max={record['max']:.6g}"
            )
        else:
            print("stderr:")
            print(record["stderr"].rstrip())
            if record.get("parse_error"):
                print("parse_error:")
                print(record["parse_error"])
            if not args.keep_going:
                break
        print()

    summary_json = output_root / "summary.json"
    summary_csv = output_root / "summary.csv"

    with summary_json.open("w", encoding="ascii") as f:
        json.dump(records, f, indent=2)

    with summary_csv.open("w", newline="", encoding="ascii") as f:
        writer = csv.writer(f)
        writer.writerow(["p", "returncode", "min", "median", "max", "output_dir"])
        for record in records:
            writer.writerow(
                [
                    record.get("p", ""),
                    record.get("returncode", ""),
                    record.get("min", ""),
                    record.get("median", ""),
                    record.get("max", ""),
                    record.get("output_dir", ""),
                ]
            )

    print(f"Wrote {summary_json}")
    print(f"Wrote {summary_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
