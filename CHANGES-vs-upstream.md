# Changes vs. upstream `rtest`

This suite is Alexander Shen's [`rtest`](https://github.com/alexander-shen/rtest)
plus an expansion of **20 new test statistics (numbers 22–41)**. Everything else
is upstream and byte-for-byte unmodified — so this file is the complete list of
what is new or changed, to make review against upstream straightforward.

## New test files (tests 22–41)

| File | # | Test |
|------|---|------|
| `robust/test_dna.c` | 22 | DNA |
| `robust/test_count1s_stream.c` | 23 | Count-the-1s (stream) |
| `robust/test_count1s_byte.c` | 24 | Count-the-1s (bytes) |
| `robust/test_parking.c` | 25 | Parking Lot |
| `robust/test_squeeze.c` | 26 | Squeeze |
| `robust/test_operm5.c` | 27 | OPERM5 |
| `robust/test_craps.c` | 28 | Craps |
| `robust/test_dab_dct.c` | 29 | DAB DCT |
| `robust/test_dab_filtering.c` | 30 | DAB Filtering |
| `robust/test_linear_complexity.c` | 31 | Linear Complexity |
| `robust/test_random_excursions.c` | 32 | Random Excursions |
| `robust/test_random_excursions_variant.c` | 33 | Random Excursions Variant |
| `robust/test_3d_spheres.c` | 34 | 3D Spheres |
| `robust/test_gcd.c` | 35 | Marsaglia–Tsang GCD |
| `robust/test_nonperiodic.c` | 36 | Non-overlapping Template Matching |
| `robust/test_runs_nist.c` | 37 | Runs |
| `robust/test_longest_run.c` | 38 | Longest Run of Ones |
| `robust/test_cusum.c` | 39 | Cumulative Sums |
| `robust/test_approximate_entropy.c` | 40 | Approximate Entropy |
| `robust/test_universal.c` | 41 | Maurer's Universal |

## Modified from upstream (only to register the 20 new tests)

- `robust/test_func.h` — 20 forward declarations added.
- `robust/test_func.c` — 20 entries added to `functions_list[]`.
- `robust/Makefile` — the 20 new files appended to `TESTS_C` (no other change).

## Added tooling and docs (not part of upstream)

- `scripts/` — Python sweep + ECDF-plotting tools (research tooling; several
  assume the author's local folder layout — set their path flags to run elsewhere).
- `robust/rtest_expansion.sh` — battery runner for tests 22–41 (the upstream
  `rtest1m.sh … rtest10g.sh` cover the original tests only).
- `robust/doc/expansion-notes.txt` — documentation of the expansion.
- `README.md` — this suite's README. Shen's original is kept as `README-upstream.md`.
- `CHANGES-vs-upstream.md` — this file.

## Issues found in upstream files (reported, not changed)

These were found while testing the expansion. They are in Shen's original files,
so they are left alone here and listed for him to decide on.

1. **`kolmogorov-smirnov/ksmirnov.c` — `psmirnov2x` underflows above ~2500
   samples.** The recursion returns 0, so `rtest` reports a p-value of exactly
   1.0 regardless of the data. Checked directly: at a fixed deviation of
   `1/sqrt(n)` it gives 0.702 at n=100 and 0.692 at n=2000, then exactly
   1.0 from n=3000 upward. The exact GMP routine (`-k`, `ks2mp.c`) returns
   0.685 at n=3400, so `-k` is a correct workaround. This matters because
   `rtest.c` permits `-p`/`-q` up to 10000.

2. **`robust/rtest.c` — stack overflow on high-dimension tests.**
   `test_p_value` holds both samples in stack VLAs sized `n * dimension`. Test
   36 (dimension 148) segfaults with no message above about `-p 3400` on macOS,
   and near half that on Linux, where `long double` is 16 bytes.
   `ulimit -s unlimited` avoids it.

3. **`kolmogorov-smirnov/ks2.c` has a leftover debug `printf` in `ks2bar`.**
   Harmless in practice: the Makefile links `ks2mp.c` instead, so this file is
   not compiled into `rtest`.

4. **`robust/Makefile` builds with `-fsanitize=address`** and hardcodes
   `/usr/local` include and library paths.

## Not modified

`robust/rtest.c`, `robust/generators.c` / `.h`, the entire `kolmogorov-smirnov/`
engine, and every other upstream file are identical to upstream. Any issues found
in those files are upstream issues, not part of this expansion.
