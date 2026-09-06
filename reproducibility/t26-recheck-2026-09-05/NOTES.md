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
- etalon: the **512,000,000-byte prefix** of the campaign etalon, SHA-256
  `fa25613eca5d81265896f622c127a629c1dd1208968ef1bc0fc5596ae279246a`. See
  `../README.md` for why a prefix of that length is sufficient and how it was
  checked against the recorded values.

Produced by the repository revision recorded in `results.csv`, on macOS on
Apple Silicon. Both generators were run separately and are recorded separately
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

| Generator | max_p | objective | status |
|---|---:|---|---|
| Blum-Blum-Shub | 54 | 0.2137 | ok |
| Cubic Congruential | 54 | 0 | censored_zero |
| G-using-SHA-1 | 97 | 0 | censored_zero |
| Linear Congruential | 54 | 0.4447 | ok |
| Micali-Schnorr | 54 | 0.7597 | ok |
| Modular Exponentiation | 54 | 0.7597 | ok |
| Quadratic Congruential II | 54 | 3.0e-10 | ok |
| Quadratic Congruential I | 54 | 0.5985 | ok |
| XOR | 54 | 4.9e-10 | ok |

The cap of 120 was chosen to keep the exact backend tractable; it is not a
measured ceiling. `unresolved` means the value is below what the driver can
print, not that a detection has been established.
