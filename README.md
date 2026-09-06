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

41 tests, covering Diehard and most of NIST STS. Yash Belani added 20 tests
(numbers 22 to 41) to Alexander Shen's original
[`rtest`](https://github.com/alexander-shen/rtest).
Theory: [lirmm-03065320](https://hal.archives-ouvertes.fr/lirmm-03065320/),
[lirmm-03371151](https://hal.archives-ouvertes.fr/lirmm-03371151/).

---

## 1. Install the dependencies

GMP, GSL and a C++ compiler, plus **Python 3.10 or later** for the scripts
(standard library only, nothing to `pip install`).

```bash
sudo apt-get install libgmp-dev libgsl-dev     # Debian/Ubuntu
brew install gmp gsl                            # macOS
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
Remove it from `FLAGS` for long runs.

**Every command in this README runs from the repository root.** The few that
need a different directory say so and change into it themselves.

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

---

## 5. Read the result

- **Between 0.01 and 0.99**: that test found nothing. It does not certify the
  generator; it means this statistic saw nothing at this sample size.
- **Very small, say below 1e-6**: evidence that the test can tell your generator
  from random. Smaller means stronger evidence. The campaign treated below
  1e-10 as a detection.
- **Exactly 1.0**: legitimate at very small sample sizes, where the discrete
  KS distribution really does reach 1. At larger sample sizes it usually means
  the p-value routine underflowed. See the note below.
- **`oops, eof in generator`**: your files are too small for that test. Use
  bigger ones or lower `-p` and `-q`.

Two things that will bite you:

- **The safe sample size depends on your platform.** The default p-value
  routine works in `long double`, which is 8 bytes on Apple Silicon and 16
  bytes with a wider exponent on x86-64. On Apple Silicon it underflows above
  roughly 2500 samples and returns exactly 1.0 whatever the data says; on
  x86-64 Linux it has been observed to agree with the exact routine at 3000
  and beyond. Measure it on your own machine with `make check` and a few
  spot comparisons against `-k`. `-k` selects the GMP backend, which avoids
  this underflow and is slower; it is not free of every limit, as the next two
  points describe.
- **A p-value of exactly 1.0 is not automatically a bug.** At very small
  sample sizes the discrete KS distribution genuinely reaches 1. Above a few
  dozen samples, treat it as the underflow above until you have checked with
  `-k`.
- **Very small p-values are printed as zero.** The driver prints 18 decimal
  places, so anything below 1e-18 comes out as `0.000000000000000000`, and the
  default routine can print a small negative value instead through
  cancellation. Both mean "smaller than can be shown here", not "no result",
  and neither certifies a particular value. `-k` removes the cancellation but
  not the 18-decimal output, and the exact routine reduces its own denominator
  under 2^128, which can truncate a very small numerator to zero as well. Treat
  such a point as "too small to report" rather than as a measured number.
- **A single p-value is not the answer.** The p-value is not monotone in the
  sample size, so a real signal can appear at one size and vanish at another.
  Run several sizes and take the smallest value you see. That minimum is a
  search summary over many sample sizes and coordinates, not a calibrated
  p-value: it is biased low by the search itself. Fix the family of tests,
  coordinates and sizes in advance and correct for multiplicity, or report the
  minimum as exploratory and judge it against a small fixed threshold.

## 6. Test your own generator

You need two files:

- **your generator's output**, raw bytes with no header. A few hundred MB suits
  most tests; see the per-test budget in `reproducibility/README.md`.
- **an etalon**, any fixed file at least as large. Its contents do not affect
  validity, but they do affect the numbers, so keep the one you used if you want
  to reproduce a result later.

```bash
head -c 300000000 /dev/urandom > etalon.bin
```

Then run one test. This one is NIST Runs, test 37:

```bash
(cd robust && ./rtest -x -f ../yourgen.bin -e ../etalon.bin \
    -p 40 -q 40 -d 1 -n 100000 -t 37 -r 1)
```

It prints the KS p-value, one per coordinate.

The flags:

| Flag | Meaning |
|------|---------|
| `-x` | XOR mode. Always use it. |
| `-f` | your generator file |
| `-e` | the etalon file |
| `-t` | which test, 0 to 41 |
| `-d` | how many values that test returns |
| `-n` | that test's size parameter, whose unit is test-dependent |
| `-p` `-q` | the two sample sizes |
| `-r 1` | run once. `-r 0` repeats until the data runs out. |
| `-k` | the GMP backend: slower, and free of the underflow in step 5 |
| `-m` | extra parameter, needed only by some tests (test 31 uses `-m 500`) |
| `-o` | write the raw sample values to this directory, for plotting |
| `-v` | verbose, prints what it is doing |

**`-d` and `-n` are not free to choose.** Each test needs particular values,
listed in `scripts/robust_test_catalog.py` and used automatically by the scripts
in steps 3 and 4, so take them from there rather than guessing.

## 7. Run a whole battery

The battery scripts write next to their input, so run them from `robust/`:

```bash
(cd robust && ./rtest_expansion.sh ../yourgen.bin ../etalon.bin)   # tests 22-41
(cd robust && ./rtest100m.sh ../yourgen.bin ../etalon.bin)         # tests 0, 1, 3-16
```

`rtest_expansion.sh` exits non-zero if any test fails to produce a p-value.
The upstream batteries cover tests 0, 1 and 3 to 16 only. Test 2 is a
debugging function, and **tests 17 to 21 have no battery**, so run those by
hand with `rtest` if you need them.

Results land in `yourgen.bin.expansion` and `yourgen.bin.test100m`. Use
`rtest1m.sh`, `rtest10m.sh`, `rtest100m.sh`, `rtest1g.sh` or `rtest10g.sh` to
match your file's size.

Watch the output suffix, it is inconsistent upstream. `rtest1m.sh` writes
`.tst1m`, with no `e`. Every other battery writes `.test10m`, `.test100m`,
`.test1g`, `.test10g`. If a result file seems to be missing, that is usually
why.

## 8. Sweep the sample size

Do not just run once. This runs one test across a range of sizes and reports the
strongest result:

```bash
python3 scripts/run_maximal_p_sweep.py --campaign mytest \
    --generator-dir /path/to/generators --etalon etalon.bin --tests 37
```

## 9. Look at the curves for one test

To see what a test is actually doing:

```bash
python3 scripts/compare_curves.py -t 37 -f yourgen.bin -e etalon.bin
```

This runs test 37 at five sample sizes and writes one SVG with a panel per run.
Each panel draws the two distributions being compared.

- **Curves lying on top of each other**: the test sees nothing.
- **Curves pulling apart**: the test is distinguishing your generator from
  random, and the p-value above the panel says how strongly.

Options: `-t` any test from 22 to 41, `--sizes` for your own sample sizes,
`--coord` to pick a coordinate on tests that return several values, `-o` for the
output filename.

## What is in here

```
robust/          the driver and all 41 tests
  rtest.c          main program
  test_*.c         one file per statistic, each with a header comment
  rtest*.sh        batteries for files of 1 MB to 10 GB
  doc/             tests-description.tex (tests 0-21), expansion-notes.txt (22-41)
kolmogorov-smirnov/  the KS engine
reproducibility/ generator recipes, input hashes, preserved campaign results
data/            a small etalon, data.e
scripts/         compare_curves.py, run_maximal_p_sweep.py and friends
ent16/ general/ independent/ pipes/ readfile/ spectral_tests/ wav/
                 upstream utilities, not needed to run tests
```

The twenty tests added on top of upstream:

| # | Test | From | # | Test | From |
|---|------|------|---|------|------|
| 22 | DNA | Diehard | 32 | Random Excursions | NIST |
| 23 | Count-the-1s (stream) | Diehard | 33 | Random Excursions Variant | NIST |
| 24 | Count-the-1s (bytes) | Diehard | 34 | 3D Spheres | Diehard |
| 25 | Parking Lot | Diehard | 35 | Marsaglia-Tsang GCD | Dieharder |
| 26 | Squeeze | Diehard | 36 | Non-overlapping Template Matching | NIST |
| 27 | OPERM5 | Diehard | 37 | Runs | NIST |
| 28 | Craps | Diehard | 38 | Longest Run of Ones | NIST |
| 29 | DAB DCT | Dieharder | 39 | Cumulative Sums | NIST |
| 30 | DAB Filtering | Dieharder | 40 | Approximate Entropy | NIST |
| 31 | Linear Complexity | NIST | 41 | Maurer's Universal | NIST |

For more than this page: `robust/doc/expansion-notes.txt` for the new tests,
`robust/doc/tests-description.tex` for tests 0-21, and `CHANGES-vs-upstream.md`
for exactly which files differ from upstream and which known bugs live in which
file.

## Known bugs

Both are in upstream files and are left unchanged here.

1. `psmirnov2x` in `kolmogorov-smirnov/ksmirnov.c` underflows above about 2500
   samples and returns a p-value of exactly 1.0. Use `-k`, or keep `-p` and `-q`
   at 2000 or below.
2. `test_p_value` in `robust/rtest.c` keeps both samples on the stack, so
   high-dimension tests such as test 36 segfault silently above roughly
   `-p 3400` on macOS and half that on Linux. Raise the stack limit first.

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

The robust two-sample scheme and the original `rtest` are by Alexander Shen
(LIRMM, CNRS / Univ. Montpellier); his original description is kept as
`README-upstream.md`. Statistics adapted from Diehard (Marsaglia), Dieharder
(R. G. Brown) and the NIST Statistical Test Suite (SP 800-22).

## License

Not settled yet. Several statistics derive from Dieharder, which is GPL, so this
will most likely have to be GPL as well, matching upstream `rtest`.
