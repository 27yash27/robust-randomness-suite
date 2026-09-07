# Changes vs. upstream `rtest`

Upstream baseline: [`alexander-shen/rtest`](https://github.com/alexander-shen/rtest)
at commit `6ae81dcec44d5cbe46c7bc58620c275a7cfa3c1d`.

That commit is authored by Alexander Shen and titled "yash changes", which can
look odd for a "pristine upstream" baseline. It is upstream: Shen authored and
committed it to his own repository, incorporating earlier contributions of mine
that predate this expansion. It is pinned here because it is the revision this
work started from, and everything below is measured against it.

Re-derive this comparison at any time with
`tools/check-upstream-provenance.sh`, which clones that revision and reports,
for every tracked file, whether it is identical to upstream, modified, or new.
It currently reports **113 identical, 4 modified, 29 new**, and exits non-zero
if the modified set, or either count, stops matching what is recorded here.
Licensing consequences of that split are in `LICENSING.md`. Comparisons below
are against that revision, so they stay checkable as upstream moves.

This suite is Alexander Shen's [`rtest`](https://github.com/alexander-shen/rtest)
plus an expansion of **20 new test statistics (numbers 22-41)**. Everything else
is upstream and byte-for-byte unmodified.

Four files are modified, in upstream's own formatting; nothing was reflowed or
reindented. Measured against upstream: `test_func.h` +60/-0, `test_func.c`
+21/-1, `robust/Makefile` +29/-6, and `README.md`, which replaces upstream's.

In `test_func.h` and `test_func.c` the changes register the twenty new tests
and nothing else; the single replaced line in `test_func.c` is an existing line
re-emitted with a comma appended. `robust/Makefile` does that too, and
additionally carries **three corrections to upstream behaviour** — the library
search path, `clean`, and `uninstall` — each listed individually below with the
reason. Nothing else in the suite is altered. This file is the complete list of
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

Tests 29 and 30 are marked adapted because they are not Dieharder's statistics,
only the same idea. Dieharder's DAB DCT takes 256-point DCTs of many blocks and
looks at the maximum coefficient; test 29 takes low-frequency energy from one
large DCT. Dieharder's DAB filtering is a different construction again; test 30
applies a fixed 8-tap zero-sum filter to non-overlapping blocks. Under the
two-sample construction the exact statistic does not have to match a published
one, since both samples go through the same code, but the tables should not
imply these are ports. See `robust/doc/expansion-notes.txt`.

## Modified from upstream

- `robust/test_func.h` - 20 forward declarations added, in upstream's style.
  Nothing else in the file differs: +60 lines, no line removed.
- `robust/test_func.c`, 20 entries added to `functions_list[]` (+21), and the
  previously last entry re-emitted with the trailing comma the new entries
  require (-1). That replaced line is the file's only non-addition.
- `robust/Makefile` (+29/-6). Two parts, kept separate on purpose.

  *Registering the expansion:* the 20 new files appended to `TESTS_C` and
  `rtest_expansion.sh` appended to `SCRIPTS` so `make install` installs it -
  those two list assignments are two of the replaced lines - plus a new `check`
  target that runs `check.sh`, and a new `fast` target described below.

  *Three corrections,* which do change upstream behaviour and are listed here
  individually so the diff holds no surprises:

  1. `-L /usr/local/bin/` to `-L /usr/local/lib`. `-L` names a directory
     searched for libraries; `/usr/local/bin` holds executables. It linked only
     because `LIBRARY_PATH` or the system paths covered for it, and emitted
     ``ld: warning: search path '/usr/local/bin/' not found`` on every build.
     Reported to A. Shen as well; see issue 5 below.
  2. `clean` now uses `rm -f` and also removes `test-nonperiodic-boundary`.
     Without `-f` it printed a `No such file or directory` line per missing
     artifact on a fresh tree, which reads as a broken build. The boundary
     binary is this expansion's own addition, so leaving it behind was our bug.
  3. `uninstall` now removes `/usr/local/bin/rtest*.sh` rather than
     `rtest*m.sh`. The old glob did not match `rtest_expansion.sh`, which
     `install` copies, so an installed expansion battery was never removed.
     That asymmetry only exists because this expansion added the script to
     `SCRIPTS`, so it is ours to fix. `-f` added for the same reason as above.

  A `fast` target was added because overriding `FLAGS` on the command line does
  not work as the documentation used to suggest: `make` compares timestamps,
  not flags, so once `rtest` is built a `FLAGS=...` override prints
  ``make: `rtest' is up to date.`` and silently keeps the sanitizer binary.
  `make fast` relinks unconditionally without AddressSanitizer.

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
- `docs/`, the detail the README points to: `running-tests.md`,
  `reading-results.md` and `validation.md`.
- `reproducibility/generators/README.md`, explaining that that directory is
  an overlay onto a downloaded NIST STS 2.1.2 tree rather than a buildable
  one, with the steps in order.
- `tools/check-upstream-provenance.sh`, which re-derives this file's comparison.
- `LICENSING.md`, the component-by-component licence position.
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

  The same statistic was later made O(1) per bit instead of O(148). The 148
  templates are distinct 9-bit values, so at most one can equal the sliding
  window; a 512-entry reverse lookup replaces the scan over all templates at
  every bit. This is a speed change only, and was checked rather than assumed:
  on the fixture above, all 148 coordinates are identical before and after at
  both `-n 2000` and `-n 50000`, and the boundary regression still passes at
  every offset. Measured on the same machine, `-n 50000` went from 4.29 s to
  0.33 s of user time on an `-O2` build (17.9 s to 0.54 s on the default
  sanitizer build). The lookup asserts that no template repeats, so a
  transcription error in the table fails loudly instead of silently dropping
  counts.

## Issues found in upstream files

These were found while testing the expansion. Items 1 to 4 and 7 to 8 are in
Shen's original files and are left alone here, listed for him to decide on.
Items 5 and 6 were in `robust/Makefile`, which this expansion already modifies,
and have been corrected here as well as reported; both are described in the
"Modified from upstream" section above.

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
   Intel Mac, the configuration the line was written for, linking fails.

   **Corrected here** to `-L /usr/local/lib`, which removes the
   `ld: warning: search path '/usr/local/bin/' not found` that every build used
   to emit. Still worth reporting to A. Shen so upstream carries the same fix.
   The `-fsanitize=address` default is left as it is, with a `fast` target
   added beside it.

6. **`make uninstall` does not remove `rtest_expansion.sh`.** `install` copies
   everything in `SCRIPTS`, and this expansion appends `rtest_expansion.sh` to
   that list, but `uninstall` deletes `/usr/local/bin/rtest*m.sh` by glob and
   that name does not match. So an installed `rtest_expansion.sh` is left
   behind. The asymmetry is in Shen's `uninstall` line, but it is this
   expansion's addition to `SCRIPTS` that exposes it, so it is ours to fix.
   **Corrected here** to a `rtest*.sh` glob, which covers both.

7. **`robust/rtest.c` uses `sprintf` at lines 125 and 478.** Deprecated on
   macOS, and the only compiler warnings a user sees on an otherwise clean
   build. `snprintf` is the drop-in replacement. Harmless as written, since
   both buffers are comfortably large for their fixed-width formats.

8. **`robust/doc/Makefile`'s `clean` target uses `rm` without `-f`**, so on a
   tree that has not built the LaTeX documentation it prints four
   `No such file or directory` lines. `make clean` in `robust/` calls it, so
   those four lines appear even after the corrections above. Left unchanged
   because `robust/doc/Makefile` is otherwise byte-identical to upstream and
   editing it would add a fifth modified file for cosmetics.

## Not modified

`robust/rtest.c`, `robust/generators.c` / `.h`, the entire `kolmogorov-smirnov/`
engine, and every other upstream file are identical to upstream. Any issues found
in those files are upstream issues, not part of this expansion.
