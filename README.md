# Robust randomness testing suite

This package tests whether a stream of bits can be distinguished from
independent, unbiased random bits.

It applies the same statistic to two samples from your generator, transforming
one of them by XOR with a fixed reference file. Under the randomness model that
transformation leaves the distribution unchanged, so the two samples can be
compared directly with a two-sample Kolmogorov-Smirnov test. That avoids having
to derive a null distribution for each statistic separately, which is where
approximation error usually enters. Because the same deterministic code produces
both samples, an inaccurate statistic can still leave the null calibration
intact under the construction's assumptions; it will generally change individual
p-values and the test's power, and it is not a guarantee against arbitrary
implementation or numerical errors.

Small p-values are evidence against the randomness model. A large p-value does
not certify a generator, and the numerical limits in step 5 are real; read them
before drawing conclusions.

## Provenance and credits

The method and the original suite are not mine.

- **The robust two-sample construction** is the work of **Alexander Shen** and
  **Andrey Romashchenko** (LIRMM, CNRS / Univ. Montpellier). Shen's own
  `robust/doc/tests-description.tex` cites them jointly for the method, under
  the key `shen-romashchenko-robust`. Papers:
  [lirmm-03065320](https://hal.archives-ouvertes.fr/lirmm-03065320/),
  [lirmm-03371151](https://hal.archives-ouvertes.fr/lirmm-03371151/).
- **Theirs:** the driver (`robust/rtest.c`), the generator layer, the
  Kolmogorov-Smirnov engine, tests 0 to 21, and every supporting directory.
  113 of the files here are byte-identical to
  [`alexander-shen/rtest`](https://github.com/alexander-shen/rtest) at
  `6ae81dce`; Shen's own description is preserved as `README-upstream.md`.
- **Mine (Yash Belani):** tests 22 to 41, the tooling in `scripts/`, the
  reproducibility package, and this README.

This repository was created by copying upstream rather than by forking, so
`git blame` attributes Shen's original files to my import commit rather than to
him. `CHANGES-vs-upstream.md` lists exactly which files differ, and
`tools/check-upstream-provenance.sh` re-derives that list against `6ae81dce`.

41 tests in total, covering Diehard and most of NIST STS.

---

## 1. Install the dependencies

GMP, GSL and a C++ compiler, plus **Python 3.10 or later** for the scripts
(standard library only, nothing to `pip install`).

```bash
sudo apt-get install libgmp-dev libgsl-dev      # Debian/Ubuntu
```

On macOS, a machine that has never built anything needs the Command Line Tools
first. Without them there is no compiler, Homebrew cannot install, and the
system `python3` is a stub that fails the same way:

```bash
xcode-select --install
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install gmp gsl
```

On Apple Silicon, set these before building, because the Makefile looks in
`/usr/local` while Homebrew installs to `/opt/homebrew`:

```bash
export CPATH=/opt/homebrew/include LIBRARY_PATH=/opt/homebrew/lib
```

Before any large run, raise the stack limit, or high-dimension tests will crash
with no message: `ulimit -s unlimited` on Linux, `ulimit -s 65520` on macOS.

## 2. Build it and check it

From the repository root:

```bash
make -C robust
make -C robust check
```

`make check` takes a few seconds and uses only files in this repository. It
checks four things: that the generators still match their committed reference
output, that a known-good input passes, that a known-bad one is detected, and
that test 36 counts a template wherever it sits in a block. Passing means those
four checks passed; it is a build sanity check, not evidence that every
statistic is correct.

The Makefile builds with `-fsanitize=address`, which is about ten times slower.
For long runs override `FLAGS` on the command line rather than editing the file,
so nothing tracked changes:

```bash
make -C robust FLAGS="-I /usr/local/include -L /usr/local/lib -lgsl -lgslcblas -lm -lgmp"
```

On Apple Silicon use `/opt/homebrew` in place of `/usr/local` there.

**Every command in this README runs from the repository root.** The few that
need a different directory say so and change into it themselves.

`make -C robust install` copies `rtest` and the battery scripts into
`/usr/local/bin` with `sudo`, and `uninstall` removes them. You do not need it
for anything below, but the upstream `rtest*.sh` batteries expect `rtest` on the
`PATH`, so they only work after installing or from inside `robust/`.

## 3. See it work, with no files of your own

The quickest way to see the whole workflow. From the repository root:

```bash
python3 scripts/reproduce_randomness_demo.py --repo . --out ../randomness-demo
```

It builds three deterministic 20 MB inputs from recorded recipes, runs test 37
at five fixed sample sizes against two of them, and writes:

- `shake_fixture.svg` and `ascii_fixture.svg`, the curve comparisons
- `results.csv`, with the exact command, revision, backend, raw p-value and
  numerical status for every run
- `input_manifest.csv`, with the generation recipe and SHA-256 of each input
- `provenance.json`, plus raw logs and the statistic samples

Open `ascii_fixture.svg` first. Its input is the ASCII bytes `0` and `1`
repeated, which is strongly biased, and test 37 detects it: the p-value falls
from 0.33 at 2 samples to about 1.45e-11 at 20, and the two curves visibly pull
apart. Then open `shake_fixture.svg`, whose input should look random: the curves
sit on top of each other and the p-values stay unremarkable.

The sample sizes are fixed in advance, so nothing here is selected after the
fact.

This demonstrates the workflow. It is not the nine-generator validation
campaign, and it does not estimate a false-positive rate.

## 4. Run every added test

The same idea across all twenty added tests:

```bash
python3 scripts/run_all_experiments.py --repo . --out ../experiments --size-mb 300
```

Runs tests 22 to 41 at the sample sizes fixed in
`scripts/robust_test_catalog.py`, against the same two inputs, and writes one
SVG per test and fixture plus a `results.csv` recording the command, revision,
backend, raw p-value, numeric status, plotted coordinate and every coordinate
value for each run.

It prints, before starting, any planned run your `--size-mb` cannot support.
Tests 32 and 33 need 640 MB at their largest sample size, so use `--size-mb 700`
for a complete set; at 300 MB everything else completes. Expect a few runs to
report `statistic_declined_too_few_cycles`: Random Excursions cannot evaluate
the biased ASCII input, and says so. Not every test can detect every defect, and
the runner records why rather than hiding it.

Add `--ksexact` for the exact KS backend. `reproducibility/README.md` explains
the statuses, the per-test input budget, how to rebuild the nine research
generators, and what the preserved campaign does and does not establish.

## 5. Read a result

- **between 0.01 and 0.99**: that test found nothing at that sample size. It
  does not certify the generator.
- **very small, below about 1e-6**: evidence the test can tell your generator
  from random.
- **printed as zero**: below what the driver can show. Not a bound, and not a
  measured detection.
- **exactly 1.0**: legitimate at tiny sample sizes; above a few dozen samples
  suspect the KS underflow.
- **`oops, eof in generator`**: the files are too small for that test.

A single p-value is not the answer: it is not monotone in the sample size, and
the minimum over a sweep is biased low by the search. `docs/reading-results.md`
covers the numerical limits, the platform-dependent underflow and the known
upstream bugs, and you should read it before quoting a number.

## 6. Test your own files

`docs/running-tests.md` covers running one test, the full battery, the sample
size sweep and the curve comparison for a single test, with the flag reference.

One thing to know before you use it: `robust/rtest_expansion.sh` runs all twenty
added tests at the smallest size in the catalog, so it is a **smoke test**. A
two-sample KS test cannot return a p-value below `1/C(2p,p)`, which at those
sizes is 0.167 to 0.004, so the battery confirms every test runs but cannot
report a detection. Detection comes from step 4 or from the sweep.

---

## What is in here

```
robust/          the driver and all 41 tests
  rtest.c          main program
  test_*.c         one file per statistic, each with a header comment
  rtest*.sh        batteries for files of 1 MB to 10 GB
  doc/             tests-description.tex (tests 0-21), expansion-notes.txt (22-41)
kolmogorov-smirnov/  the KS engine
reproducibility/ generator recipes, input hashes, preserved campaign results
tools/           check-upstream-provenance.sh, which re-derives the upstream diff
LICENSING.md     component-by-component licence position
CHANGES-vs-upstream.md  exactly which files differ from upstream, and known bugs
data/            a small etalon, data.e
scripts/         compare_curves.py, run_maximal_p_sweep.py and friends
ent16/ general/ independent/ pipes/ readfile/ spectral_tests/ wav/
                 upstream utilities, not needed to run tests
```

The twenty tests added on top of upstream are 22 to 41: the Diehard battery,
most of NIST STS, and three from Dieharder. `CHANGES-vs-upstream.md` lists them
with their sources and files.

For more than this page: `robust/doc/expansion-notes.txt` for the new tests,
`robust/doc/tests-description.tex` for tests 0-21, and `CHANGES-vs-upstream.md`
for exactly which files differ from upstream and which known bugs live in which
file.

## Validation

Checked against the nine NIST reference generators, on **tests 22 to 31 only**.
In that campaign the three intended controls (Blum-Blum-Shub, Linear
Congruential, Micali-Schnorr) crossed the 1e-10 threshold on no test, and the
other six crossed it on at least one. Read those as recorded exploratory
outcomes, not as an estimated false-positive rate: nine generators over ten
tests cannot establish one, the minimum over a sweep is biased low by the
search, and 27 of the 90 rows report exactly 1.0 through the backend that is
known to underflow at that sample size.

The campaign metadata records XOR mode as enabled throughout, so this repository
holds no no-XOR comparison; any claim that results agreed with and without the
XOR step is not supported by what is committed here. The generator files run to tens of
GB and are not in this repository, but their recipes, hashes and the original
results are: see `reproducibility/`. **That campaign covers tests 22 to 31
only**, on nine generators; tests 32 to 41 have no campaign of their own. Two of
its inputs, the 40 GB etalon and the pre-fix SHA-1 generator, cannot be
recreated from anything published, so its exact p-values cannot be reproduced;
it is archived evidence rather than a reproduction target. That directory has the modified NIST STS
sources and the guide needed to rebuild the nine generators, a manifest with the
SHA-256 of each input, and the campaign output with a note on how it was
produced and what has and has not been checked. `scripts/run_maximal_p_sweep.py`
reruns the sweep against generator files you supply; the `rtest*.sh` batteries
cover tests 0, 1 and 3-16.

## Credits

See `LICENSING.md` for full attribution. In brief: the robust two-sample scheme
and the original `rtest` are by Alexander Shen
(LIRMM, CNRS / Univ. Montpellier); his original description is kept as
`README-upstream.md`. Statistics adapted from Diehard (Marsaglia), Dieharder
(R. G. Brown) and the NIST Statistical Test Suite (SP 800-22).

## License

Intended to be **GPL-2.0-or-later**, which is both what the Dieharder ancestry
requires and what Alexander Shen wants so the suite can be packaged in Linux
distributions.

It is not in force yet, and there is no `LICENSE` file, for one reason: upstream
`rtest` declares no license, and Shen holds the copyright on the 113 files here
that are byte-identical to it. A short written grant from him settles it.
**Until then, do not redistribute the combined work.**

`LICENSING.md` gives the component-by-component breakdown: which tests carry
GPL through Dieharder, which come from the public-domain NIST suite, and the
separate notice on `spectral_tests/rand.h` that must travel with the code.
