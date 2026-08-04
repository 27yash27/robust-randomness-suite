#!/usr/bin/env python3
"""
KS diagnostics for rtest p-value streams.

WHY THIS SCRIPT EXISTS
======================

Built 2026-05-14 in response to Professor Shen's feedback Point #7, which
challenged the "XOR Amplification" finding in the Tests 32-41 XOR Sweep
Report (campaign `maxp_xor_32_41_20260509`).

Shen's hypothesis was that the apparent XOR-mode amplification of detection
hits had to be one of:
  (a) a faulty etalon -- BitBabbler `etal.bin` carrying a structural flaw
      that bleeds into results and creates false positives, or
  (b) a XOR / bit-consumption bug introducing artifacts.

The investigation report
  `My-robust-Test-Results/maximal_sweeps/XOR_METHODOLOGY_INVESTIGATION_20260514.md`
showed the real cause was a methodology reporting bug (the max_p sweep
reports `final_objective` at the file ceiling, missing the strongest signal
which lives at mid-p for tests 32-41). Two of the diagnostics in that
investigation were one-shot inline Python in `python3 -c` blocks, with no
saved script. This script makes those diagnostics reproducible so anyone
(Shen, future-us, a reviewer) can re-verify any cell of any campaign
without re-running rtest.

WHAT IT DOES
============

Given a path to one of the rtest output files
  `<campaign>/sweeps/<gen>/t<NN>/final_p<P>/000000.<test|etal>.<coord>`

it computes:

  * Basic stats (n, min, max, mean, std, unique value count)
  * One-sample KS distance against Uniform[0,1] -- the etalon-validation
    diagnostic. Reports the critical value at alpha=0.05 (1.36/sqrt(n)) so
    "do we reject uniformity?" is a glance.
  * If a second file is supplied, two-sample KS distance between them --
    the "two curves" check Shen recommended for validating a known-good
    generator's behavior in xor mode.

USAGE
=====

Single file -- check whether it is Uniform[0,1]:
  python3 ks_diagnostics_20260514.py path/to/000000.etal.0000

Two files -- compare them (the "two curves" check):
  python3 ks_diagnostics_20260514.py path/to/000000.test.0000 path/to/000000.etal.0000

REPRODUCIBILITY NOTE
====================

Uses only the Python standard library -- no numpy, no scipy. The KS formulas
implemented here are textbook (Kolmogorov 1933, Smirnov 1948); any reviewer
can verify the implementation against any KS reference. Critical-value
constant 1.36 is the Kolmogorov-distribution quantile for alpha=0.05.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path


def read_values(path: Path) -> list[float]:
    with path.open() as f:
        return [float(line.strip().split()[0]) for line in f if line.strip()]


def basic_stats(vals: list[float]) -> dict:
    n = len(vals)
    mean = sum(vals) / n
    var = sum((v - mean) ** 2 for v in vals) / n
    return {
        "n": n,
        "min": min(vals),
        "max": max(vals),
        "mean": mean,
        "std": math.sqrt(var),
        "unique": len(set(vals)),
    }


def ks_one_sample_uniform(vals: list[float]) -> float:
    """One-sample Kolmogorov-Smirnov statistic against Uniform[0,1].

    For sorted samples v_1 <= v_2 <= ... <= v_n the empirical CDF jumps from
    (i-1)/n to i/n at v_i. Since the uniform CDF G(x)=x is continuous, the
    sup |F_emp - G| is attained at one of the jump points. Check both sides
    of each jump because the empirical CDF is right-continuous.
    """
    sorted_vals = sorted(vals)
    n = len(sorted_vals)
    d = 0.0
    for i, v in enumerate(sorted_vals):
        post = (i + 1) / n  # F_emp just after v
        pre = i / n         # F_emp just before v
        d = max(d, abs(post - v), abs(pre - v))
    return d


def ks_two_sample(a: list[float], b: list[float]) -> float:
    """Two-sample Kolmogorov-Smirnov statistic: D = sup |F_a(x) - F_b(x)|.

    Standard merge-based computation: walk through both sorted samples
    incrementing whichever pointer has the smaller value, tracking the
    running difference of empirical CDFs.
    """
    a_sorted = sorted(a)
    b_sorted = sorted(b)
    na, nb = len(a_sorted), len(b_sorted)
    i = j = 0
    fa = fb = 0.0
    d = 0.0
    while i < na and j < nb:
        if a_sorted[i] <= b_sorted[j]:
            i += 1
            fa = i / na
        else:
            j += 1
            fb = j / nb
        d = max(d, abs(fa - fb))
    # Drain remaining points (the other side's CDF has reached 1.0)
    while i < na:
        i += 1
        fa = i / na
        d = max(d, abs(fa - fb))
    while j < nb:
        j += 1
        fb = j / nb
        d = max(d, abs(fa - fb))
    return d


def ks_critical_alpha_005(n: int) -> float:
    """Approximate critical value at alpha=0.05 for one-sample KS test."""
    return 1.36 / math.sqrt(n)


def ks_two_sample_critical_alpha_005(na: int, nb: int) -> float:
    """Approximate critical value at alpha=0.05 for two-sample KS test."""
    return 1.36 * math.sqrt((na + nb) / (na * nb))


def report_single(path: Path) -> None:
    vals = read_values(path)
    s = basic_stats(vals)
    d_uniform = ks_one_sample_uniform(vals)
    d_crit = ks_critical_alpha_005(s["n"])
    reject = d_uniform > d_crit

    print(f"File: {path}")
    print(f"  n             = {s['n']}")
    print(f"  unique values = {s['unique']} ({100*s['unique']/s['n']:.1f}% of n)")
    print(f"  min / max     = {s['min']:.6g} / {s['max']:.6g}")
    print(f"  mean          = {s['mean']:.6g}   (Uniform[0,1] expected: 0.5)")
    print(f"  std           = {s['std']:.6g}   (Uniform[0,1] expected: 0.288675 = 1/sqrt(12))")
    print()
    print(f"  KS distance from Uniform[0,1]:   D     = {d_uniform:.4f}")
    print(f"  Critical value at alpha=0.05:    D_c   = {d_crit:.4f}")
    if reject:
        print(f"  Verdict: REJECT uniformity at alpha=0.05 (D > D_c)")
    else:
        print(f"  Verdict: CANNOT reject uniformity at alpha=0.05 (D <= D_c)")
    print()


def report_pair(path_a: Path, path_b: Path) -> None:
    a = read_values(path_a)
    b = read_values(path_b)
    sa = basic_stats(a)
    sb = basic_stats(b)
    d_two = ks_two_sample(a, b)
    d_crit = ks_two_sample_critical_alpha_005(sa["n"], sb["n"])
    reject = d_two > d_crit

    print(f"File A (test): {path_a}")
    print(f"  n = {sa['n']}, unique = {sa['unique']}, "
          f"mean = {sa['mean']:.6g}, std = {sa['std']:.6g}, "
          f"min/max = {sa['min']:.6g}/{sa['max']:.6g}")
    print(f"File B (etal): {path_b}")
    print(f"  n = {sb['n']}, unique = {sb['unique']}, "
          f"mean = {sb['mean']:.6g}, std = {sb['std']:.6g}, "
          f"min/max = {sb['min']:.6g}/{sb['max']:.6g}")
    print()
    print("One-sample KS distance from Uniform[0,1]:")
    print(f"  D_A vs Uniform = {ks_one_sample_uniform(a):.4f}  "
          f"(D_c at n={sa['n']}: {ks_critical_alpha_005(sa['n']):.4f})")
    print(f"  D_B vs Uniform = {ks_one_sample_uniform(b):.4f}  "
          f"(D_c at n={sb['n']}: {ks_critical_alpha_005(sb['n']):.4f})")
    print()
    print("Two-sample KS distance (the 'two curves' check):")
    print(f"  D(A, B)        = {d_two:.4f}")
    print(f"  D_c at alpha=0.05 = {d_crit:.4f}")
    if reject:
        print(f"  Verdict: REJECT H0 'same distribution' at alpha=0.05 (D > D_c)")
    else:
        print(f"  Verdict: CANNOT reject 'same distribution' at alpha=0.05 (D <= D_c)")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("file_a", type=Path,
                        help="Path to first rtest output file (e.g. 000000.etal.0000)")
    parser.add_argument("file_b", type=Path, nargs="?",
                        help="(optional) Second file for two-sample KS comparison")
    args = parser.parse_args()

    if args.file_b is None:
        report_single(args.file_a)
    else:
        report_pair(args.file_a, args.file_b)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
