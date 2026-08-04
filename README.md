# Robust randomness testing suite

A complete suite of statistical tests for random-bit generators that reports
**valid p-values** — without the approximation assumptions that make ordinary
randomness tests hard to interpret. It extends Alexander Shen's
[`rtest`](https://github.com/alexander-shen/rtest) framework from 21 to **41
test families**, covering the full Diehard battery and about 93% of NIST STS.

Most randomness tests report a p-value derived from an asymptotic approximation
with no proven error bound. When that number is small you can't tell whether the
generator is genuinely bad or the approximation is just inaccurate at your sample
size. This suite uses Shen's **two-sample construction** instead: for a test
statistic `t`, it compares `t` on your generator against `t` on your generator
XOR-ed with a fixed reference sequence, and compares the two samples with a
Kolmogorov–Smirnov test. If the generator is random, so is its XOR with anything
fixed, so the two samples must match — and the p-value is valid with no
distributional assumption. Background:

- https://hal.archives-ouvertes.fr/lirmm-03065320/
- https://hal.archives-ouvertes.fr/lirmm-03371151/

## What's in here

```
robust/               the test driver and all 41 test statistics
  rtest.c               main program: parses arguments, runs a test, does the KS comparison
  generators.c/.h       generator interface (reads a file of bits; computes the XOR)
  test_func.c/.h        the registry mapping test numbers 0–41 to their code
  test_*.c              one file per statistic (some define several tests)
  Makefile              build definition
  rtest1m.sh … 10g.sh   preset test batteries for 1 MB / 10 MB / 100 MB / 1 GB / 10 GB files
  doc/                  tests-description.tex (tests 0–21), expansion-notes.txt (tests 22–41)
kolmogorov-smirnov/   the KS math engine: one- and two-sample tests, a multiprecision
                      (GMP) backup for exact values, and the ECDF plotting utilities
data/                 a fixed reference ("etalon") sequence, data.e, used with XOR mode
scripts/              Python tooling for adaptive sweeps, NIST campaigns, and ECDF charts
ent16/ general/ independent/ pipes/ readfile/ spectral_tests/ wav/
                      supporting utilities from the upstream rtest repository
```

The 20 tests added on top of upstream (numbers 22–41) are:

| # | Test | Adapted from | # | Test | Adapted from |
|---|------|------|---|------|------|
| 22 | DNA | Diehard | 32 | Random Excursions | NIST |
| 23 | Count-the-1s (stream) | Diehard | 33 | Random Excursions Variant | NIST |
| 24 | Count-the-1s (bytes) | Diehard | 34 | 3D Spheres | Diehard |
| 25 | Parking Lot | Diehard | 35 | Marsaglia–Tsang GCD | Dieharder |
| 26 | Squeeze | Diehard | 36 | Non-overlapping Template Matching | NIST |
| 27 | OPERM5 | Diehard | 37 | Runs | NIST |
| 28 | Craps | Diehard | 38 | Longest Run of Ones | NIST |
| 29 | DAB DCT | Dieharder | 39 | Cumulative Sums | NIST |
| 30 | DAB Filtering | Dieharder | 40 | Approximate Entropy | NIST |
| 31 | Linear Complexity | NIST | 41 | Maurer's Universal | NIST |

Every `test_*.c` file opens with a header comment describing the statistic, its
parameters, and its source. Full specifications live in `robust/doc/`: tests 0–21
in `tests-description.tex`, tests 22–41 in `expansion-notes.txt`.

## Dependencies

- **GMP** — multiprecision arithmetic (exact KS values)
- **GSL** — GNU Scientific Library (statistics)
- **Python 3** — for the `scripts/` tools (standard library only, nothing to `pip install`)

```bash
# Debian/Ubuntu
sudo apt-get install libgmp-dev libgsl-dev
# macOS
brew install gmp gsl
```

## Build

```bash
cd robust
make
```

This produces the `rtest` binary. `make install` copies `rtest` and the batch
scripts to `/usr/local/bin` so you can call them from anywhere.

> **macOS on Apple Silicon:** Homebrew installs headers under `/opt/homebrew`,
> which the compiler doesn't search by default (the Makefile targets the Linux
> and Intel-Mac location `/usr/local`). Point it there first — no Makefile edit
> needed:
>
> ```bash
> export CPATH="/opt/homebrew/include"
> export LIBRARY_PATH="/opt/homebrew/lib"
> make
> ```

## Testing your own generator

1. **Produce a file of your generator's raw output** — just bytes, no header.
   A few MB is enough for the small tests; the large ones (DNA, OPERM5, …) want
   100 MB–1 GB.

2. **Run one test.** Use XOR mode (`-x`) against the provided reference file
   `data/data.e`. For example, NIST Runs (test 37):

   ```bash
   ./rtest -x -f yourgen.bin -e ../data/data.e -p 40 -q 40 -n 2000 -t 37 -d 1 -o out
   ```

   It prints the two-sample KS p-value (in a quick check here, `0.16…` for a
   sound generator). The flags:

   - `-x` XOR mode — compare the generator against generator ⊕ reference
   - `-f` your generator file &nbsp; `-e` the reference/etalon file
   - `-t` test number &nbsp; `-d` its dimension &nbsp; `-n` values per call
   - `-p`, `-q` the two sample sizes &nbsp; `-o` output prefix

   Each test expects specific `-t`/`-d`/`-n` values — they aren't free to guess.
   The right settings for every test are already encoded in the batch scripts and
   in `scripts/robust_test_catalog.py`, so use those rather than hand-tuning.

3. **Or run a whole battery at once.** After `make install`:

   ```bash
   ./rtest1m.sh yourgen.bin ../data/data.e     # 1 MB file; also 10m, 100m, 1g, 10g
   ```

   This runs every test that makes sense for that file size and writes the
   results to `yourgen.bin.tst1m`.

**Reading the result.** A p-value that looks uniform (say, above 0.01) is a pass:
no evidence your generator differs from random under that test. A very small
p-value means the test can tell your generator apart from random — the smaller,
the stronger. In the validation campaigns a best-in-sweep p-value below `10⁻¹⁰`
is treated as a real detection.

**One reporting rule that matters.** The KS p-value is not monotone in the sample
size: as you use more of the file, failing and passing windows mix and a real
signal can wash out. So don't just run once at the largest size — sweep the
sample size and report the *best* (smallest) p-value seen. That's what
`scripts/run_maximal_p_sweep.py` automates.

## Sweep and plotting tools (`scripts/`)

Python 3 tooling built around the `rtest` binary:

- `run_robust_nist_campaign.py` — runs a full campaign over a set of generators, picks the best `p=q` per test, and emits ECDF charts. Main entry point.
- `run_maximal_p_sweep.py` — for one (generator, test) pair, finds the file's data ceiling by doubling then bisection, and reports the best objective.
- `robust_test_catalog.py` — the per-test settings (dimension, sample sizes) shared by the other scripts.
- `plot_distribs_svg.py` — draws the two-curve ECDF comparison charts (overlapping curves = a good generator; separated = a bad one). SVG, no plotting library required.
- `run_rtest_t22_sweep.py … t31_sweep.py` — per-test sweep helpers.

These are research tools, not polished CLIs: a couple of them default to the
author's local paths for the generator directory and etalon file, so pass the
corresponding `--` flags for your own setup.

## Reproducing the validation

The 41 tests were checked against nine NIST reference generators:

- the three controls (Blum–Blum–Shub, Linear Congruential, Micali–Schnorr) produced no false positives in any configuration;
- the six known-defective generators were all detected (best objective below `10⁻¹⁰`);
- results agreed whether or not the XOR step was used.

The generator files (~tens of GB per size class) and the full campaign outputs
are far too large to host here, so they are not included; `scripts/` regenerates
them from a generator directory you supply. `robust/doc/expansion-notes.txt` has
the full account of the method, the reporting convention, and the results.

## How the construction stays valid — and why AI could help build it

For a statistic `t`, the suite builds two samples: `U` from `t` on your generator
`A`, and `V` from `t` on `A ⊕ E` for a fixed reference `E`. If `A` is random then
`A ⊕ E` is random too, so `U` and `V` should match; the same code computes both,
so a rough approximation or even a coding error shifts them together and cancels
in the comparison. Validity is therefore structural: a mistake in a statistic can
cost sensitivity, but it cannot make a good generator fail. That is exactly what
made it safe to draft the twenty new statistics (22–41) with AI assistance, in a
reviewed loop — the construction, not the code, is what guarantees the p-values.

## Attribution

- The robust two-sample framework and the original `rtest` suite are by **Alexander Shen** (LIRMM, CNRS / Univ. Montpellier); see the HAL papers above and the upstream repo. Shen's original top-level description is kept here as `README-upstream.md`.
- The test statistics are adapted from **Diehard** (G. Marsaglia), **Dieharder** (R. G. Brown), and the **NIST Statistical Test Suite** (SP 800-22).

## License

To be confirmed with A. Shen before wider distribution. Several statistics are
adapted from Dieharder (GPL), so the combined work will most likely need to be
GPL; the upstream `rtest` license should be matched here.
