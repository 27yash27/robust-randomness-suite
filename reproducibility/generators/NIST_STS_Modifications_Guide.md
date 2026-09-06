# NIST STS 2.1.2 — Modification Guide

**Purpose:** Generate large binary files (100MB / 1GB) of packed random data from
the 9 built-in NIST STS pseudo-random number generators, suitable for
downstream randomness testing.

**Base software:** NIST Statistical Test Suite (STS) version 2.1.2
(https://csrc.nist.gov/projects/random-bit-generation/documentation-and-software)

**Prerequisites:**
- macOS or Linux with GCC
- OpenSSL 3.x development libraries (`brew install openssl` on macOS)
- Python 3.x (for the automation scripts)

---

## Bit order, and why it does not invalidate the tests

The packing routine added to `src/utilities.c` writes eight bits per output
byte with the **first bit in the most significant position**:

```c
packed_byte = (packed_byte << 1) | (epsilon[i] & 0x01);
```

A partial final byte is left-shifted, so its padding sits in the low bits.
There is no 32-bit word step in this routine.

`rtest` reads the other way. `g_int32_lsb()` in `robust/generators.c` assembles
four bytes into a word with the first byte in the low eight bits, and the tests
then take bits from that word starting at the least significant. **So within
each byte, the suite consumes the bits in the reverse of the order NIST emitted
them.**

That is not a defect. Bit reversal within a byte is a fixed permutation applied
identically to both compared samples, so the two-sample construction is
unaffected and the p-values remain valid. It does mean the campaign tested a
bit-reversed view of each generator, so its numbers are not directly comparable
to published NIST STS results for the same generators. Anyone comparing against
published STS output should account for this.

## Overview of Changes

Three C source files and one Makefile are modified from the original NIST STS
distribution. Two Python automation scripts are added. No other NIST STS files
are changed.

| File | What changed |
|------|-------------|
| `makefile` | Added OpenSSL include/link flags |
| `src/utilities.c` | Added bit-packing routine in `nist_test_suite()` + early return to skip statistical tests |
| `src/generators.c` | Replaced custom big-integer math with OpenSSL in 3 crypto generators; fixed integer overflow in XOR |
| `generate_nist_inputs.py` | New: automation script for batch generation. The script that actually produced the campaign inputs, `nist_test_generator_both.py`, is archived under `../campaign-2026-05-02/original-tooling/` and should not be run: it hardcodes a personal path and kills processes by name. |

---

## Step-by-Step Modifications

### 1. makefile

**Goal:** Link the OpenSSL cryptography library so the crypto generators
(Modular Exponentiation, Blum-Blum-Shub, Micali-Schnorr) can use
hardware-accelerated big-integer math.

**Find** (near the top of the file):

```makefile
CC = /usr/bin/gcc
GCCFLAGS = -c -Wall
```

**Replace with:**

```makefile
CC = /usr/bin/gcc
OPENSSL_PREFIX = /opt/homebrew/opt/openssl@3
GCCFLAGS = -c -Wall -I$(OPENSSL_PREFIX)/include
LDFLAGS = -L$(OPENSSL_PREFIX)/lib -lcrypto
```

> **Note:** On Linux, `OPENSSL_PREFIX` is typically `/usr` or `/usr/local`.
> Adjust the path to wherever `openssl/bn.h` lives on your system.

**Find** the link rule:

```makefile
assess: $(OBJ)
	$(CC) -o $@ $(OBJ) -lm
```

**Replace with:**

```makefile
assess: $(OBJ)
	$(CC) -o $@ $(OBJ) -lm $(LDFLAGS)
```

**Find** the `assess.o` compile rule:

```makefile
$(OBJDIR)/assess.o: $(SRCDIR)/assess.c defs.h decls.h utilities.h
	$(CC) -o $@ -c $(SRCDIR)/assess.c
```

**Replace with:**

```makefile
$(OBJDIR)/assess.o: $(SRCDIR)/assess.c defs.h decls.h utilities.h
	$(CC) -o $@ $(GCCFLAGS) $(SRCDIR)/assess.c
```

---

### 2. src/utilities.c — Bit-Packing and Test Bypass

**Goal:** When `nist_test_suite()` is called by a generator, pack the bits in
the `epsilon[]` array into a binary file (8 bits per byte) and skip all
15 statistical tests. This makes generation ~100x faster because the
tests (FFT, Rank, etc.) are computationally expensive and unnecessary
when we only want the raw generated data.

**Find** the `nist_test_suite()` function (around line 464). The original looks
like:

```c
void
nist_test_suite()
{
	if ( (testVector[0] == 1) || (testVector[TEST_FREQUENCY] == 1) )
		Frequency(tp.n);
	...
```

**Replace the entire function body** (keep the function signature) with:

```c
void
nist_test_suite()
{
    // --- START OF CUSTOM BIT-PACKING & STREAMING ROUTINE ---
    // This appends the current epsilon array chunk to the binary file
    FILE *fp = fopen("bad_generator_output.bin", "ab"); // "ab" is append mode

    if (fp != NULL) {
        unsigned char packed_byte = 0;
        int bit_count = 0;

        // Use tp.n, which is the sequence length parameter in the NIST suite
        for (int i = 0; i < tp.n; i++) {
            packed_byte = (packed_byte << 1) | (epsilon[i] & 0x01);
            bit_count++;

            if (bit_count == 8) {
                fwrite(&packed_byte, 1, 1, fp);
                packed_byte = 0;
                bit_count = 0;
            }
        }

        // Pad the remaining bits if the sequence length isn't perfectly divisible by 8
        if (bit_count > 0) {
            packed_byte = packed_byte << (8 - bit_count);
            fwrite(&packed_byte, 1, 1, fp);
        }
        fclose(fp);
    } else {
        printf("Error: Could not open file for appending.\n");
    }

    // Skip all statistical tests — we only need the generated data, not test results.
    // This makes generation ~100x faster since tests (FFT, Rank, etc.) are expensive.
    return;
    // --- END OF CUSTOM ROUTINE ---

    // Original NIST test calls below are kept for reference but never reached.

	if ( (testVector[0] == 1) || (testVector[TEST_FREQUENCY] == 1) )
		Frequency(tp.n);

	if ( (testVector[0] == 1) || (testVector[TEST_BLOCK_FREQUENCY] == 1) )
		BlockFrequency(tp.blockFrequencyBlockLength, tp.n);

	if ( (testVector[0] == 1) || (testVector[TEST_CUSUM] == 1) )
		CumulativeSums(tp.n);

	if ( (testVector[0] == 1) || (testVector[TEST_RUNS] == 1) )
		Runs(tp.n);

	if ( (testVector[0] == 1) || (testVector[TEST_LONGEST_RUN] == 1) )
		LongestRunOfOnes(tp.n);

	if ( (testVector[0] == 1) || (testVector[TEST_RANK] == 1) )
		Rank(tp.n);

	if ( (testVector[0] == 1) || (testVector[TEST_FFT] == 1) )
		DiscreteFourierTransform(tp.n);

	if ( (testVector[0] == 1) || (testVector[TEST_NONPERIODIC] == 1) )
		NonOverlappingTemplateMatchings(tp.nonOverlappingTemplateBlockLength, tp.n);

	if ( (testVector[0] == 1) || (testVector[TEST_OVERLAPPING] == 1) )
		OverlappingTemplateMatchings(tp.overlappingTemplateBlockLength, tp.n);

	if ( (testVector[0] == 1) || (testVector[TEST_UNIVERSAL] == 1) )
		Universal(tp.n);

	if ( (testVector[0] == 1) || (testVector[TEST_APEN] == 1) )
		ApproximateEntropy(tp.approximateEntropyBlockLength, tp.n);

	if ( (testVector[0] == 1) || (testVector[TEST_RND_EXCURSION] == 1) )
		RandomExcursions(tp.n);

	if ( (testVector[0] == 1) || (testVector[TEST_RND_EXCURSION_VAR] == 1) )
		RandomExcursionsVariant(tp.n);

	if ( (testVector[0] == 1) || (testVector[TEST_SERIAL] == 1) )
		Serial(tp.serialBlockLength,tp.n);

	if ( (testVector[0] == 1) || (testVector[TEST_LINEARCOMPLEXITY] == 1) )
		LinearComplexity(tp.linearComplexitySequenceLength, tp.n);
}
```

**How it works:** Each time a generator fills the `epsilon[]` array with
`tp.n` bits and calls `nist_test_suite()`, this routine packs every
8 bits into one byte and appends it to `bad_generator_output.bin`.
The file is opened in append mode (`"ab"`) so multiple calls
accumulate data. The `return` statement skips all test execution.

---

### 3. src/generators.c — OpenSSL Integration and Overflow Fix

**Goal:** Replace the naive byte-by-byte big-integer routines (`ModExp`,
`ModSqr`, `ModMult`) with OpenSSL's optimized `BN_mod_exp()` and
`BN_mod_sqr()`. This gives a 50–200x speedup for the three
cryptographic generators. Also fix an integer overflow in the XOR
generator that prevents 1GB file generation.

#### 3a. Add OpenSSL header

**Find** (at the top of the file):

```c
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <time.h>
#include "../include/externs.h"
```

**Add** after `<time.h>`:

```c
#include <openssl/bn.h>
```

#### 3b. Fix XOR generator integer overflow

**Find** in the `exclusiveOR()` function:

```c
	int		i, num_0s, num_1s, bitsRead;
```

**Replace with:**

```c
	long	i;
	int		num_0s, num_1s, bitsRead;
```

**Find** (in the same function):

```c
	for ( i=127; i<tp.n*tp.numOfBitStreams; i++ ) {
```

**Replace with:**

```c
	for ( i=127; i<(long)tp.n*tp.numOfBitStreams; i++ ) {
```

**Why:** `tp.n * tp.numOfBitStreams` can exceed 2^31 for 1GB files
(1,000,000 x 8,000 = 8,000,000,000), overflowing a 32-bit `int`.

#### 3c. Replace modExp() function

**Find** the entire `modExp()` function and **replace** with:

```c
void
modExp()
{
	int		k, num_0s, num_1s, bitsRead, done;
	BYTE	p_bytes[64], g_bytes[64], y_bytes[20], x_bytes[64];

	if ( (epsilon = (BitSequence *)calloc(tp.n, sizeof(BitSequence))) == NULL ) {
		printf("Insufficient memory available.\n");
		exit(1);
	}
	ahtopb("7AB36982CE1ADF832019CDFEB2393CABDF0214EC", y_bytes, 20);
	ahtopb("987b6a6bf2c56a97291c445409920032499f9ee7ad128301b5d0254aa1a9633fdbd378d40149f1e23a13849f3d45992f5c4c6b7104099bc301f6005f9d8115e1", p_bytes, 64);
	ahtopb("3844506a9456c564b8b8538e0cc15aff46c95e69600f084f0657c2401b3c244734b62ea9bb95be4923b9b7e84eeaf1a224894ef0328d44bc3eb3e983644da3f5", g_bytes, 64);

	/* OpenSSL setup */
	BN_CTX *ctx = BN_CTX_new();
	BIGNUM *bn_g = BN_bin2bn(g_bytes, 64, NULL);
	BIGNUM *bn_p = BN_bin2bn(p_bytes, 64, NULL);
	BIGNUM *bn_y = BN_bin2bn(y_bytes, 20, NULL);
	BIGNUM *bn_x = BN_new();

	for ( k=0; k<tp.numOfBitStreams; k++ ) {
		num_0s = 0;
		num_1s = 0;
		bitsRead = 0;
		done = 0;
		do {
			BN_mod_exp(bn_x, bn_g, bn_y, bn_p, ctx);
			/* Convert result to 64-byte big-endian array */
			memset(x_bytes, 0x00, 64);
			BN_bn2binpad(bn_x, x_bytes, 64);
			done = convertToBits(x_bytes, 512, tp.n, &num_0s, &num_1s, &bitsRead);
			/* Next exponent = last 20 bytes of result */
			BN_bin2bn(x_bytes + 44, 20, bn_y);
		} while ( !done );
		fprintf(freqfp, "\t\tBITSREAD = %d 0s = %d 1s = %d\n", bitsRead, num_0s, num_1s); fflush(freqfp);
		nist_test_suite();
	}

	BN_free(bn_g);
	BN_free(bn_p);
	BN_free(bn_y);
	BN_free(bn_x);
	BN_CTX_free(ctx);
	free(epsilon);

	return;
}
```

#### 3d. Replace bbs() function

**Find** the entire `bbs()` function and **replace** with:

```c
void
bbs()
{
	int		i, v, bitsRead;
	BYTE	p_bytes[64], q_bytes[64], s_bytes[64];
	int		num_0s, num_1s;

	if ( (epsilon = (BitSequence*)calloc(tp.n, sizeof(BitSequence))) == NULL ) {
		printf("Insufficient memory available.\n");
		exit(1);
	}
	ahtopb("E65097BAEC92E70478CAF4ED0ED94E1C94B154466BFB9EC9BE37B2B0FF8526C222B76E0E915017535AE8B9207250257D0A0C87C0DACEF78E17D1EF9DC44FD91F", p_bytes, 64);
	ahtopb("E029AEFCF8EA2C29D99CB53DD5FA9BC1D0176F5DF8D9110FD16EE21F32E37BA86FF42F00531AD5B8A43073182CC2E15F5C86E8DA059E346777C9A985F7D8A867", q_bytes, 64);
	ahtopb("10d6333cfac8e30e808d2192f7c0439480da79db9bbca1667d73be9a677ed31311f3b830937763837cb7b1b1dc75f14eea417f84d9625628750de99e7ef1e976", s_bytes, 64);

	/* OpenSSL setup */
	BN_CTX *ctx = BN_CTX_new();
	BIGNUM *bn_p = BN_bin2bn(p_bytes, 64, NULL);
	BIGNUM *bn_q = BN_bin2bn(q_bytes, 64, NULL);
	BIGNUM *bn_n = BN_new();
	BIGNUM *bn_x = BN_new();
	BIGNUM *bn_s = BN_bin2bn(s_bytes, 64, NULL);

	/* n = p * q */
	BN_mul(bn_n, bn_p, bn_q, ctx);
	/* x = s^2 mod n (initial squaring) */
	BN_mod_sqr(bn_x, bn_s, bn_n, ctx);

	for ( v=0; v<tp.numOfBitStreams; v++ ) {
		num_0s = 0;
		num_1s = 0;
		bitsRead = 0;
		for ( i=0; i<tp.n; i++ ) {
			BN_mod_sqr(bn_x, bn_x, bn_n, ctx);
			/* Extract LSB */
			if ( BN_is_bit_set(bn_x, 0) == 0 ) {
				num_0s++;
				epsilon[i] = 0;
			}
			else {
				num_1s++;
				epsilon[i] = 1;
			}
			bitsRead++;
		}

		fprintf(freqfp, "\t\tBITSREAD = %d 0s = %d 1s = %d\n", bitsRead, num_0s, num_1s); fflush(freqfp);
		nist_test_suite();
	}

	BN_free(bn_p);
	BN_free(bn_q);
	BN_free(bn_n);
	BN_free(bn_x);
	BN_free(bn_s);
	BN_CTX_free(ctx);
	free(epsilon);
}
```

#### 3e. Replace micali_schnorr() function

**Find** the entire `micali_schnorr()` function and **replace** with:

```c
// The exponent, e, is set to 11
// This results in k = 837 and r = 187
void
micali_schnorr()
{
	long	i, j;
	int		k=837, num_0s, num_1s, bitsRead, done;
	BYTE	p_bytes[64], q_bytes[64], X_bytes[128], Y_bytes[128], Tail[105];

	if ( (epsilon = (BitSequence *)calloc(tp.n, sizeof(BitSequence))) == NULL ) {
		printf("Insufficient memory available.\n");
		exit(1);
	}
	ahtopb("E65097BAEC92E70478CAF4ED0ED94E1C94B154466BFB9EC9BE37B2B0FF8526C222B76E0E915017535AE8B9207250257D0A0C87C0DACEF78E17D1EF9DC44FD91F", p_bytes, 64);
	ahtopb("E029AEFCF8EA2C29D99CB53DD5FA9BC1D0176F5DF8D9110FD16EE21F32E37BA86FF42F00531AD5B8A43073182CC2E15F5C86E8DA059E346777C9A985F7D8A867", q_bytes, 64);

	/* OpenSSL setup */
	BN_CTX *ctx = BN_CTX_new();
	BIGNUM *bn_p = BN_bin2bn(p_bytes, 64, NULL);
	BIGNUM *bn_q = BN_bin2bn(q_bytes, 64, NULL);
	BIGNUM *bn_n = BN_new();
	BIGNUM *bn_e = BN_new();
	BIGNUM *bn_X = BN_new();
	BIGNUM *bn_Y = BN_new();

	BN_mul(bn_n, bn_p, bn_q, ctx);
	BN_set_word(bn_e, 0x0b);  /* e = 11 */

	memset(X_bytes, 0x00, 128);
	ahtopb("237c5f791c2cfe47bfb16d2d54a0d60665b20904ec822a6", X_bytes+104, 24);
	BN_bin2bn(X_bytes, 128, bn_X);

	for ( i=0; i<tp.numOfBitStreams; i++ ) {
		num_0s = 0;
		num_1s = 0;
		bitsRead = 0;
		do {
			BN_mod_exp(bn_Y, bn_X, bn_e, bn_n, ctx);
			memset(Y_bytes, 0x00, 128);
			BN_bn2binpad(bn_Y, Y_bytes, 128);
			/* Extract Tail = Y[23..127] shifted left 3 bits */
			memcpy(Tail, Y_bytes+23, 105);
			for ( j=0; j<3; j++ )
				bshl(Tail, 105);
			done = convertToBits(Tail, k, tp.n, &num_0s, &num_1s, &bitsRead);
			/* Next X = top 24 bytes of Y, shifted right 5 bits */
			memset(X_bytes, 0x00, 128);
			memcpy(X_bytes+104, Y_bytes, 24);
			for ( j=0; j<5; j++ )
				bshr(X_bytes+104, 24);
			BN_bin2bn(X_bytes, 128, bn_X);
		} while ( !done );

		fprintf(freqfp, "\t\tBITSREAD = %d 0s = %d 1s = %d\n", bitsRead, num_0s, num_1s); fflush(freqfp);
		nist_test_suite();
	}

	BN_free(bn_p);
	BN_free(bn_q);
	BN_free(bn_n);
	BN_free(bn_e);
	BN_free(bn_X);
	BN_free(bn_Y);
	BN_CTX_free(ctx);
	free(epsilon);
}
```

---

## Building

After making all changes:

```bash
# Install OpenSSL (macOS)
brew install openssl

# Build
cd sts-2.1.2
make clean
make
```

The `assess` binary should compile with no errors (only pre-existing warnings).

---

## Running

### Quick manual test (single generator, 100K bits)

```bash
printf '1\n1\n0\n1\n' | ./assess 100000
ls -l bad_generator_output.bin   # should be 12,500 bytes
```

### Using the automation script

```bash
python3 generate_nist_inputs.py --sts . --out ./inputs --size-mb 1000

# it copies this tree per generator, so the tree you point at is not modified
```

Choose `1` for 100MB or `2` for 1GB. The script:
1. Kills any stale `assess` processes
2. Creates a timestamped output folder
3. Runs each generator via a single `./assess` call with N bit-streams
4. Shows real-time progress with ETA
5. Verifies each output file (hexdump + size check)

### Expected generation times (100MB, Apple M-series Mac)

| Generator | Time |
|-----------|------|
| Linear Congruential | ~27s |
| Quadratic Congruential I | ~104s |
| Quadratic Congruential II | ~20s |
| Cubic Congruential | ~42s |
| XOR | ~10s |
| Modular Exponentiation | ~20s |
| Blum-Blum-Shub | ~73 min |
| Micali-Schnorr | ~96s |
| G Using SHA-1 | ~9s |

### Expected output

Each file is exactly `100,000,000` bytes (100MB) or `1,000,000,000` bytes (1GB)
of packed binary data. The hexdump verification confirms proper bit-packing
(many distinct byte values, not just 0x00/0x01).

---

## Summary of Why Each Change Was Needed

1. **Bit-packing in `nist_test_suite()`** — The original NIST code stores bits
   in memory as individual bytes (0x00 or 0x01). We pack 8 bits per byte and
   write to a binary file for efficient storage.

2. **Early `return` to skip tests** — Running all 15 statistical tests on
   every chunk adds ~30 minutes per generator. Since we only want the
   generated data, skipping tests makes generation ~100x faster.

3. **OpenSSL for crypto generators** — The original NIST code uses naive
   byte-by-byte big-integer arithmetic. OpenSSL uses 64-bit machine words,
   Montgomery multiplication, and hardware acceleration. This gives a
   50–200x speedup for Modular Exponentiation, Blum-Blum-Shub, and
   Micali-Schnorr (e.g., ModExp 100MB: 27 hours -> 20 seconds).

4. **XOR integer overflow fix** — The loop counter `i` was a 32-bit `int`.
   For 1GB files, `tp.n * tp.numOfBitStreams = 8,000,000,000` overflows.
   Changed to `long` with explicit cast.
