# What has been validated, and what has not

Short version: tests 22 to 31 were run against the nine NIST reference
generators in one exploratory campaign. Tests 32 to 41 have no campaign of
their own. Nothing here is an estimated false-positive rate.

## The campaign

Nine NIST reference generators, **tests 22 to 31 only**. The three intended
controls (Blum-Blum-Shub, Linear Congruential, Micali-Schnorr) crossed the
1e-10 threshold on no test; the other six crossed it on at least one.

Read those as recorded exploratory outcomes, for three reasons:

- Nine generators over ten tests cannot establish a false-positive rate.
- The minimum over a sweep is biased low by the search itself.
- 27 of the 90 rows report exactly 1.0, through the backend that is known to
  underflow at that sample size. See `reading-results.md`.

The campaign metadata records XOR mode as enabled throughout, so this
repository holds no no-XOR comparison. Any claim that results agreed with and
without the XOR step is **not** supported by what is committed here.

## Why the exact p-values cannot be reproduced

Two of the campaign inputs cannot be recreated from anything published: the
40 GB etalon, and the pre-fix SHA-1 generator. So the campaign is archived
evidence, not a reproduction target.

What is committed: the modified NIST STS sources and the guide needed to
rebuild the nine generators, a manifest with the SHA-256 of each input, and
the campaign output with a note on how it was produced and what has and has
not been checked. See `reproducibility/`.

## The saturated rows

36 campaign rows report a p-value of exactly 1.0. Tests 29, 30 and 31 were
rerun on both KS backends at the same settings: the default routine returns
exactly 1.0 while the exact routine (`-k`) returns ordinary values (0.872,
0.565, 0.759 at 3000 samples). The saturation is arithmetic, not data.

Test 25 was **not** rerun. It shares the signature in the campaign, but that
is inference rather than measurement.

That check establishes the mechanism on a sample of settings. It does not
replace the 36 recorded rows, which would need those rows rerun with
`--ksexact`. Raw logs and commands:
`reproducibility/campaign-2026-05-02/saturation-check/`.

## Reproducing or extending it

`scripts/run_maximal_p_sweep.py` reruns the sweep against generator files you
supply. The upstream `rtest*.sh` batteries cover tests 0, 1 and 3 to 16.
`reproducibility/README.md` explains the run statuses, the per-test input
budget, and how to rebuild the nine research generators.
