# Reading a result, and the numerical limits

## Read the result

- **Between 0.01 and 0.99**: that test found nothing. It does not certify the
  generator; it means this statistic saw nothing at this sample size.
- **Very small, say below 1e-6**: evidence that the test can tell your generator
  from random. Smaller means stronger evidence. The campaign treated below
  1e-10 as a detection.
- **Exactly 1.0**: legitimate at very small sample sizes, where the discrete
  KS distribution really does reach 1. At larger sample sizes it usually means
  the p-value routine underflowed. See the note below.
- **`oops, eof in generator`**: your files are too small for that test. Use
  bigger ones or lower `-p` and `-q`.

Two things that will bite you:

- **The safe sample size depends on your platform.** The default p-value
  routine works in `long double`, which is 8 bytes on Apple Silicon and 16
  bytes with a wider exponent on x86-64. On Apple Silicon it underflows above
  roughly 2500 samples and returns exactly 1.0 whatever the data says; on
  x86-64 Linux it has been observed to agree with the exact routine at 3000
  and beyond. Measure it on your own machine with `make check` and a few
  spot comparisons against `-k`. `-k` selects the GMP backend, which avoids
  this underflow and is slower; it is not free of every limit, as the next two
  points describe.
- **A p-value of exactly 1.0 is not automatically a bug.** At very small
  sample sizes the discrete KS distribution genuinely reaches 1. Above a few
  dozen samples, treat it as the underflow above until you have checked with
  `-k`.
- **Very small p-values are printed as zero.** The driver prints 18 decimal
  places, so anything below 1e-18 comes out as `0.000000000000000000`, and the
  default routine can print a small negative value instead through
  cancellation. Both mean "smaller than can be shown here", not "no result",
  and neither certifies a particular value. `-k` removes the cancellation but
  not the 18-decimal output, and the exact routine reduces its own denominator
  under 2^128, which can truncate a very small numerator to zero as well. Treat
  such a point as "too small to report" rather than as a measured number.
- **A single p-value is not the answer.** The p-value is not monotone in the
  sample size, so a real signal can appear at one size and vanish at another.
  Run several sizes and take the smallest value you see. That minimum is a
  search summary over many sample sizes and coordinates, not a calibrated
  p-value: it is biased low by the search itself. Fix the family of tests,
  coordinates and sizes in advance and correct for multiplicity, or report the
  minimum as exploratory and judge it against a small fixed threshold.

## Known bugs

Both are in upstream files and are left unchanged here.

1. `psmirnov2x` in `kolmogorov-smirnov/ksmirnov.c` underflows above about 2500
   samples and returns a p-value of exactly 1.0. Use `-k`, or keep `-p` and `-q`
   at 2000 or below.
2. `test_p_value` in `robust/rtest.c` keeps both samples on the stack, so
   high-dimension tests such as test 36 segfault silently above roughly
   `-p 3400` on macOS and half that on Linux. Raise the stack limit first.
