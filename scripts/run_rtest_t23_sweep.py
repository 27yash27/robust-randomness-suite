#!/usr/bin/env python3

import argparse
import csv
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path


TEST_NUM = 23
DIMENSION = 1
N_VALUE = 0
FLOAT_RE = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?")


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parent.parent.parent
    default_results_root = repo_root / "My-robust-Test-Results" / "manual_sweeps"
    parser = argparse.ArgumentParser(
        description="Sweep rtest -t 23 (Count the 1s in a stream of bytes)."
    )
    parser.add_argument(
        "--tested",
        required=True,
        type=Path,
        help="Path to the tested binary",
    )
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
        default=default_results_root / "sweeps_t23",
        type=Path,
        help="Directory where per-run outputs and summaries are written",
    )
    parser.add_argument(
        "--p-values",
        nargs="+",
        type=int,
        default=[100, 150, 200],
        help="List of p=q sample counts to try",
    )
    parser.add_argument(
        "--xor",
        action="store_true",
        help="Pass -x so the comparison side uses tested xor etalon",
    )
    parser.add_argument(
        "--keep-going",
        action="store_true",
        help="Continue even if one sweep point fails",
    )
    return parser.parse_args()


def parse_single_pvalue(stdout: str) -> float:
    floats = [float(x) for x in FLOAT_RE.findall(stdout)]
    if not floats:
        raise ValueError("Expected at least one floating-point output, got none")
    return floats[0]


def run_one(
    rtest: Path,
    tested: Path,
    etalon: Path,
    output_dir: Path,
    p: int,
    use_xor: bool,
) -> dict[str, object]:
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
            record["pvalue"] = parse_single_pvalue(result.stdout)
        except ValueError as exc:
            record["returncode"] = 2
            record["parse_error"] = str(exc)
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
    if etalon.stat().st_size == 0:
        print(f"etalon file is empty: {etalon}", file=sys.stderr)
        return 1

    output_root.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []

    print("Python is driving shell commands for you here.")
    print("For -t 23, the script fixes the required settings: -d 1 -n 0.")
    print()

    for p in args.p_values:
        run_dir = output_root / f"t23_p{p:04d}"
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
            print(f"pvalue: {record['pvalue']:.9g}")
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
        writer.writerow(["p", "returncode", "pvalue", "output_dir"])
        for record in records:
            writer.writerow(
                [
                    record.get("p", ""),
                    record.get("returncode", ""),
                    record.get("pvalue", ""),
                    record.get("output_dir", ""),
                ]
            )

    print(f"Wrote {summary_json}")
    print(f"Wrote {summary_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
