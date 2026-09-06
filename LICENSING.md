# Licensing

**Intent: this suite is meant to be distributed under the GNU General Public
License, version 2 or later.** Alexander Shen's stated goal is that it can be
packaged in Linux distributions under the GPL, and the components below are
compatible with that.

**Status: not yet in force.** The repository carries no `LICENSE` file, because
the decisive permission is not ours to give. See "What is still needed".

## What this repository is made of

| Component | Where | Origin | Terms |
|---|---|---|---|
| The `rtest` framework: driver, generator layer, KS engine, tests 0-21, and every supporting directory | 113 files, byte-identical to upstream | Alexander Shen (method with Andrey Romashchenko), LIRMM / CNRS / Univ. Montpellier | **No license declared upstream.** See below. |
| Registration of the 20 new tests | `robust/test_func.c`, `robust/test_func.h`, `robust/Makefile` | Shen's files, edited here | follows the framework |
| Tests 22-28, 34 | `test_dna.c`, `test_count1s_*.c`, `test_parking.c`, `test_squeeze.c`, `test_operm5.c`, `test_craps.c`, `test_3d_spheres.c` | **Diehard and Dieharder** both, per `robust/doc/expansion-notes.txt` | **GPL**, through the Dieharder side. |
| Tests 29, 30, 35 | `test_dab_dct.c`, `test_dab_filtering.c`, `test_gcd.c` | **Dieharder** (R. G. Brown) | **GPL.** |
| Test 31 | `test_linear_complexity.c` | **NIST and Dieharder** both | **GPL**, through the Dieharder side. |
| Tests 32, 33, 36-41 | `test_random_excursions*.c`, `test_nonperiodic.c`, `test_runs_nist.c`, `test_longest_run.c`, `test_cusum.c`, `test_approximate_entropy.c`, `test_universal.c` | **NIST Statistical Test Suite** (SP 800-22) | Work of a U.S. government agency: **public domain**, freely combinable. |
| Spectral test support | `spectral_tests/rand.h` and companions | **Yann Ollivier, 1997-1999** | Free distribution and modification, provided the notice is kept and changes are described. See below. |
| Everything added here | `scripts/`, `reproducibility/`, `robust/check.sh`, `robust/test_nonperiodic_boundary.c`, `robust/rtest_expansion.sh`, the 20 `test_*.c` files | Yash Belani | intended GPL-2.0-or-later, with the framework |

`CHANGES-vs-upstream.md` lists exactly which files differ from upstream, and
`tools/check-upstream-provenance.sh` re-derives that list against the pinned
upstream revision `6ae81dcec44d5cbe46c7bc58620c275a7cfa3c1d`.

## Why GPL is the right target

Twelve of the twenty added tests draw on Dieharder, which is GPL, and a combined
work that includes GPL code inherits the GPL. This is an obligation, not a
preference. Nothing else here conflicts with it: NIST STS code is public domain,
Marsaglia released Diehard without restriction, and the Ollivier notice permits
distribution and modification. So GPL-2.0-or-later is simultaneously what the
Dieharder ancestry requires and what Shen wants for distribution packaging.

The per-test origins are taken from `robust/doc/expansion-notes.txt`, which
records them test by test. Where a test is marked "Diehard + Dieharder" the
Dieharder side is what determines the licence.

## What is still needed

Two things, neither of which this repository can settle on its own.

**1. Shen's written confirmation.** Upstream `rtest` has no `LICENSE` file and
no copyright notice in its sources. Absent an explicit grant, the default in
most jurisdictions is that all rights are reserved by the author. He is the
copyright holder of 113 of the files here, so only he can license them. What is
needed is a short written statement that `rtest` is released under
GPL-2.0-or-later, ideally added to his own repository. Until then this document
records an intention, not a grant, and **the combined work should not be
redistributed.**

**2. The Ollivier notice.** `spectral_tests/rand.h` carries its own terms:
distribution is free provided the whole notice travels with it, and any
modification must be accompanied by a description of the changes. Those
conditions are compatible with the GPL, but they must be honoured: keep the
notice, and if that file is ever modified, record what changed. It is currently
byte-identical to upstream.

## Attribution

- The robust two-sample construction is by **Alexander Shen** and **Andrey
  Romashchenko** (LIRMM, CNRS / Univ. Montpellier), cited jointly for the method
  in Shen's own `robust/doc/tests-description.tex`. The `rtest` implementation
  is Shen's. His description
  is preserved verbatim as `README-upstream.md`. Papers:
  [lirmm-03065320](https://hal.archives-ouvertes.fr/lirmm-03065320/),
  [lirmm-03371151](https://hal.archives-ouvertes.fr/lirmm-03371151/).
- The statistics are adapted from **Diehard** (George Marsaglia), **Dieharder**
  (Robert G. Brown), and the **NIST Statistical Test Suite** (SP 800-22).
- `spectral_tests/` includes code by **Yann Ollivier** (1997-1999).
- The 20 added tests, the tooling under `scripts/`, and the reproducibility
  package are by **Yash Belani**.
