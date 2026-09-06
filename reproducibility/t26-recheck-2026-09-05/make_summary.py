#!/usr/bin/env python3
"""Print the full-sweep summary table from full-sweep/maximal_p.csv.

    python3 make_summary.py

The table in NOTES.md is produced by this, so the prose cannot drift from the
records. Values are shown as they appear in the CSV.
"""
import csv
from pathlib import Path

CSV = Path(__file__).resolve().parent / "full-sweep" / "maximal_p.csv"

NAMES = {
    "g01_blum_blum_shub": "Blum-Blum-Shub",
    "g02_cubic_congruential_1gb": "Cubic Congruential",
    "g03_g_using_sha": "G-using-SHA-1",
    "g04_linear_congruential_1gb": "Linear Congruential",
    "g05_micali_schnorr_1gb": "Micali-Schnorr",
    "g06_modular_exponentiation_1gb": "Modular Exponentiation",
    "g07_quadratic_congruential_ii": "Quadratic Congruential II",
    "g08_quadratic_congruential_i": "Quadratic Congruential I",
    "g09_xor_1gb": "XOR",
}

rows = sorted(csv.DictReader(CSV.open()), key=lambda r: r["generator_code"])
print("| Generator | max_p | final objective | status | beats 1e-10 |")
print("|---|---:|---|---|---|")
for r in rows:
    obj = r["final_objective"]
    try:
        obj = f"{float(obj):.6g}"
    except ValueError:
        pass
    print(f"| {NAMES.get(r['generator_code'], r['generator_code'])} "
          f"| {r['max_p']} | {obj} | {r['final_numeric_status']} "
          f"| {r['beats_threshold']} |")
