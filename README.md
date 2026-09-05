# Robust randomness testing suite

Tests a random-bit generator and tells you whether it is distinguishable from
random, with a p-value you can actually trust.

Ordinary randomness tests compute a p-value from an approximation whose error is
not bounded, so a small value might mean a bad generator or just a bad
approximation. This suite compares your generator against itself XOR-ed with a
fixed file instead. If the generator is random, both sides are random, so the
two samples must match. Comparing them with a Kolmogorov-Smirnov test gives a
p-value that needs no assumption about the distribution of the statistic, which
is the assumption ordinary tests get wrong. It still relies on the samples being
independent and on the arithmetic being sound, so read the limits below.

41 tests, covering Diehard and most of NIST STS. Built on Alexander Shen's
[`rtest`](https://github.com/alexander-shen/rtest), extended from 21 tests to 41.
Theory: [lirmm-03065320](https://hal.archives-ouvertes.fr/lirmm-03065320/),
[lirmm-03371151](https://hal.archives-ouvertes.fr/lirmm-03371151/).

---

## 1. What you need before you start

- **GMP and GSL**, plus a C++ compiler.
  - Debian/Ubuntu: `sudo apt-get install libgmp-dev libgsl-dev`
  - macOS: `brew install gmp gsl`
- **Python 3** for the plotting scripts. Standard library only, nothing to install.
- **Your generator's output in a file**: raw bytes, no header. 300 MB is a good
  size. Smaller works, but the heavy tests will run out of data.
- **An etalon file**: any fixed file of at least the same size. Its quality does
  not matter, only its size. Make one with:
  ```bash
  head -c 300000000 /dev/urandom > etalon.bin
  ```

## 2. Build it

```bash
cd robust
make
```

You now have the `rtest` binary. Steps 3 to 7 below all run from this
`robust/` directory; step 8 runs from the repository root and says so.

- **On Apple Silicon**, run this first, because the Makefile looks in
  `/usr/local` and Homebrew installs to `/opt/homebrew`:
  ```bash
  export CPATH=/opt/homebrew/include LIBRARY_PATH=/opt/homebrew/lib
  ```
- **Before any large run**, raise the stack limit or high-dimension tests will
  crash without printing anything:
  ```bash
  ulimit -s unlimited      # on macOS: ulimit -s 65520
  ```
- The Makefile builds with `-fsanitize=address`, which is about ten times
  slower. Remove it from `FLAGS` for long runs.

Confirm the build is good before you trust any result:

```bash
make check
```

It takes a few seconds and uses only files in this repository. It checks four
things: that the generators still match their committed reference output, that
a known-good generator passes, that a known-bad one is detected, and that test
36 counts a template wherever it sits in a block. Passing means those four
checks passed. It is a build sanity check, not evidence that every statistic is
correct.

## 3. Run one test

```bash
./rtest -x -f yourgen.bin -e etalon.bin -p 40 -q 40 -d 1 -n 100000 -t 37 -r 1
```

That is NIST Runs (test 37). It prints one p-value per coordinate.

The flags:

| Flag | Meaning |
|------|---------|
| `-x` | XOR mode. Always use it. |
| `-f` | your generator file |
| `-e` | the etalon file |
| `-t` | which test, 0 to 41 |
| `-d` | how many values that test returns |
| `-n` | that test's size parameter |
| `-p` `-q` | the two sample sizes |
| `-r 1` | run once. `-r 0` repeats until the data runs out. |
| `-k` | slower, exact p-value. See the warning in step 5. |
| `-m` | extra parameter, needed only by some tests (test 31 uses `-m 500`) |
| `-o` | write the raw sample values to this directory, for plotting |
| `-v` | verbose, prints what it is doing |

**`-d` and `-n` are not free to choose.** Each test needs particular values.
They are listed in `scripts/robust_test_catalog.py`, and the scripts below read
them from there, so you never have to type them by hand.

## 4. Or run every test at once

```bash
./rtest_expansion.sh yourgen.bin etalon.bin     # tests 22-41
./rtest100m.sh yourgen.bin etalon.bin           # tests 0, 1 and 3-16
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

## 5. Read the result

- **Between 0.01 and 0.99**: pass. That test found nothing wrong.
- **Very small, say below 1e-6**: the test can tell your generator from random.
  Smaller means stronger evidence. In our validation runs anything below 1e-10
  counted as a real detection.
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
  spot comparisons against `-k`, or simply pass `-k`, which is exact
  everywhere and slower.
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

## 6. Sweep the sample size

Do not just run once. This runs one test across a range of sizes and reports the
strongest result:

```bash
python3 ../scripts/run_maximal_p_sweep.py --campaign mytest \
    --generator-dir /path/to/generators --etalon etalon.bin --tests 37
```

## 7. Look at the curves

To see what a test is actually doing:

```bash
python3 ../scripts/compare_curves.py -t 37 -f yourgen.bin -e etalon.bin
```

This runs test 37 at five sample sizes and writes one SVG with a panel per run.
Each panel draws the two distributions being compared.

- **Curves lying on top of each other**: the test sees nothing.
- **Curves pulling apart**: the test is distinguishing your generator from
  random, and the p-value above the panel says how strongly.

Options: `-t` any test from 22 to 41, `--sizes` for your own sample sizes,
`--coord` to pick a coordinate on tests that return several values, `-o` for the
output filename.

## 8. A worked example you can reproduce

To see the whole workflow run end to end without supplying a generator of your
own. Note this one runs from the repository root, not from `robust/`:

```bash
cd ..
python3 scripts/reproduce_randomness_demo.py --repo . --out ../randomness-demo
```

It builds three deterministic 20 MB inputs from recorded recipes, runs test 37
at five fixed sample sizes against two of them, and writes:

- `shake_fixture.svg` and `ascii_fixture.svg`, the curve comparisons
- `results.csv`, with the exact command, revision, backend, raw p-value and
  numerical status for every run
- `input_manifest.csv`, with the generation recipe and SHA-256 of each input
- `provenance.json`, plus raw logs and the statistic samples

The SHAKE fixture should look random. The ASCII fixture, which is the bytes
`01` repeated, should be detected: its p-value falls from 0.33 at 2 samples to
about 1.45e-11 at 20. The sample sizes are fixed in advance, so nothing here is
selected after the fact.

This demonstrates the workflow. It is not the nine-generator validation
campaign, and it does not estimate a false-positive rate.

## 9. Every test, on inputs you can rebuild

The same idea across all twenty added tests:

```bash
python3 scripts/run_all_experiments.py --repo . --out ../experiments --size-mb 300
```

Runs tests 22 to 41 at the sample sizes fixed in
`scripts/robust_test_catalog.py`, against one input that should look random and
one that should not, and writes an SVG per test and fixture plus a `results.csv`
recording the command, revision, backend, raw p-value and numeric status of
every run. Add `--ksexact` for the exact KS routine, `--tests` to narrow it
down, and raise `--size-mb` if a heavy test reports running out of data.

See `reproducibility/` for how to rebuild the nine research generators, the
input hashes, and the preserved campaign results.

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

Checked against the nine NIST reference generators. The three good ones
(Blum-Blum-Shub, Linear Congruential, Micali-Schnorr) gave no false positives.
All six defective ones were detected, with best-in-sweep p-values below 1e-10.
Results agreed with and without the XOR step. The generator files run to tens of
GB and are not in this repository, but their recipes, hashes and the original
results are: see `reproducibility/`. That directory has the modified NIST STS
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
