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
# A whole token that is a fixed-decimal number. Used with fullmatch so that
# "nan", "1.2e5x" or a word from a diagnostic cannot pass as a result.
RESULT_TOKEN_RE = re.compile(r"[-+]?\d+\.\d+")

FIXTURES = (
    ("random_like", "SHAKE256 stream, should look random",
     "shake_256(b'robust suite experiments v1')"),
    ("structured", "the ASCII bytes '0' and '1' repeated (0x30 0x31)",
     "b'01' repeated"),
)


# Bytes the tested generator consumes per unit of -p, measured with "rtest -r 2"
# on this catalog (the etalon consumes exactly half as much). Used to warn
# before a run that the chosen input size cannot support, rather than letting it
# surface later as an end-of-input that looks like a test limitation.
BYTES_PER_SAMPLE = {
    22: 16_777_304, 23: 512_024, 24: 2_048_048, 25: 192_016, 26: 18_447_383,
    27: 8_000_016, 28: 10_804_480, 29: 32_784, 30: 32_784, 31: 32_784,
    32: 8_000_016, 33: 8_000_016, 34: 96_016, 35: 800_016, 36: 16_016,
    37: 800_016, 38: 800_016, 39: 800_016, 40: 800_016, 41: 800_016,
}


def required_bytes(test_num, samples):
    """Tested-file bytes a run needs, or None if the test is not tabulated."""
    per = BYTES_PER_SAMPLE.get(test_num)
    return None if per is None else per * samples


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
# excursion cycles, which NIST specifies. The ASCII fixture triggers this: the
# bytes 0x30 0x31 carry five one-bits in every sixteen, so the random walk
# drifts steadily downward instead of returning to zero, and few cycles form.
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
    blob = (f"$ {' '.join(verbose)}\nreturncode: {r.returncode}\n"
            f"--- stdout ---\n{r.stdout}\n--- stderr ---\n{r.stderr}")
    if r.returncode != 0:
        # The diagnostic run itself failed, so its text is not trustworthy
        # evidence about why the first run was silent.
        return "no_output_unexplained", blob
    for needle, status in KNOWN_DECLINES:
        if needle in r.stdout or needle in r.stderr:
            return status, blob
    return "no_output_unexplained", blob


def classify(result, dimension):
    """Return (status, p_value_or_None, raw_string)."""
    if result.returncode != 0:
        return ("process_failure", None, "", [])
    if "oops" in result.stdout or "oops" in result.stderr:
        return ("ran_out_of_data", None, "", [])
    # rtest prints the p-value vector as whitespace-separated fixed-decimal
    # numbers, five per line. Take only lines that are entirely such numbers, so
    # a diagnostic line cannot contribute a value, and require the exact count.
    values, raw_tokens = [], []
    for line in result.stdout.splitlines():
        tokens = line.split()
        if not tokens:
            continue
        if all(RESULT_TOKEN_RE.fullmatch(t) for t in tokens):
            raw_tokens.extend(tokens)
            values.extend(float(t) for t in tokens)
        elif values:
            # numbers already seen, then something else: stop rather than
            # stitching unrelated text onto the result vector
            break

    if not raw_tokens:
        # Empty output is not self-explaining, so it is not accepted as a
        # decline on its own. The caller re-runs with -v and only a recognised
        # refusal is treated as one; anything else fails visibly.
        return ("no_output", None, "", [])
    if len(values) != dimension:
        return ("parse_error", None, " ".join(raw_tokens[:4]), [])
    if not all(math.isfinite(v) for v in values):
        return ("numerical_failure", None, raw_tokens[0], values)
    if not all(0.0 <= v <= 1.0 for v in values):
        # a p-value outside [0,1] is not a p-value
        return ("out_of_range", None, raw_tokens[0], values)

    raw = raw_tokens[0]
    value = values[0]
    if value <= 0.0:
        # A printed zero says the value fell below the driver's fixed-decimal
        # output, nothing more. It is not a measured detection and not a bound.
        return ("numerically_unresolved", value, raw, values)
    if value == 1.0:
        return ("exactly_one", value, raw, values)
    return ("reported", value, raw, values)


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

    # Say up front which planned runs the chosen input size cannot support.
    undersized = []
    for tnum in tests:
        for size in list(TEST_CATALOG[tnum].p_values)[:a.max_sizes]:
            need = required_bytes(tnum, size)
            if need is not None and need > size_bytes:
                undersized.append((tnum, size, need))
    if undersized:
        print(f"note: {len(undersized)} planned run(s) need more than the "
              f"{a.size_mb} MB inputs and will stop at end of input:")
        for tnum, size, need in undersized:
            print(f"   test {tnum} at p=q={size} needs {need/1e6:.0f} MB")
        biggest = max(n for _t, _s, n in undersized)
        print(f"   pass --size-mb {int(biggest/1e6) + 1} to cover all of them.\n")

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
            "coordinate_plotted", "all_coordinates", "curve",
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
                    status, value, raw, all_values = classify(r, cfg.dimension)
                    if status == "no_output":
                        status, explain = explain_empty_output(cmd, out)
                        (out / stdout_rel).write_text(
                            r.stdout + r.stderr
                            + "\n--- re-run with -v to explain empty output ---\n"
                            + explain)

                    # The curves depend on the saved statistic samples, not on
                    # whether the p-value could be reported. A run whose value is
                    # zero or one still has two complete distributions worth
                    # looking at, so it is drawn and annotated rather than
                    # dropped from the family.
                    coord = cfg.chart_coords[0]
                    sd = out / sample_dir
                    curve = "not attempted"
                    if status in ("reported", "numerically_unresolved", "exactly_one"):
                        try:
                            tv = renderer.read_values(sd / f"000000.test.{coord:04d}")
                            ev = renderer.read_values(sd / f"000000.etal.{coord:04d}")
                        except (OSError, ValueError) as exc:
                            curve = f"samples unreadable: {exc}"
                        else:
                            if len(tv) != size or len(ev) != size:
                                curve = (f"sample count mismatch: {len(tv)}/{len(ev)} "
                                         f"where {size} expected")
                            elif not (all(math.isfinite(x) for x in tv)
                                      and all(math.isfinite(x) for x in ev)):
                                curve = "non-finite values in samples"
                            else:
                                panels.append((size, value if value is not None else 0.0,
                                               tv, ev))
                                ok_runs += 1
                                curve = "drawn"

                    all_statuses.append(status)
                    w.writerow({
                        "test_num": tnum, "title": cfg.title, "fixture": fixture,
                        "dimension": cfg.dimension, "n_value": cfg.n_value,
                        "modifier": cfg.modifier if cfg.modifier is not None else "",
                        "samples": size, "xor": True, "ks_backend": backend,
                        "p_value_raw": raw, "numeric_status": status,
                        "coordinate_plotted": coord,
                        "all_coordinates": " ".join(f"{v:.18f}" for v in all_values),
                        "curve": curve,
                        "returncode": r.returncode, "repo_revision": revision,
                        "command": json.dumps(cmd), "stdout_file": str(stdout_rel)})
                    f.flush()
                    print(f"   {fixture:<12} p={size:<6} {status:<24} "
                          f"curve={curve:<12} {raw or ''}")
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
