# Running the tests on your own files

Everything here assumes you have built the binary and run the checks:

```bash
make -C robust
make -C robust check
```

Commands run from the repository root unless a subshell says otherwise.

## Test your own generator

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
| `-t` | which test, 0 to 41 (the catalog covers 22 to 41; see below) |
| `-d` | how many values that test returns |
| `-n` | that test's size parameter, whose unit is test-dependent |
| `-p` `-q` | the two sample sizes |
| `-r 1` | run once. `-r 0` repeats until the data runs out. |
| `-k` | the GMP backend: slower, and free of the underflow in step 5 |
| `-m` | extra parameter, needed only by some tests (test 31 uses `-m 500`) |
| `-o` | write the raw sample values to this directory, for plotting |
| `-v` | verbose, prints what it is doing |

**`-d` and `-n` are not free to choose.** Each test needs particular values.
For **tests 22 to 41** they are in `scripts/robust_test_catalog.py`, which the
runner and the sweep read automatically. That catalog does **not** cover tests
0 to 21: for those, take the dimension and size parameter from the comment
beside each declaration in `robust/test_func.h`, and see the `rtest*.sh`
batteries for worked settings.
## Run a whole battery

The battery scripts write next to their input, so run them from `robust/`:

```bash
(cd robust && ./rtest_expansion.sh ../yourgen.bin ../etalon.bin)   # tests 22-41
(cd robust && ./rtest100m.sh ../yourgen.bin ../etalon.bin)         # tests 0, 1, 3-16
```

`rtest_expansion.sh` exits non-zero if any test fails to produce a p-value.
The upstream batteries cover tests 0, 1 and 3 to 16 only. Test 2 is a
debugging function, and **tests 17 to 21 have no battery**, so run those by
hand with `rtest` if you need them.

Results land in `yourgen.bin.expansion` and `yourgen.bin.test100m`.
`rtest_expansion.sh` exits non-zero if a test fails to produce a p-value, but
not when a statistic states its own reason for declining, which it records with
that reason. On a 300 MB random input, expect tests 32 and 33 to decline with
"too few cycles".

**The expansion battery is a smoke test, not a detector.** It uses the smallest
sample size in the catalog for each test, and a two-sample KS test has a hard
floor on the p-value it can return at small sizes:

| sample size | smallest possible p-value |
|---|---|
| p = q = 2 | 1/C(4,2) = 0.167 |
| p = q = 3 | 1/C(6,3) = 0.05 |
| p = q = 5 | 1/C(10,5) = 0.004 |

So it confirms every test runs and produces a value; it cannot report a
detection. Upstream's `rtest100m.sh` uses 1000 to 5000 for that reason.
Detection comes from `run_maximal_p_sweep.py` below, or from
`run_all_experiments.py`, which sweeps a range of sizes per test. Use
`rtest1m.sh`, `rtest10m.sh`, `rtest100m.sh`, `rtest1g.sh` or `rtest10g.sh` to
match your file's size.

Watch the output suffix, it is inconsistent upstream. `rtest1m.sh` writes
`.tst1m`, with no `e`. Every other battery writes `.test10m`, `.test100m`,
`.test1g`, `.test10g`. If a result file seems to be missing, that is usually
why.
## Sweep the sample size

Do not just run once. This runs one test across a range of sizes and reports the
strongest result:

```bash
python3 scripts/run_maximal_p_sweep.py --campaign mytest \
    --generator-dir /path/to/generators --etalon etalon.bin --tests 37
```
## Look at the curves for one test

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
