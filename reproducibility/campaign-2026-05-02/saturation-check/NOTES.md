# Why 36 campaign rows report exactly 1.0

The campaign rows for tests 25, 29, 30 and 31 all ran above 2500 samples on the
default KS routine and all returned exactly 1.0. These runs test whether that is
the `psmirnov2x` underflow or something about the data, by running the same
settings on both backends.

`results.csv` records each run with its command and the path to its raw log.
Inputs: `bad_Blum-Blum-Shub_1GB.bin` from the 9 April campaign set, against a
1,000,000,000-byte prefix of the campaign etalon (SHA-256
`71a1e24ce3cd639c4910bc918005910012a1471a22baf84e0999ce3aaf18fa68`). Sample size
3000, above the threshold where the default routine is known to fail and small
enough for the exact routine to finish.

Three of the four affected tests were checked: 29, 30 and 31. In each the
default routine returns exactly 1.0 while the exact routine returns an ordinary
p-value at the same settings. The saturation is arithmetic, not data. Test 25
was not rerun; it shares the same signature in the campaign, but that is
inference rather than measurement.

This checks the mechanism on a sample of settings. It does not replace the 36
recorded rows, which would need those rows rerun with `--ksexact`.
