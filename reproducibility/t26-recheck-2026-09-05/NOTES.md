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
- etalon: a **1,000,000,000-byte prefix** of the campaign etalon, SHA-256
  `71a1e24ce3cd639c4910bc918005910012a1471a22baf84e0999ce3aaf18fa68`. See
  `../README.md` for why a prefix of that length is sufficient. The 16 boundary
  runs below were originally executed against a 512 MB prefix and give the same
  values; the surviving logs are those runs.

  `full-sweep/campaign.json` records the etalon path as the original
  `etal.bin`, because the sweep script writes the path it was given. That sweep
  was run against the prefix. The committed metadata does not resolve this by
  itself, which is a gap in the record rather than a claim you should take on
  trust.

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
`--ksexact`, capped at 120 samples, run with the current tooling and the 512 MB
etalon prefix. It shows the same thing from the other direction: the two
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
