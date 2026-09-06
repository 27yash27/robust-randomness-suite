#!/usr/bin/env python3
"""Generate a small, reproducible demonstration of robust randomness testing.

From an already built robust-randomness-suite checkout:
    python3 /path/to/reproduce_randomness_demo.py --repo . --out ../randomness-demo

Uses Python's standard library and the repository's rtest and SVG renderer.
Creates three deterministic 20 MB inputs, ten runs of test 37, two SVG plots,
results.csv, input_manifest.csv, raw logs/samples, and provenance.json.
The output directory must not already exist. Keep generated inputs outside Git.

These illustrative fixtures do not reproduce the historical nine-generator
research campaign or estimate a false-positive rate. All sample counts are
fixed in advance. No significance claim is made from a selected minimum.
"""

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import platform
from pathlib import Path
import subprocess
import sys

BYTES = 20_000_000
SIZES = (2, 5, 10, 15, 20)
TEST = 37
DIMENSION = 1
N_WORDS = 100_000


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def git_output(repo, *args):
    p = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True)
    return p.stdout.strip() if p.returncode == 0 else None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--repo', type=Path, default=Path.cwd(), help='Built repository checkout')
    ap.add_argument('--out', type=Path, required=True, help='New directory for all outputs')
    a = ap.parse_args()
    repo, out = a.repo.resolve(), a.out.resolve()
    rtest = repo / 'robust/rtest'
    renderer_path = repo / 'scripts/compare_curves.py'
    if not rtest.is_file() or not renderer_path.is_file():
        ap.error('Expected robust/rtest and scripts/compare_curves.py; build the checkout first.')
    if out.exists():
        ap.error('Output directory already exists; choose a new directory.')

    # Reuse the repository renderer, while running rtest ourselves so that
    # exact mode, raw output, and complete per-run metadata are recorded.
    sys.path.insert(0, str(repo / 'scripts'))
    spec = importlib.util.spec_from_file_location('demo_curve_renderer', renderer_path)
    renderer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(renderer)

    out.mkdir(parents=True)
    inputs, runs, logs = out / 'inputs', out / 'runs', out / 'logs'
    for directory in (inputs, runs, logs):
        directory.mkdir()

    input_rows = []
    for name, role, recipe in (
        ('reference.bin', 'fixed XOR reference', 'rtest review etalon v1'),
        ('shake_fixture.bin', 'SHAKE256 demonstration fixture', 'rtest review tested v1'),
        ('ascii_fixture.bin', 'structured ASCII demonstration fixture', 'ASCII 01 repeated'),
    ):
        data = b'01' * (BYTES // 2) if name == 'ascii_fixture.bin' else hashlib.shake_256(recipe.encode('ascii')).digest(BYTES)
        path = inputs / name
        path.write_bytes(data)
        input_rows.append(dict(file=str(path.relative_to(out)), role=role,
                               size_bytes=BYTES, sha256=digest(path), recipe=recipe))
        del data
    with (out / 'input_manifest.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(input_rows[0]))
        writer.writeheader()
        writer.writerows(input_rows)

    revision = git_output(repo, 'rev-parse', 'HEAD')
    source_diff = git_output(repo, 'diff', 'HEAD', '--', 'robust', 'scripts', 'kolmogorov-smirnov', 'general', 'spectral_tests')
    provenance = dict(
        purpose='Illustrative deterministic demo; not the historical nine-generator campaign',
        repo_revision=revision, tracked_source_diff=source_diff,
        binary_sha256=digest(rtest), renderer_sha256=digest(renderer_path),
        python=sys.version, platform=platform.platform(), machine=platform.machine(),
        ks_backend='GMP (-k), including the upstream output/conversion limitations',
        xor=True, test=TEST, dimension=DIMENSION, n_words=N_WORDS,
        fixed_sample_sizes=list(SIZES), inputs=input_rows,
        numeric_policy='Keep raw values and statuses. Zero/negative/nonfinite results are unresolved; no automatic detection claim.',
        environment_note='Compiler, linked library versions and build flags should accompany a publication campaign.',
    )
    (out / 'provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')

    columns = ['fixture', 'test', 'dimension', 'n_words', 'samples_test',
               'samples_reference', 'xor', 'ks_backend', 'p_value_raw',
               'numeric_status', 'returncode', 'repo_revision', 'command_json',
               'stdout_file', 'stderr_file', 'samples_directory']
    failures = 0
    with (out / 'results.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for fixture in ('shake_fixture', 'ascii_fixture'):
            panels = []
            for size in SIZES:
                tag = f'{fixture}_n{size}'
                rel_samples = Path('runs') / tag
                cmd = [str(rtest), '-x', '-k', '-f', str(inputs / f'{fixture}.bin'),
                       '-e', str(inputs / 'reference.bin'), '-t', str(TEST),
                       '-d', str(DIMENSION), '-n', str(N_WORDS),
                       '-p', str(size), '-q', str(size), '-r', '1', '-o', str(rel_samples)]
                result = subprocess.run(cmd, cwd=out, capture_output=True, text=True, timeout=120)
                stdout_rel, stderr_rel = Path('logs') / f'{tag}.stdout', Path('logs') / f'{tag}.stderr'
                (out / stdout_rel).write_text(result.stdout)
                (out / stderr_rel).write_text(result.stderr)
                raw, value = '', None
                if result.returncode != 0:
                    status = 'process_failure'
                elif 'oops' in result.stdout or 'oops' in result.stderr:
                    status = 'eof'
                elif 'unresolved tie' in result.stderr:
                    status = 'unresolved_tie'
                else:
                    tokens = result.stdout.split()
                    try:
                        if len(tokens) != 1:
                            raise ValueError('Expected one coordinate')
                        raw, value = tokens[0], float(tokens[0])
                        if not math.isfinite(value) or value < 0 or value > 1:
                            status = 'numerical_failure'
                        elif value == 0:
                            status = 'zero_unresolved'
                        else:
                            status = 'finite_reported'
                    except ValueError:
                        status = 'parse_error'
                if status == 'finite_reported':
                    sample_dir = out / rel_samples
                    tested = renderer.read_values(sample_dir / '000000.test.0000')
                    reference = renderer.read_values(sample_dir / '000000.etal.0000')
                    if len(tested) != size or len(reference) != size:
                        status = 'incomplete_samples'
                    else:
                        panels.append((size, value, tested, reference))
                if status != 'finite_reported':
                    failures += 1
                writer.writerow(dict(
                    fixture=fixture, test=TEST, dimension=DIMENSION, n_words=N_WORDS,
                    samples_test=size, samples_reference=size, xor=True, ks_backend='GMP (-k)',
                    p_value_raw=raw, numeric_status=status, returncode=result.returncode,
                    repo_revision=revision, command_json=json.dumps(cmd),
                    stdout_file=str(stdout_rel), stderr_file=str(stderr_rel),
                    samples_directory=str(rel_samples)))
                f.flush()
                print(f'{fixture}: samples={size}, p={raw or "unavailable"}, status={status}', flush=True)
            if panels:
                svg = renderer.build_svg(f'Test 37: Runs — {fixture}',
                                         'Fixed sample counts; blue: tested, orange: tested XOR reference; GMP (-k)', panels)
                (out / f'{fixture}.svg').write_text(svg)
    print(f'Outputs: {out}')
    print('Demo checks execution and produces evidence; it does not certify a generator or reproduce the historical campaign.')
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
