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

**This path has not been re-walked from scratch.** The files are the ones that
produced the campaign inputs, but nobody has yet rebuilt the generators from
this guide on a clean machine and confirmed the output matches the hashes in
`input-manifest.csv`. Until someone does, treat it as documentation rather than
a verified reproduction. Doing that check is the single most useful thing a
reviewer could do here, and the hashes are recorded precisely so it is possible.

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
