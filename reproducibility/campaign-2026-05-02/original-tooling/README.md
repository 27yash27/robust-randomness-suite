# Original generation tooling, archived

`nist_test_generator_both.py` is the script that actually produced the campaign
inputs in April and May 2026. It is kept here for provenance.

**Do not run it.** It is unsafe on a machine that is doing anything else:

- it hardcodes a `/Users/...` path to the author's STS tree;
- it runs its cleanup at import time, before it asks for anything;
- that cleanup scans the whole process table and sends `SIGKILL` to any process
  whose command line looks like `assess` or a generator script, including ones
  it did not start;
- it discards `assess` stdout and stderr, treats the mere existence of an output
  file as success, only warns on a size mismatch, and prints a success message
  regardless.

Use `../../generators/generate_nist_inputs.py` instead. It takes explicit
`--sts` and `--out` paths, works in a directory you name, signals no process it
did not start, checks the produced byte count, records the command, exit code,
logs, hashes and toolchain versions, and exits non-zero if any generator fails.

The two produce the same bytes: the single `assess` invocation per generator and
the `"{selector}\n1\n0\n{streams}\n"` stdin recipe are preserved exactly, because
starting a fresh process per chunk would restart the generator and change the
output.
