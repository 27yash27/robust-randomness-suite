# This directory is an overlay, not a buildable tree

Running `make` here will fail, and that is expected. What is committed is the
set of files that **differ** from NIST's Statistical Test Suite 2.1.2, plus the
guide describing the changes. The other twenty-odd sources the `makefile`
references are NIST's, and are not redistributed here.

You only need any of this if you want to rebuild the nine research generators
used in the archived campaign. Nothing in the main README depends on it.

## Step 0: get the base tree

Download and unpack **NIST STS 2.1.2** from

  https://csrc.nist.gov/projects/random-bit-generation/documentation-and-software

so that you have an `sts-2.1.2/` directory. Everything below happens inside it.

## Step 1: apply the overlay

Copy the files from this directory over the unpacked tree:

```bash
cp makefile             sts-2.1.2/
cp src/generators.c     sts-2.1.2/src/
cp src/utilities.c      sts-2.1.2/src/
cp include/generators.h sts-2.1.2/include/
mkdir -p sts-2.1.2/obj          # the makefile writes objects here and does not create it
```

`NIST_STS_Modifications_Guide.md` documents what was changed in each file and
why, including the bit-packing routine and the early return that skips the
statistical tests.

## Step 2: point it at OpenSSL

The committed `makefile` hardcodes

```
OPENSSL_PREFIX = /opt/homebrew/opt/openssl@3
```

which is Homebrew on Apple Silicon. Change it for your machine: `/usr/local/opt/openssl@3`
on Intel Homebrew, and typically `/usr` or `/usr/local` on Linux.

## Step 3: build

```bash
cd sts-2.1.2 && make
```

This produces `assess`. `generate_nist_inputs.py` in this directory drives it to
produce the generator files; `../input-manifest.csv` records the SHA-256 of each
one.

## What this cannot reproduce

Two of the original campaign inputs — the 40 GB etalon and the pre-fix SHA-1
generator — cannot be recreated from anything published, so the campaign's exact
p-values are not reproducible even with a correct build here. See
`../../docs/validation.md`.
