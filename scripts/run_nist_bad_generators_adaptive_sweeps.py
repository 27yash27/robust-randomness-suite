#!/usr/bin/env python3

import csv
import json
import re
import subprocess
import sys
from pathlib import Path


TEST_CONFIGS = {
    22: {"dimension": 31, "n": 2097161, "p_values": [3, 4, 5], "kind": "triple"},
    23: {"dimension": 1, "n": 0, "p_values": [100, 150, 200, 250, 300], "kind": "single_anyfloat"},
    24: {"dimension": 4, "n": 0, "p_values": [10, 20, 30, 40, 50], "kind": "triple_lastline"},
    25: {"dimension": 1, "n": 24000, "p_values": [10, 20, 30, 40, 50], "kind": "single_lastline"},
    26: {"dimension": 1, "n": 0, "p_values": [2, 3, 4, 5, 6], "kind": "single_lastline"},
}

FLOAT_RE = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?")
FLOAT_LINE_RE = re.compile(r"^\s*[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?(?:\s+[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)*\s*$")


def summarize(values: list[float]) -> tuple[float, float, float]:
    ordered = sorted(values)
    return ordered[0], ordered[len(ordered) // 2], ordered[-1]


def parse_output(test_num: int, stdout: str) -> dict[str, float]:
    kind = TEST_CONFIGS[test_num]["kind"]
    if kind == "triple":
        floats = [float(x) for x in FLOAT_RE.findall(stdout)]
        needed = TEST_CONFIGS[test_num]["dimension"]
        if len(floats) < needed:
            raise ValueError(f"expected at least {needed} floats, got {len(floats)}")
        mn, med, mx = summarize(floats[:needed])
        return {"min": mn, "median": med, "max": mx}

    if kind == "triple_lastline":
        numeric_lines = [line.strip() for line in stdout.splitlines() if FLOAT_LINE_RE.fullmatch(line)]
        if not numeric_lines:
            raise ValueError("expected numeric output line, got none")
        floats = [float(x) for x in numeric_lines[-1].split()]
        needed = TEST_CONFIGS[test_num]["dimension"]
        if len(floats) != needed:
            raise ValueError(f"expected {needed} floats, got {len(floats)}")
        mn, med, mx = summarize(floats)
        return {"min": mn, "median": med, "max": mx}

    if kind == "single_anyfloat":
        floats = [float(x) for x in FLOAT_RE.findall(stdout)]
        if not floats:
            raise ValueError("expected a float, got none")
        return {"pvalue": floats[0]}

    if kind == "single_lastline":
        numeric_lines = [line.strip() for line in stdout.splitlines() if FLOAT_LINE_RE.fullmatch(line)]
        if not numeric_lines:
            raise ValueError("expected numeric output line, got none")
        return {"pvalue": float(numeric_lines[-1])}

    raise ValueError(f"unknown parse kind: {kind}")


def step_down(p: int) -> int:
    if p >= 10:
        return p - 10
    return p - 1


def short_prefix(bin_path: Path) -> str:
    match = re.match(r"(\d+)\.?", bin_path.name)
    if not match:
        raise ValueError(f"could not extract numeric prefix from {bin_path.name}")
    return f"ra{match.group(1)}"


def run_one(repo_root: Path, tested: Path, etalon: Path, test_num: int, requested_p: int, actual_p: int) -> dict[str, object]:
    rel_output = Path("My-robust-Test-Results") / f"{short_prefix(tested)}_{test_num}" / f"req{requested_p:03d}_run{actual_p:03d}"
    (repo_root / rel_output.parent).mkdir(parents=True, exist_ok=True)

    cfg = TEST_CONFIGS[test_num]
    cmd = [
        str(repo_root / "robust" / "rtest"),
        "-x",
        "-f",
        str(tested),
        "-e",
        str(etalon),
        "-p",
        str(actual_p),
        "-q",
        str(actual_p),
        "-d",
        str(cfg["dimension"]),
        "-n",
        str(cfg["n"]),
        "-t",
        str(test_num),
        "-r",
        "1",
        "-o",
        str(rel_output),
    ]

    result = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True)
    combined = f"{result.stdout}\n{result.stderr}".lower()
    record: dict[str, object] = {
        "generator": tested.name,
        "test": test_num,
        "requested_p": requested_p,
        "actual_p": actual_p,
        "returncode": result.returncode,
        "output_dir": str(rel_output),
        "stdout": result.stdout,
        "stderr": result.stderr,
    }

    if "eof" in combined:
        record["status"] = "eof"
        return record

    try:
        parsed = parse_output(test_num, result.stdout)
    except ValueError as exc:
        record["status"] = "parse_error"
        record["parse_error"] = str(exc)
        return record

    record["status"] = "ok"
    record.update(parsed)
    return record


def cell_text(record: dict[str, object]) -> str:
    req = int(record["requested_p"])
    act = int(record["actual_p"])
    prefix = f"p=q={req}"
    if act != req:
        prefix += f" -> {act}"
    if TEST_CONFIGS[int(record["test"])]["kind"].startswith("triple"):
        return f"{prefix}: min={record['min']:.6g}"
    return f"{prefix}: {record['pvalue']:.6g}"


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent.parent
    results_root = repo_root / "My-robust-Test-Results" / "legacy" / "adaptive_runs"
    etalon = (Path.home() / "Downloads" / "etal.bin").resolve()
    tested_files = [
        repo_root / "My-RNG-Generators" / "NIST_Bad_Generators" / "1.bad_Linear_Congruential_100MB.bin",
        repo_root / "My-RNG-Generators" / "NIST_Bad_Generators" / "2. bad_Quadratic_Congruential_II_100MB.bin",
        repo_root / "My-RNG-Generators" / "NIST_Bad_Generators" / "3. bad_Quadratic_Congruential_I_100MB.bin",
        repo_root / "My-RNG-Generators" / "NIST_Bad_Generators" / "4. bad_Cubic_Congruential_100MB.bin",
        repo_root / "My-RNG-Generators" / "NIST_Bad_Generators" / "5. bad_XOR_100MB.bin",
        repo_root / "My-RNG-Generators" / "NIST_Bad_Generators" / "9. bad_G_Using_SHA-1_100MB.bin",
    ]

    if not etalon.is_file():
        print(f"etalon file not found: {etalon}", file=sys.stderr)
        return 1

    for path in tested_files:
        if not path.is_file():
            print(f"tested file not found: {path}", file=sys.stderr)
            return 1

    all_records: list[dict[str, object]] = []

    for tested in tested_files:
        print(f"Running {tested.name}")
        for test_num, cfg in TEST_CONFIGS.items():
            for requested_p in cfg["p_values"]:
                actual_p = requested_p
                while actual_p > 0:
                    record = run_one(repo_root, tested, etalon, test_num, requested_p, actual_p)
                    if record["status"] == "ok":
                        all_records.append(record)
                        print(f"  t{test_num} p=q={requested_p} -> {actual_p} ok")
                        break
                    if record["status"] == "eof":
                        next_p = step_down(actual_p)
                        print(f"  t{test_num} p=q={requested_p} hit EOF at {actual_p}, retrying {next_p}")
                        actual_p = next_p
                        continue
                    all_records.append(record)
                    print(f"  t{test_num} p=q={requested_p} parse failure at {actual_p}")
                    break
                else:
                    fail_record = {
                        "generator": tested.name,
                        "test": test_num,
                        "requested_p": requested_p,
                        "actual_p": "",
                        "status": "unresolved",
                    }
                    all_records.append(fail_record)

    out_dir = results_root
    long_json = out_dir / "nist_bad_generators_adaptive_results.json"
    long_csv = out_dir / "nist_bad_generators_adaptive_results.csv"
    wide_csv = out_dir / "nist_bad_generators_adaptive_summary_table.csv"

    with long_json.open("w", encoding="ascii") as f:
        json.dump(all_records, f, indent=2)

    with long_csv.open("w", newline="", encoding="ascii") as f:
        writer = csv.writer(f)
        writer.writerow(["generator", "test", "requested_p", "actual_p", "status", "min", "median", "max", "pvalue", "output_dir"])
        for r in all_records:
            writer.writerow([
                r.get("generator", ""),
                r.get("test", ""),
                r.get("requested_p", ""),
                r.get("actual_p", ""),
                r.get("status", ""),
                r.get("min", ""),
                r.get("median", ""),
                r.get("max", ""),
                r.get("pvalue", ""),
                r.get("output_dir", ""),
            ])

    grouped: dict[str, dict[int, list[dict[str, object]]]] = {}
    for r in all_records:
        if r.get("status") != "ok":
            continue
        grouped.setdefault(str(r["generator"]), {}).setdefault(int(r["test"]), []).append(r)

    with wide_csv.open("w", newline="", encoding="ascii") as f:
        writer = csv.writer(f)
        writer.writerow(["Generator", "Test 22", "Test 23", "Test 24", "Test 25", "Test 26"])
        for generator in [p.name for p in tested_files]:
            row = [generator]
            for test_num in [22, 23, 24, 25, 26]:
                records = sorted(grouped.get(generator, {}).get(test_num, []), key=lambda r: int(r["requested_p"]))
                row.append("; ".join(cell_text(r) for r in records))
            writer.writerow(row)

    print(long_json)
    print(long_csv)
    print(wide_csv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
    results_root.mkdir(parents=True, exist_ok=True)
