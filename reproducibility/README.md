# Reproducibility

What you need to rebuild the inputs, rerun the experiments, and check the
published numbers.

## Run the experiments yourself

The quickest path, needing nothing but this repository:

```bash
cd robust && make && cd ..
python3 scripts/run_all_experiments.py --repo . --out ../experiments --size-mb 300
```

That builds three inputs from recorded recipes, runs all twenty added tests
(22 to 41) at the sample sizes fixed in `scripts/robust_test_catalog.py`, and
writes one SVG per test and fixture, a `results.csv` with the exact command,
revision, backend, raw p-value and numeric status of every run, an input
manifest with SHA-256 hashes, and the raw logs.

One fixture is a SHAKE-256 stream that should look random; the other is the
bytes `01` repeated, which should be detected. Comparing the two shows what a
test does when it sees something and when it does not.

Read `numeric_status` in the results rather than only the p-value:

| status | meaning | fails the run? |
|---|---|---|
| `reported` | an ordinary p-value in (0,1) | no |
| `numerically_unresolved` | printed as zero or a small negative; below what the driver's fixed decimals can show. Not a bound, not a certified detection | no |
| `exactly_one` | the upper limit; legitimate at small sample sizes, suspect the KS underflow at large ones | no |
| `statistic_declined_too_few_cycles` | the test said so itself, confirmed from its own `-v` output | no |
| `ran_out_of_data` | the input was too small; raise `--size-mb` | no |
| `out_of_range` | a value outside [0,1], which is not a p-value | yes |
| `numerical_failure` | a non-finite value | yes |
| `parse_error` | the wrong number of result values | yes |
| `no_output_unexplained` | silent, and the `-v` re-run gave no recognised reason | yes |
| `process_failure` | `rtest` exited non-zero | yes |

There is a companion column, `observed_reason`. It is empty except where a run
was predicted undersized and then failed to report a value: there it holds what
the statistic actually said, while `numeric_status` records `ran_out_of_data`.

**Three scripts, three vocabularies.** They are different tools and their tables
are not interchangeable. The one above is `run_all_experiments.py`. The other
two are shorter:

| script | statuses |
|---|---|
| `run_all_experiments.py` | the ten above, plus `observed_reason` |
| `run_maximal_p_sweep.py` | `ok`, `censored_zero`, `eof`, `rtest_failed`, `unresolved`, `parse_error` |
| `reproduce_randomness_demo.py` | `finite_reported`, `exactly_one`, `zero_unresolved`, `unresolved_tie`, `incomplete_samples`, `numerical_failure`, `parse_error`, `eof`, `process_failure` |

The correspondences worth knowing: the sweep's `censored_zero` is this table's
`numerically_unresolved`, and the sweep's `ok` covers both `reported` and
`exactly_one`, so a sweep row reading `ok` at a large sample size still deserves
the scrutiny `docs/reading-results.md` describes.

Curves are drawn whenever the statistic samples exist, including runs whose
p-value is zero or one; those panels are labelled "numerically unresolved"
rather than given an invented bound.

`statistic_declined_too_few_cycles` is expected for Random Excursions (32) and
its variant (33) on the ASCII fixture. NIST requires a minimum number of
excursion cycles. The bytes `0x30 0x31` carry five one-bits in every sixteen, so
the walk drifts steadily downward rather than returning to zero, and too few
cycles form. That is the test reporting its own limit.

**A decline is not evidence against the generator.** It is a statement about the
sample size and the data available, nothing more. The clearest demonstration is
that these same two tests also decline at some sample sizes on the `random_like`
SHAKE-256 fixture, which is this repository's own example of a stream that
should look random. If a decline meant the generator had been rejected, that
fixture would be rejected too.

When a run was already flagged as undersized before it started, the binding
constraint is the input budget rather than anything about the data, so it is
recorded as `ran_out_of_data` with the statistic's own words preserved in the
`observed_reason` column beside it.

A full run of all twenty tests at `--size-mb 700` produces **200 runs: 182
curves drawn and 18 declines**, with every one of the twenty tests yielding at
least one curve. 200 is the complete plan: 20 tests x 5 sample sizes x 2
fixtures. Of the 200, 172 report an ordinary p-value, 7 sit at exactly one and
3 are numerically unresolved; all 182 of those are drawn and annotated rather
than dropped. The 18 declines are tests 32 and 33, which is where the
`random_like` counts below come from.

The 18 break down as all ten `structured` runs of both tests, plus four of the
five `random_like` runs of each. That second half is the point made above: the
fixture that is supposed to look random also produces declines, so a decline
cannot be read as a verdict on the generator.

These numbers are configuration-dependent, so state the configuration with
them. Measured on **macOS 26.6.2, arm64**, Python 3.9.6, `--size-mb 700`, the
**default `psmirnov2x` backend** (no `--ksexact`), on an `-O2` build from
`make -C robust fast`. A different platform, input size or KS backend will move
the reported/unresolved split in particular; re-derive rather than quote these
if any of those differ. At `--size-mb 300` tests 32 and 33 cannot reach their
two largest sample sizes at all, and those runs are recorded as
`ran_out_of_data`.

### Input budget

`-n` is not a bit count for every test. Tests 32 and 33 read a million 32-bit
integers per invocation, so at the catalog's largest sample size they need
`(80 + 80) x 1,000,000 x 4 = 640 MB` of tested data. The runner reports which
planned runs your `--size-mb` cannot support before it starts, so an
undersized recipe shows up as a stated limit rather than a mysterious end of
input. Measured requirements at the largest catalog sample size:

| Test | MB needed | Test | MB needed |
|---|---:|---|---:|
| 22 | 84 | 32 | **640** |
| 23 | 154 | 33 | **640** |
| 24 | 102 | 34 | 8 |
| 25 | 10 | 35 | 64 |
| 26 | 111 | 36 | 1 |
| 27 | 192 | 37 | 64 |
| 28 | 162 | 38 | 64 |
| 29 | 2 | 39 | 64 |
| 30 | 2 | 40 | 64 |
| 31 | 2 | 41 | 64 |

Use `--size-mb 700` to cover every planned run. At 300 MB everything completes
except the four largest runs of tests 32 and 33.

For a single test with the curves side by side, use `scripts/compare_curves.py`
instead. For a shorter run, `scripts/reproduce_randomness_demo.py` covers test
37 only.

## Rebuild the nine research generators

`generators/` holds everything needed to rebuild the generators used in the
validation campaign: the modification guide, the changed NIST STS source files,
and the batch generation script.

```
generators/NIST_STS_Modifications_Guide.md   step by step, with the reasoning
generators/makefile                          OpenSSL include and link flags
generators/src/generators.c                  OpenSSL big-integer math, XOR overflow fix, SHA-1
generators/src/utilities.c                   bit packing, early return, case 9 dispatch
generators/include/generators.h              SHA1 renamed to sha1Generator
generators/generate_nist_inputs.py           batch generation
```

Once `assess` is built in the patched tree:

```bash
python3 reproducibility/generators/generate_nist_inputs.py \
    --sts /path/to/sts-2.1.2 --out ./inputs --size-mb 1000
```

It works only inside the directory you name, records each command, exit code,
log, byte count and SHA-256, and exits non-zero if any generator fails or
produces the wrong size. Note that the patched `assess` exits 1 even when it
succeeds, because the bit-packing change returns before the statistical tests;
the script therefore gates on the completion marker and the byte count, and
records the exit code separately.

The script that actually produced the campaign inputs is archived under
`campaign-2026-05-02/original-tooling/` with a warning: it hardcodes a personal
path and kills processes by name at import time. Do not run it.

The STS menu numbers and the campaign identifiers are not the same, so check
this mapping before regenerating anything:

| STS selector | Generator | Campaign identifier |
|---:|---|---|
| 1 | Linear Congruential | `g04_linear_congruential_1gb` |
| 2 | Quadratic Congruential I | `g08_quadratic_congruential_i` |
| 3 | Quadratic Congruential II | `g07_quadratic_congruential_ii` |
| 4 | Cubic Congruential | `g02_cubic_congruential_1gb` |
| 5 | XOR | `g09_xor_1gb` |
| 6 | Modular Exponentiation | `g06_modular_exponentiation_1gb` |
| 7 | Blum-Blum-Shub | `g01_blum_blum_shub` |
| 8 | Micali-Schnorr | `g05_micali_schnorr_1gb` |
| 9 | G-using-SHA-1 | `g03_g_using_sha` |

Download NIST STS 2.1.2 from
https://csrc.nist.gov/projects/random-bit-generation/documentation-and-software,
apply these files, and follow the guide.

### This path has been checked

On 5 September 2026 the modified STS was rebuilt from exactly these files on
macOS with OpenSSL 3, and the first 10 MB of each generator was regenerated and
compared byte for byte against the campaign inputs.

| Generator | Result |
|---|---|
| Linear Congruential | identical |
| Quadratic Congruential I | identical |
| Quadratic Congruential II | identical |
| Cubic Congruential | identical |
| XOR | identical |
| Modular Exponentiation | identical |
| Blum-Blum-Shub | identical |
| Micali-Schnorr | identical |
| **G-using-SHA-1** | **differs, see below** |

Eight of the nine match **over the first 10,000,000 bytes**, which is what was
compared. The remaining 990,000,000 bytes of each 1 GB file were not checked.

### The SHA-1 generator is the exception

The campaign input `bad_G_Using_SHA-1_1GB.bin`, dated 9 April 2026, was built
**before** the legacy inline SHA-1 transform was replaced with OpenSSL's
`SHA1()`. The recipe committed here contains that replacement, so it does not
rebuild that file. It rebuilds the corrected generator, and that was confirmed over the same
10,000,000-byte prefix against the regenerated 4 May 2026 file.

So one row of the preserved campaign, `g03_g_using_sha`, was computed on an
input that the committed recipe no longer produces. Both files are listed in
`input-manifest.csv` with their hashes, so which is which stays unambiguous.
Anyone rebuilding from this guide gets the corrected SHA-1 generator, which is
the right one to use going forward, but its numbers will not match that row.

Reproduce the check with, from a built STS directory:

```bash
rm -f bad_generator_output.bin                  # assess appends; a stale file
                                                # would silently extend
printf "1\n1\n0\n80\n" | ./assess 1000000     # generator 1, 80 x 1 Mbit = 10 MB
shasum -a 256 bad_generator_output.bin
```

Substitute the generator number 1 to 9 as listed in the guide.

## The inputs, and what you can and cannot reproduce

`input-manifest.csv` lists the nine generator files with their size and SHA-256.
They are 1 GB each and are not in this repository; rebuild them with the recipe
above.

### The etalon: a 1 GB prefix, not 40 GB

The etalon used in the campaign is a 40 GB file, which looked impossible to
publish. It does not have to be published in full.

In XOR mode both samples are drawn from the tested generator and only the second
group is XOR-ed with etalon blocks. Writing A for the bytes the untransformed
sample takes and B for the transformed one, the tested file supplies A+B and the
etalon supplies B. So

    etalon bytes = B < A + B = tested bytes <= tested file size.

Every tested file in this campaign is 1,000,000,000 bytes, so **no run can read
more than 1 GB of etalon.** That is the whole argument, and it holds whatever
the statistic does internally.

An earlier version of this file claimed a factor of two rather than one, on the
grounds that A and B are equal. They are not. Statistics that read until a
data-dependent stopping condition can consume very unequal amounts. Squeeze on a
zero-filled input is the clearest case:

```
robust/rtest -x -f zero.bin -e reference.bin -p 1 -q 1 -n 0 -d 1 -t 26 -r 2
  Used 9621132 bytes from the test generator [0]
  Used 9221124 bytes from the etalon generator [1]
```

That is 96% of the tested consumption, not 50%. The ratio was measured at 0.500
for test 23, 0.772 for test 28 and 0.958 for test 26 on that fixture. Only the
inequality above is safe to rely on.

A 1,000,000,000-byte prefix was cut and checked, including a data-dependent test
at the ceiling the recheck sweep reached:

| Case | With the 1 GB prefix | Recorded |
|---|---|---|
| t23, BBS, p=q=1953 | 0.261534995558913019 | 0.261534995558913 |
| t26, Cubic Congruential, p=q=30 | 0.000000000000000222 | 2.22e-16 |
| t26, G-using-SHA-1, p=q=97 | 0.000000000000000444 | (recheck sweep ceiling) |

Its SHA-256 is
`71a1e24ce3cd639c4910bc918005910012a1471a22baf84e0999ce3aaf18fa68`, and it is the
first 1,000,000,000 bytes of the file whose full SHA-256 is
`64b26aacdbb69488da061d2b8b1ef74f106be69e128dc582e2e11be52f709ce1`.

Those are three spot checks, not a rerun of the 90-row campaign. What is
established is the bound above plus agreement on those three settings.

**The prefix is not published yet.** It is small enough for a data archive with
a stable identifier, and publishing it is the remaining step for independent
historical reproduction.

The etalon is a fixed XOR mask, not a trusted source of randomness. Its quality
does not affect validity, but its *contents* determine the observed samples and
p-values, which is exactly why substituting a different file reproduces the
method and not the numbers.

**The SHA-1 generator input** predates the OpenSSL fix, as described above, and
is the other input a third party cannot currently obtain.

Until that prefix and the old SHA-1 file are published, treat
`campaign-2026-05-02/` as **archived evidence**: a record of what was run and
what it produced, which has been spot-checked here but which a third party
cannot yet re-derive. To generate results that
someone else can check number for number, run a new campaign with an etalon
built from a published recipe, for example

```bash
python3 -c "from hashlib import shake_256; from pathlib import Path; \
Path('etalon.bin').write_bytes(shake_256(b'my etalon v1').digest(1_000_000_000))"
```

and record its hash alongside the results. `scripts/run_all_experiments.py`
already works this way, which is why its outputs are reproducible by anyone.

## What is in this directory

```
README.md                     this file
input-manifest.csv            every campaign input, with size and SHA-256
generators/                   the patched NIST STS sources, the guide, and
                              generate_nist_inputs.py
campaign-2026-05-02/          the original campaign output, its provenance
                              notes, and the archived tooling that produced it
t26-recheck-2026-09-05/       the test-26 recheck: 16 boundary runs with raw
                              logs, a nine-generator sweep, and make_summary.py
```

## The campaign

`campaign-2026-05-02/` holds the original results, preserved as produced.
**Read its `NOTES.md` first.** In short: those numbers came from earlier tooling
that lived outside this repository, they cover tests 22 to 31 only, and the
tooling had a parsing defect whose effect on the recorded ceilings was checked
by rerunning the boundary on the original inputs. The notes give the commands
and what they returned.
