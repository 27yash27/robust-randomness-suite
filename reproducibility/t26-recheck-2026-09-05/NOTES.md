# Test 26 recheck, 5 September 2026

Why: in `../campaign-2026-05-02/maximal_p.csv`, two test-26 (Squeeze) rows stop
at `max_p` 30 with `bad_reason_at_ceiling` of `eof_zero`. That label came from
tooling that could not tell end of input from a p-value below the printed
resolution. These runs establish which it was.

**It was not end of input.** No run here printed an end-of-input message, and
the exact backend returns decreasing positive values where the default backend
prints zero. The sweep stopped for a numerical reason, not a capacity one, so
the recorded ceiling of 30 and the recorded objective both understate what the
data supports.

## What was run

Two generators, four sample sizes, both KS backends: 16 runs. `results.csv` has
one row each, with the exact command, return code, whether an end-of-input
message appeared, and the path to the raw output. `logs/` holds the unedited
stdout and stderr of every run.

Inputs:

- tested: `bad_Cubic_Congruential_1GB.bin` and `bad_G_Using_SHA-1_1GB.bin`, the
  same 9 April 2026 campaign files, hashed in `../input-manifest.csv`
- etalon: **the 16 boundary runs used a 512,000,000-byte prefix** of the
  campaign etalon, SHA-256
  `fa25613eca5d81265896f622c127a629c1dd1208968ef1bc0fc5596ae279246a`. The logs
  in `logs/` are those runs.

  **The nine-generator sweep in `full-sweep/` used the original 40 GB etalon**,
  not a prefix. Its `campaign.json` records that path, which is correct. The two
  parts of this recheck therefore used different reference bytes, and both are
  identified above rather than assumed to be the same.

  `../README.md` explains the prefix bound and shows the same values reproducing
  from a 1 GB prefix. A 512 MB prefix is sufficient for the boundary settings
  used here; 1 GB is the figure that is provably sufficient for any run on a
  1 GB tested file.

Produced on macOS on Apple Silicon. `results.csv` records the command, sample
size, backend, return code, whether an end-of-input message appeared, and the
log path for each run. It does **not** record a producing revision or the input
hashes; those were not captured at the time and are not reconstructed here. The
commands in that column are written with `<gen>` and
`<etalon-1GB-prefix>` placeholders rather than the absolute private paths; the
files they stand for are the ones named just above. Both generators were run separately and are recorded separately
even though their outputs agree at these settings.

## Caveat

`bad_G_Using_SHA-1_1GB.bin` is the pre-fix SHA-1 input. The committed generator
recipe no longer rebuilds it, so that half of this recheck describes a generator
that has since been corrected. See `../README.md`.

## A full sweep, for the same reason

`full-sweep/` holds a complete test-26 sweep over all nine generators with
`--ksexact`, capped at 120 samples, run with the current tooling against the
original 40 GB etalon. It shows the same thing from the other direction: the two
generators the old campaign stopped at 30 now run to 54 and 97, and where the
value falls below the printed resolution the result is recorded as
`censored_zero` with a threshold verdict of `unresolved` rather than being
discarded as exhausted input.

| Generator | max_p | final objective | status | beats 1e-10 |
|---|---:|---|---|---|
| Blum-Blum-Shub | 54 | 0.213675 | ok | no |
| Cubic Congruential | 54 | 0 | censored_zero | unresolved |
| G-using-SHA-1 | 97 | 0 | censored_zero | unresolved |
| Linear Congruential | 54 | 0.444707 | ok | no |
| Micali-Schnorr | 54 | 0.759708 | ok | no |
| Modular Exponentiation | 54 | 0.759708 | ok | no |
| Quadratic Congruential II | 54 | 3e-18 | ok | yes |
| Quadratic Congruential I | 54 | 0.598484 | ok | no |
| XOR | 54 | 4.88425e-06 | ok | no |

Regenerate this table with `python3 make_summary.py`; it is printed from
`full-sweep/maximal_p.csv` rather than typed, because an earlier hand-written
version of it misreported two of these values.

The cap of 120 was chosen to keep the exact backend tractable; it is not a
measured ceiling. `unresolved` means the value is below what the driver can
print, not that a detection has been established. The recorded `max_p` values
are where each sweep stopped under that cap; the committed summary does not by
itself identify which input exhausted first, and the per-probe histories for
this sweep were not preserved.
