# Changes vs. upstream `rtest`

Upstream baseline: [`alexander-shen/rtest`](https://github.com/alexander-shen/rtest)
at commit `6ae81dcec44d5cbe46c7bc58620c275a7cfa3c1d`.

Re-derive this comparison at any time with
`tools/check-upstream-provenance.sh`, which clones that revision and reports,
for every tracked file, whether it is identical to upstream, modified, or new.
It currently reports **113 identical, 4 modified, 26 new**, and exits non-zero
if the modified set ever stops matching the one recorded below. Licensing
consequences of that split are in `LICENSING.md`. Comparisons below are
against that revision, so they stay checkable as upstream moves.

This suite is Alexander Shen's [`rtest`](https://github.com/alexander-shen/rtest)
plus an expansion of **20 new test statistics (numbers 22-41)**. Everything else
is upstream and byte-for-byte unmodified. The four modified files below contain
additions only, in upstream's own formatting; nothing was reflowed or
reindented. This file is the complete list of
what is new or changed, to make review against upstream straightforward.

## New test files (tests 22-41)

| File | # | Test |
|------|---|------|
| `robust/test_dna.c` | 22 | DNA |
| `robust/test_count1s_stream.c` | 23 | Count-the-1s (stream) |
| `robust/test_count1s_byte.c` | 24 | Count-the-1s (bytes) |
| `robust/test_parking.c` | 25 | Parking Lot |
| `robust/test_squeeze.c` | 26 | Squeeze |
| `robust/test_operm5.c` | 27 | OPERM5 |
| `robust/test_craps.c` | 28 | Craps |
| `robust/test_dab_dct.c` | 29 | DAB DCT (adapted, see note) |
| `robust/test_dab_filtering.c` | 30 | DAB Filtering (adapted, see note) |
| `robust/test_linear_complexity.c` | 31 | Linear Complexity |
| `robust/test_random_excursions.c` | 32 | Random Excursions |
| `robust/test_random_excursions_variant.c` | 33 | Random Excursions Variant |
| `robust/test_3d_spheres.c` | 34 | 3D Spheres |
| `robust/test_gcd.c` | 35 | Marsaglia-Tsang GCD |
| `robust/test_nonperiodic.c` | 36 | Non-overlapping Template Matching |
| `robust/test_runs_nist.c` | 37 | Runs |
| `robust/test_longest_run.c` | 38 | Longest Run of Ones |
| `robust/test_cusum.c` | 39 | Cumulative Sums |
| `robust/test_approximate_entropy.c` | 40 | Approximate Entropy |
| `robust/test_universal.c` | 41 | Maurer's Universal |

## Modified from upstream (only to register the 20 new tests)

- `robust/test_func.h` - 20 forward declarations added, in upstream's style.
  Nothing else in the file differs: 60 changed lines, all additions.
- `robust/test_func.c`, 20 entries added to `functions_list[]`, plus the comma
  the previously last entry needed. 22 changed lines, all additions.
- `robust/Makefile`, the 20 new files appended to `TESTS_C`;
  `rtest_expansion.sh` added to `SCRIPTS` so `make install` installs it;
  a `check` target added that runs `check.sh`.

## Added tooling and docs (not part of upstream)

- `scripts/`, Python sweep and ECDF-plotting tools. Standard library only.
  All paths are derived from the script location or passed as arguments, so
  they run from a clean checkout anywhere.
- `robust/rtest_expansion.sh`, battery runner for tests 22-41 (the upstream
  `rtest1m.sh to rtest10g.sh` cover the original tests only).
- `robust/check.sh`, smoke test for a fresh build, run as `make check`.
- `robust/test_nonperiodic_boundary.c`, boundary regression for test 36,
  built by `make test-nonperiodic-boundary` and run as part of `make check`.
- `robust/doc/expansion-notes.txt`, documentation of the expansion.
- `README.md`, this suite's README. Shen's original is kept as `README-upstream.md`.
- `CHANGES-vs-upstream.md`, this file.

## Fixed in this expansion

- **`robust/test_nonperiodic.c` (test 36) miscounted the first eight candidate
  positions of every block.** The per-template "bits since last match" counter
  was only advanced after the 9-bit window had filled, so a template sitting at
  offsets 0 to 7 of a block was never counted; the first eligible position was
  offset 8. Fixed by advancing the counter for every consumed bit.
  `test_nonperiodic_boundary.c` locks the behaviour in by running the statistic
  at every offset in a block and requiring the same count each time.

  The fix does change reported p-values. On the fixture below, 19 of the 148
  coordinates moved (coordinate 9 went from 0.174533 to 0.335591); on other
  inputs at other settings nothing moved at all, because whether the missed
  positions actually hold a template occurrence depends on the data. So a
  p-value comparison is not a reliable way to detect this class of error, and
  the regression checks the statistic directly instead.

  What the robust construction provides is null calibration under its
  assumptions: a deterministic error in a statistic should not make a good
  generator systematically fail. That is not the same as leaving individual
  p-values unchanged, and it is not by itself a measurement of lost
  sensitivity, which would need a power comparison.

  Reproduce the 19 changed coordinates with:

  ```python
  from hashlib import shake_256
  from pathlib import Path
  Path('tested.bin').write_bytes(shake_256(b'rtest review tested v1').digest(128_000_000))
  Path('etalon.bin').write_bytes(shake_256(b'rtest review etalon v1').digest(128_000_000))
  ```
  ```
  rtest -x -f tested.bin -e etalon.bin -p 20 -q 20 -d 148 -n 2000 -t 36 -r 1
  ```

## Issues found in upstream files (reported, not changed)

These were found while testing the expansion. They are in Shen's original files,
so they are left alone here and listed for him to decide on.

1. **`kolmogorov-smirnov/ksmirnov.c`, `psmirnov2x` underflows at large
   sample sizes, and where it starts depends on the platform.** Measured on
   Apple Silicon, where `long double` is 8 bytes; on x86-64, where it is 16
   bytes with a wider exponent, the onset is later and agreement with the
   exact routine has been reported at 3000 and beyond. The recursion returns 0, so `rtest` reports a p-value of exactly
   1.0 regardless of the data. Checked directly: at a fixed deviation of
   `1/sqrt(n)` it gives 0.702 at n=100 and 0.692 at n=2000, then exactly
   1.0 from n=3000 upward. The exact GMP routine (`-k`, `ks2mp.c`) returns
   0.685 at n=3400, so `-k` is a correct workaround. This matters because
   `rtest.c` permits `-p`/`-q` up to 10000.

2. **`robust/rtest.c`, stack overflow on high-dimension tests.**
   `test_p_value` holds both samples in stack VLAs sized `n * dimension`. Test
   36 (dimension 148) segfaults with no message above about `-p 3400` on macOS,
   and near half that on Linux, where `long double` is 16 bytes.
   `ulimit -s unlimited` avoids it.

3. **Very small p-values are lost on the way out.** `rtest.c` prints 18
   decimal places, so any tail below 1e-18 is shown as `0.000000000000000000`.
   The default routine can also return a small negative value by cancellation
   where the true tail is positive. The exact GMP routine in `ks2mp.c` divides
   numerator and denominator down until the denominator fits under 2^128, which
   can truncate a small nonzero numerator to zero. All three limit how small a
   reported p-value can be; the scripts here now flag such points rather than
   treating them as failures.

4. **`kolmogorov-smirnov/ks2.c` has a leftover debug `printf` in `ks2bar`.**
   Harmless in practice: the Makefile links `ks2mp.c` instead, so this file is
   not compiled into `rtest`.

5. **`robust/Makefile` builds with `-fsanitize=address`**, and its library
   search path is wrong:

   ```
   FLAGS = -I /usr/local/include -L /usr/local/bin/ -lgsl ...
   ```

   `-L` names a directory to search for libraries, but `/usr/local/bin` holds
   executables; libraries are in `/usr/local/lib`. On Apple Silicon a
   `LIBRARY_PATH` export hides this, and on Linux the system paths do. On an
   Intel Mac, the configuration the line was written for, linking fails. The
   fix upstream is `-L /usr/local/lib`. Worth reporting to A. Shen.

## Not modified

`robust/rtest.c`, `robust/generators.c` / `.h`, the entire `kolmogorov-smirnov/`
engine, and every other upstream file are identical to upstream. Any issues found
in those files are upstream issues, not part of this expansion.
