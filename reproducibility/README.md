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

| status | meaning |
|---|---|
| `reported` | an ordinary p-value |
| `below_printing_floor` | smaller than the driver's 18 decimals can show; the true value is unknown, not a certified detection |
| `exactly_one` | legitimate at small sample sizes, suspect the KS underflow at large ones |
| `statistic_declined` | the test says it cannot compute on this input |
| `ran_out_of_data` | raise `--size-mb` |

`statistic_declined` is expected for Random Excursions (32) and its variant (33)
on the `01` fixture: NIST requires a minimum number of excursion cycles, and a
perfectly balanced stream never produces enough. The test is reporting its own
limit, which is why the runner does not treat it as a failure. On tests 22 to 41
at 300 MB, 18 of the 20 produce curves for both fixtures, and those two produce
them for the random-looking one only.

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
generators/nist_test_generator_both.py       batch generation
```

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

Eight of the nine reproduce exactly, including the three that use OpenSSL
big-integer arithmetic.

### The SHA-1 generator is the exception

The campaign input `bad_G_Using_SHA-1_1GB.bin`, dated 9 April 2026, was built
**before** the legacy inline SHA-1 transform was replaced with OpenSSL's
`SHA1()`. The recipe committed here contains that replacement, so it does not
rebuild that file. It rebuilds the corrected generator, and that was confirmed:
the regenerated 4 May 2026 file matches this recipe byte for byte.

So one row of the preserved campaign, `g03_g_using_sha`, was computed on an
input that the committed recipe no longer produces. Both files are listed in
`input-manifest.csv` with their hashes, so which is which stays unambiguous.
Anyone rebuilding from this guide gets the corrected SHA-1 generator, which is
the right one to use going forward, but its numbers will not match that row.

Reproduce the check with, from a built STS directory:

```bash
printf "1\n1\n0\n80\n" | ./assess 1000000     # generator 1, 80 x 1 Mbit = 10 MB
shasum -a 256 bad_generator_output.bin
```

Substitute the generator number 1 to 9 as listed in the guide.

## The inputs

`input-manifest.csv` lists the nine generator files with their size and SHA-256.
They are 1 GB each and are not in this repository.

The etalon was a 40 GB file. Its content does not affect validity, only its
size: XOR mode reads it as fast as it reads the generator. Any fixed file at
least as large as your generator will do.

## The campaign

`campaign-2026-05-02/` holds the original results, preserved as produced.
**Read its `NOTES.md` first.** In short: those numbers came from earlier tooling
that lived outside this repository, they cover tests 22 to 31 only, and the
tooling had a parsing defect whose effect on the recorded ceilings was checked
by rerunning the boundary on the original inputs. The notes give the commands
and what they returned.
