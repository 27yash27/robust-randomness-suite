#!/usr/bin/env python3
"""Focused checks for how run_all_experiments.py classifies rtest output.

    python3 scripts/check_classify.py

Covers the failure modes that matter: real end-of-input, a wrapped result
vector, a printed zero, a negative zero from cancellation, exactly one, an
out-of-range value, a non-finite token, and a diagnostic line that contains a
number. Exits non-zero if any case is classified wrongly.
"""

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("runner", HERE / "run_all_experiments.py")
runner = importlib.util.module_from_spec(spec)
sys.path.insert(0, str(HERE))
spec.loader.exec_module(runner)


class FakeResult:
    def __init__(self, stdout, returncode=0, stderr=""):
        self.stdout, self.returncode, self.stderr = stdout, returncode, stderr


CASES = [
    # stdout, dimension, expected status, expected first value
    ("0.70000000000000000\n", 1, "reported", 0.7),
    ("0.10000000 0.20000000 0.30000000\n0.40000000 0.50000000\n", 5, "reported", 0.1),
    ("0.000000000000000000\n", 1, "numerically_unresolved", 0.0),
    ("-0.000000000000000000\n", 1, "numerically_unresolved", -0.0),
    ("1.000000000000000000\n", 1, "exactly_one", 1.0),
    ("1.200000000000000000\n", 1, "out_of_range", None),
    ("nan 0.500000000000000000\n", 1, "no_output", None),
    ("oops, eof in generator 0\noops XOR in arg1 2\n", 1, "ran_out_of_data", None),
    ("threshold=0.010000\n0.700000000000000000\n", 1, "reported", 0.7),
    ("0.10000000 0.20000000\n", 5, "parse_error", None),
]


def main():
    failures = 0
    print(f"{'expected status':<26} {'got':<26} ok")
    for stdout, dim, want_status, want_value in CASES:
        status, value, _raw, _all = runner.classify(FakeResult(stdout), dim)
        ok = status == want_status and (
            want_value is None or (value is not None and value == want_value))
        print(f"{want_status:<26} {status:<26} {'yes' if ok else 'NO'}")
        if not ok:
            failures += 1

    # a failed diagnostic rerun must not be accepted as an explanation
    import subprocess
    real_run = subprocess.run
    try:
        subprocess.run = lambda *a, **k: FakeResult(
            "Random excursions: too few cycles (J=1 < 500.000000), aborting\n",
            returncode=1)
        status, _blob = runner.explain_empty_output(["rtest", "-x"], Path("."))
        ok = status == "no_output_unexplained"
        print(f"{'no_output_unexplained':<26} {status:<26} {'yes' if ok else 'NO'}"
              "   (failed diagnostic rerun)")
        if not ok:
            failures += 1
    finally:
        subprocess.run = real_run

    print()
    if failures:
        print(f"{failures} case(s) classified wrongly.")
        return 1
    print("All classification checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
