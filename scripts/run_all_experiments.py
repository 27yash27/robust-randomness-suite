#!/usr/bin/env python3
"""Run every added test (22-41) on deterministic inputs and draw its curves.

    python3 scripts/run_all_experiments.py --repo . --out ../experiments

For each of the twenty tests this runs the statistic at the sample sizes fixed
in scripts/robust_test_catalog.py, against two generators built from recorded
recipes: one that should look random and one that should not. It writes one SVG
per test showing the compared distributions at each sample size, plus a CSV with
the exact command, revision, backend, raw p-value and numeric status of every
run.

Nothing here is selected after the fact: the tests, the sample sizes and the
inputs are all fixed before the first run. This demonstrates the workflow on
inputs anyone can rebuild. It is not the nine-generator validation campaign,
which is preserved separately under reproducibility/.

Standard library only.
"""

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import platform
import re
import subprocess
import sys
from pathlib import Path

FLOAT_RE = re.compile(r"[-+]?(?:\d+\.\d*|\.\d+)(?:[eE][-+]?\d+)?")

FIXTURES = (
    ("random_like", "SHAKE256 stream, should look random",
     "shake_256(b'robust suite experiments v1')"),
    ("structured", "the bytes 01 repeated, should be detected",
     "b'01' repeated"),
)


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git(repo, *args):
    p = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    return p.stdout.strip() if p.returncode == 0 else None


def parse_args():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", type=Path, default=Path.cwd(),
                    help="built repository checkout")
    ap.add_argument("--out", type=Path, required=True,
                    help="new directory for all outputs")
    ap.add_argument("--size-mb", type=int, default=200,
                    help="size of each generated input in MB (default 200). "
                         "The heavier tests need a few hundred MB; raise this "
                         "if you see 'ran out of data'.")
    ap.add_argument("--tests", nargs="+", type=int, default=None,
                    help="restrict to these test numbers (default: all 22-41)")
    ap.add_argument("--max-sizes", type=int, default=5,
                    help="how many of the catalog's sample sizes to use (default 5)")
    ap.add_argument("--ksexact", action="store_true",
                    help="pass -k for the exact KS routine. Slower, but the "
                         "default routine underflows at large sample sizes on "
                         "some platforms.")
    return ap.parse_args()


def build_inputs(inputs_dir, size_bytes):
    rows = []
    for name, role, recipe in FIXTURES:
        path = inputs_dir / f"{name}.bin"
        if name == "structured":
            data = b"01" * (size_bytes // 2)
        else:
            data = hashlib.shake_256(b"robust suite experiments v1").digest(size_bytes)
        path.write_bytes(data)
        del data
        rows.append({"file": path.name, "role": role, "size_bytes": size_bytes,
                     "sha256": sha256(path), "recipe": recipe})
    # the fixed reference; its quality does not affect validity, only its size
    ref = inputs_dir / "reference.bin"
    ref.write_bytes(hashlib.shake_256(b"robust suite reference v1").digest(size_bytes))
    rows.append({"file": ref.name, "role": "fixed XOR reference (etalon)",
                 "size_bytes": size_bytes, "sha256": sha256(ref),
                 "recipe": "shake_256(b'robust suite reference v1')"})
    return rows, ref


# Refusals a statistic is documented to make, matched against its own -v output.
# Random Excursions and its variant abort when the stream yields too few
# excursion cycles, which NIST specifies.
KNOWN_DECLINES = (
    ("too few cycles", "statistic_declined_too_few_cycles"),
)


def explain_empty_output(cmd, cwd):
    """Re-run with -v and name the refusal, or report it as unexplained."""
    # Drop -o and its value: rtest creates that directory and refuses to run if
    # it already exists, which the first pass has just made it do.
    verbose, skip = [], False
    for arg in cmd:
        if skip:
            skip = False
            continue
        if arg == "-o":
            skip = True
            continue
        verbose.append(arg)
    verbose.insert(1, "-v")
    r = subprocess.run(verbose, cwd=cwd, capture_output=True, text=True)
    blob = r.stdout + r.stderr
    for needle, status in KNOWN_DECLINES:
        if needle in blob:
            return status, blob
    return "no_output_unexplained", blob


def classify(result, dimension):
    """Return (status, p_value_or_None, raw_string)."""
    if result.returncode != 0:
        return ("process_failure", None, "")
    if "oops" in result.stdout or "oops" in result.stderr:
        return ("ran_out_of_data", None, "")
    found = FLOAT_RE.findall(result.stdout)
    if not found:
        # Empty output is not self-explaining, so it is not accepted as a
        # decline on its own. The caller re-runs with -v and only a recognised
        # refusal is treated as one; anything else fails visibly.
        return ("no_output", None, "")
    if len(found) < dimension:
        return ("parse_error", None, "")
    raw = found[0]
    value = float(raw)
    if not math.isfinite(value):
        return ("numerical_failure", None, raw)
    if value <= 0.0:
        # below the driver's 18-decimal printing floor, or a small negative from
        # cancellation in the default kernel. Either way the true value is not
        # known, so it is not reported as a measured detection.
        return ("below_printing_floor", value, raw)
    if value >= 1.0:
        return ("exactly_one", value, raw)
    return ("reported", value, raw)


def main():
    a = parse_args()
    repo, out = a.repo.resolve(), a.out.resolve()
    rtest = repo / "robust" / "rtest"
    renderer_path = repo / "scripts" / "compare_curves.py"
    if not rtest.is_file():
        sys.exit(f"no rtest binary at {rtest}; run 'make' in robust/ first")
    if out.exists():
        sys.exit(f"{out} already exists; choose a new directory")

    sys.path.insert(0, str(repo / "scripts"))
    from robust_test_catalog import TEST_CATALOG
    spec = importlib.util.spec_from_file_location("renderer", renderer_path)
    renderer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(renderer)

    tests = sorted(a.tests) if a.tests else sorted(TEST_CATALOG)
    size_bytes = a.size_mb * 1_000_000

    out.mkdir(parents=True)
    inputs, curves, logs = out / "inputs", out / "curves", out / "logs"
    for d in (inputs, curves, logs):
        d.mkdir()

    print(f"building {len(FIXTURES) + 1} inputs of {a.size_mb} MB ...")
    input_rows, reference = build_inputs(inputs, size_bytes)
    with (out / "input_manifest.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(input_rows[0]))
        w.writeheader(); w.writerows(input_rows)

    revision = git(repo, "rev-parse", "HEAD")
    backend = "exact-gmp (-k)" if a.ksexact else "default-psmirnov2x"
    (out / "provenance.json").write_text(json.dumps({
        "purpose": "Runnable experiments for tests 22-41 on deterministic inputs. "
                   "Not the nine-generator validation campaign.",
        "repo_revision": revision,
        "uncommitted_changes": git(repo, "diff", "HEAD", "--stat") or "",
        "rtest_sha256": sha256(rtest),
        "ks_backend": backend,
        "xor": True,
        "input_size_bytes": size_bytes,
        "tests": tests,
        "sample_sizes_from": "scripts/robust_test_catalog.py, fixed in advance",
        "python": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
    }, indent=2) + "\n")

    cols = ["test_num", "title", "fixture", "dimension", "n_value", "modifier",
            "samples", "xor", "ks_backend", "p_value_raw", "numeric_status",
            "returncode", "repo_revision", "command", "stdout_file"]
    summary = []
    incomplete = []
    all_statuses = []

    with (out / "results.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for tnum in tests:
            cfg = TEST_CATALOG[tnum]
            sizes = list(cfg.p_values)[:a.max_sizes]
            print(f"\ntest {tnum}: {cfg.title}")
            per_fixture_panels = {}
            for fixture, _role, _recipe in FIXTURES:
                panels, ok_runs = [], 0
                for size in sizes:
                    tag = f"t{tnum:02d}_{fixture}_p{size}"
                    sample_dir = Path("curves") / tag
                    cmd = [str(rtest), "-x"]
                    if a.ksexact:
                        cmd.append("-k")
                    cmd += ["-f", str(inputs / f"{fixture}.bin"), "-e", str(reference),
                            "-t", str(tnum), "-d", str(cfg.dimension),
                            "-n", str(cfg.n_value), "-p", str(size), "-q", str(size),
                            "-r", "1", "-o", str(sample_dir)]
                    if cfg.modifier is not None:
                        cmd += ["-m", str(cfg.modifier)]
                    r = subprocess.run(cmd, cwd=out, capture_output=True, text=True)
                    stdout_rel = Path("logs") / f"{tag}.txt"
                    (out / stdout_rel).write_text(r.stdout + r.stderr)
                    status, value, raw = classify(r, cfg.dimension)
                    if status == "no_output":
                        status, explain = explain_empty_output(cmd, out)
                        (out / stdout_rel).write_text(
                            r.stdout + r.stderr
                            + "\n--- re-run with -v to explain empty output ---\n"
                            + explain)
                    all_statuses.append(status)
                    w.writerow({
                        "test_num": tnum, "title": cfg.title, "fixture": fixture,
                        "dimension": cfg.dimension, "n_value": cfg.n_value,
                        "modifier": cfg.modifier if cfg.modifier is not None else "",
                        "samples": size, "xor": True, "ks_backend": backend,
                        "p_value_raw": raw, "numeric_status": status,
                        "returncode": r.returncode, "repo_revision": revision,
                        "command": " ".join(cmd), "stdout_file": str(stdout_rel)})
                    f.flush()
                    if status == "reported":
                        coord = cfg.chart_coords[0]
                        sd = out / sample_dir
                        try:
                            tv = renderer.read_values(sd / f"000000.test.{coord:04d}")
                            ev = renderer.read_values(sd / f"000000.etal.{coord:04d}")
                            panels.append((size, value, tv, ev))
                            ok_runs += 1
                        except (OSError, ValueError):
                            pass
                    print(f"   {fixture:<12} p={size:<6} {status:<22} {raw or ''}")
                per_fixture_panels[fixture] = (panels, ok_runs)
                if ok_runs == 0:
                    incomplete.append((tnum, fixture))

            for fixture, (panels, _n) in per_fixture_panels.items():
                if panels:
                    svg = renderer.build_svg(
                        f"Test {tnum}: {cfg.title} - {fixture}",
                        f"sample sizes fixed in advance; {backend}; "
                        f"blue tested, orange tested XOR reference", panels)
                    (out / f"test{tnum:02d}_{fixture}.svg").write_text(svg)
            summary.append((tnum, cfg.title,
                            per_fixture_panels["random_like"][1],
                            per_fixture_panels["structured"][1]))

    print("\n" + "=" * 62)
    print(f"{'test':<6}{'title':<34}{'random':>8}{'structured':>12}")
    for tnum, title, a_ok, b_ok in summary:
        print(f"{tnum:<6}{title[:32]:<34}{a_ok:>8}{b_ok:>12}")
    print(f"\noutputs: {out}")
    # Real problems, as opposed to a statistic declining or wanting more data.
    hard = [r for r in all_statuses
            if r in ("process_failure", "parse_error", "numerical_failure",
                     "no_output_unexplained")]
    if incomplete:
        print(f"\n{len(incomplete)} test/fixture pairs produced no curves:")
        for tnum, fixture in incomplete:
            print(f"   test {tnum} / {fixture}")
        print("Check numeric_status in results.csv. "
              "'statistic_declined_too_few_cycles' is the test saying so itself, "
              "confirmed from its own -v output, and is expected for Random "
              "Excursions on a perfectly balanced stream. 'ran_out_of_data' means "
              "raise --size-mb. 'no_output_unexplained' is a real failure.")
    if hard:
        print(f"\n{len(hard)} runs failed for reasons that need looking at.")
        return 1
    print("\nNo run failed unexpectedly.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
