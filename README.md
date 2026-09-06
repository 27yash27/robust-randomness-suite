# Robust randomness testing suite

This package tests whether a stream of bits can be distinguished from
independent, unbiased random bits. 41 tests, covering Diehard and most of
NIST STS.

**How it works.** A randomness test computes some statistic and asks whether
the value is surprising. Knowing what "surprising" means normally requires the
statistic's distribution under true randomness, and deriving that is where
approximation error enters.

This suite avoids that step. It computes the same statistic on two samples
from your generator, having XORed one of them with a fixed reference file. If
the generator is random, XOR leaves the distribution unchanged, so the two
samples should look alike, and a two-sample Kolmogorov-Smirnov test compares
them directly. Because both samples pass through the same code, an inaccurate
statistic can still leave the null calibration intact — though it will
generally change individual p-values and the test's power, and it is no
guarantee against arbitrary implementation errors.

Small p-values are evidence against randomness. A large p-value does not
certify a generator, and the numerical limits are real: read
[docs/reading-results.md](docs/reading-results.md) before quoting a number.

## Provenance and credits

The method and the original suite are not mine.

- **The robust two-sample construction** is the work of **Alexander Shen** and
  **Andrey Romashchenko** (LIRMM, CNRS / Univ. Montpellier), cited jointly for
  the method in Shen's own `robust/doc/tests-description.tex`. Papers:
  [lirmm-03065320](https://hal.archives-ouvertes.fr/lirmm-03065320/),
  [lirmm-03371151](https://hal.archives-ouvertes.fr/lirmm-03371151/).
- **Theirs:** the driver, the generator layer, the Kolmogorov-Smirnov engine,
  tests 0 to 21, and every supporting directory. 113 files here are
  byte-identical to [`alexander-shen/rtest`](https://github.com/alexander-shen/rtest)
  at `6ae81dce`; Shen's own description is kept as `README-upstream.md`.
- **Mine (Yash Belani):** tests 22 to 41, `scripts/`, the reproducibility
  package, and this README. The statistics themselves are adapted from
  **Diehard** (George Marsaglia), **Dieharder** (Robert G. Brown) and the
  **NIST Statistical Test Suite** (SP 800-22); `spectral_tests/` includes code
  by **Yann Ollivier**. `LICENSING.md` gives the per-component detail.

This repository was created by copying upstream rather than by forking, so
`git blame` attributes Shen's files to my import commit rather than to him.
`CHANGES-vs-upstream.md` lists exactly which files differ, and
`tools/check-upstream-provenance.sh` re-derives that list against `6ae81dce`.

## 1. Install

GMP, GSL, a C++ compiler, and Python 3.10+ for the scripts (standard library
only, nothing to `pip install`).

```bash
sudo apt-get install libgmp-dev libgsl-dev      # Debian/Ubuntu
```

On macOS a machine that has never built anything needs the Command Line Tools
first; without them there is no compiler, Homebrew cannot install, and the
system `python3` is a stub that fails the same way:

```bash
xcode-select --install
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install gmp gsl
```

On Apple Silicon set these before building, because the Makefile looks in
`/usr/local` while Homebrew installs to `/opt/homebrew`:

```bash
export CPATH=/opt/homebrew/include LIBRARY_PATH=/opt/homebrew/lib
```

Before any large run raise the stack limit, or high-dimension tests crash with
no message: `ulimit -s unlimited` on Linux, `ulimit -s 65520` on macOS.

## 2. Build and check

```bash
make -C robust
make -C robust check
```

`make check` takes a few seconds and uses only files in this repository. It
checks that the generators still match their committed reference output, that
a known-good input passes, that a known-bad one is detected, and that test 36
counts a template wherever it sits in a block. It is a build sanity check, not
evidence that every statistic is correct.

**Every command here runs from the repository root.** Building for speed
rather than for the default sanitizer build, `make install`, and the full flag
table are in [docs/running-tests.md](docs/running-tests.md).

## 3. See it work, with no files of your own

```bash
python3 scripts/reproduce_randomness_demo.py --repo . --out ../randomness-demo
```

It builds three deterministic 20 MB inputs from recorded recipes, runs test 37
at five fixed sample sizes against two of them, and writes the curve
comparisons, a `results.csv` giving the exact command and p-value for every
run, the input hashes and the raw logs.

Open `ascii_fixture.svg` first. Its input is the ASCII bytes `0` and `1`
repeated, which is strongly biased, and test 37 detects it: the p-value falls
from 0.33 at 2 samples to about 1.45e-11 at 20, and the curves visibly pull
apart. Then open `shake_fixture.svg`, whose input should look random: the
curves sit on top of each other. The sizes are fixed in advance, so nothing is
selected after the fact. This is the workflow, not the validation campaign.

## 4. Run every added test

```bash
python3 scripts/run_all_experiments.py --repo . --out ../experiments --size-mb 300
```

Runs tests 22 to 41 at the sizes fixed in `scripts/robust_test_catalog.py` and
writes one SVG per test and fixture, plus a `results.csv`. It prints any
planned run your `--size-mb` cannot support; tests 32 and 33 need 700 MB for a
complete set. Expect a few runs to report `statistic_declined_too_few_cycles`:
not every test can evaluate every input, and the runner records why rather
than hiding it.

## 5. Test your own files

[docs/running-tests.md](docs/running-tests.md) covers running one test, the
full battery, the sample-size sweep and the curve comparison, with the flag
reference.

One thing to know first: `robust/rtest_expansion.sh` runs every added test at
the smallest size in the catalog, so it is a **smoke test**. It confirms each
test runs, but the two-sample KS floor at those sizes means it cannot report a
detection. Detection comes from step 4 or from the sweep.

## What is in here

```
robust/          the driver and all 41 tests
  rtest.c          main program
  test_*.c         one file per statistic, each with a header comment
  rtest*.sh        batteries for files of 1 MB to 10 GB
  doc/             tests-description.tex (0-21), expansion-notes.txt (22-41)
kolmogorov-smirnov/  the KS engine
scripts/         the sweep, the runners and the plotting tools
reproducibility/ generator recipes, input hashes, preserved campaign results
docs/            running the tests, reading a result, what was validated
tools/           check-upstream-provenance.sh
data/            a small etalon, data.e
ent16/ general/ independent/ pipes/ readfile/ spectral_tests/ wav/
                 upstream utilities, not needed to run tests
```

`CHANGES-vs-upstream.md` lists the twenty added tests with their sources,
exactly which files differ from upstream, and which known bugs live where.

## Validation

Tests 22 to 31 were checked against the nine NIST reference generators in one
exploratory campaign; tests 32 to 41 have no campaign of their own. The three
intended controls crossed the 1e-10 threshold on no test and the other six
crossed it on at least one — a recorded outcome, not an estimated
false-positive rate, and some rows are affected by a known numerical
saturation. [docs/validation.md](docs/validation.md) states what that campaign
does and does not establish, and why its p-values cannot be reproduced exactly.

## License

Intended to be **GPL-2.0-or-later**, which is both what the Dieharder ancestry
requires and what Alexander Shen wants so the suite can be packaged in Linux
distributions.

It is not in force yet, and there is no `LICENSE` file, for one reason:
upstream `rtest` declares no license, and Shen holds the copyright on the 113
files here that are byte-identical to it. A short written grant from him
settles it. **Until then, do not redistribute the combined work.**

`LICENSING.md` gives the component-by-component breakdown, including the
separate notice on `spectral_tests/rand.h` that must travel with the code.
