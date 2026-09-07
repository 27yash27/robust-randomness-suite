# Licensing

**Intent: this suite is meant to be distributed under the GNU General Public
License, version 2 or later.** Alexander Shen's stated goal is that it can be
packaged in Linux distributions under the GPL, and the components below are
compatible with that.

**Status: not yet in force.** The repository carries no `LICENSE` file, because
two decisive permissions are not ours to give: one from Alexander Shen, and one
from Yann Ollivier, whose notice on `spectral_tests/` is **not GPL-compatible**
as it stands. Shen's grant alone does not settle the question. See "What is
still needed".

## What this repository is made of

| Component | Where | Origin | Terms |
|---|---|---|---|
| The `rtest` framework: driver, generator layer, KS engine, tests 0-21, and every supporting directory | 113 files, byte-identical to upstream | Alexander Shen (method with Andrey Romashchenko), LIRMM / CNRS / Univ. Montpellier | **No license declared upstream.** See below. |
| Registration of the 20 new tests | `robust/test_func.c`, `robust/test_func.h`, `robust/Makefile` | Shen's files, edited here | follows the framework |
| Tests 22-28, 34 | `test_dna.c`, `test_count1s_*.c`, `test_parking.c`, `test_squeeze.c`, `test_operm5.c`, `test_craps.c`, `test_3d_spheres.c` | **Diehard and Dieharder** both, per `robust/doc/expansion-notes.txt` | **GPL**, through the Dieharder side. |
| Tests 29, 30, 35 | `test_dab_dct.c`, `test_dab_filtering.c`, `test_gcd.c` | **Dieharder** (R. G. Brown) | **GPL.** |
| Test 31 | `test_linear_complexity.c` | **NIST and Dieharder** both | **GPL**, through the Dieharder side. |
| Tests 32, 33, 36-41 | `test_random_excursions*.c`, `test_nonperiodic.c`, `test_runs_nist.c`, `test_longest_run.c`, `test_cusum.c`, `test_approximate_entropy.c`, `test_universal.c` | **NIST Statistical Test Suite** (SP 800-22) | Work of a U.S. government agency: **public domain**, freely combinable. |
| Spectral test support | `spectral_tests/rand.h` and `spectral_tests/rand.cpp`, **which is compiled and linked into the `rtest` binary** | **Yann Ollivier, 1997-1999** | Notice retention and change description, **plus "may not be sold" and free use only in free programs. Not GPL-compatible.** See below. |
| Everything added here | `scripts/`, `reproducibility/`, `robust/check.sh`, `robust/test_nonperiodic_boundary.c`, `robust/rtest_expansion.sh`, the 20 `test_*.c` files | Yash Belani | intended GPL-2.0-or-later, with the framework |

`CHANGES-vs-upstream.md` lists exactly which files differ from upstream, and
`tools/check-upstream-provenance.sh` re-derives that list against the pinned
upstream revision `6ae81dcec44d5cbe46c7bc58620c275a7cfa3c1d`.

## Why GPL is the right target

Twelve of the twenty added tests draw on Dieharder, which is GPL, and a combined
work that includes GPL code inherits the GPL. This is an obligation, not a
preference. NIST STS code is public domain and Marsaglia released Diehard
without restriction, so neither conflicts. So GPL-2.0-or-later is simultaneously
what the Dieharder ancestry requires and what Shen wants for distribution
packaging.

**One component does conflict**, and it is not resolved by anything Shen can
grant: the Ollivier notice on `spectral_tests/`. See point 2 below.

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

**2. A GPL-compatible grant from Yann Ollivier, or the removal of his code.**
`spectral_tests/rand.h` and `spectral_tests/rand.cpp` both carry his notice.
Beyond notice retention and change description, it says:

> This software may not be sold. … This software or any modified version of it
> may be freely used in free programs. … If you want to use it in a program you
> sell, contact me

That is a field-of-use restriction, and it is **not compatible with the GPL**.
GPL-2.0 §1 expressly permits charging a fee to distribute copies, and §6
forbids imposing any further restriction on recipients. An earlier version of
this document described the terms as notice-retention only and called them
GPL-compatible; that was wrong.

This is not academic. `rand.cpp` is listed in `CPP_CODE` in `robust/Makefile`
and is compiled and linked into the `rtest` binary the documented build
produces, so the restriction attaches to the binary every user builds.

Three ways out, and one has to be chosen before the suite is released under any
licence: ask Ollivier for a GPL-compatible grant; make the spectral test an
optional component so the default binary carries none of his code; or drop it.

One obligation the notice imposes **is** already met: `rand.cpp:20-23` records
the "revision by andrei" modification inline, which is the change description
it asks for. Both files are byte-identical to upstream.

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
