/*
 * Boundary regression for test 36 (non-overlapping template matching).
 *
 * A template occurrence must be counted wherever it sits in a block. This
 * builds a block containing exactly one copy of template 0 (000000001) at a
 * chosen offset, runs the real nonperiodic() statistic, and checks that the
 * reported value for that template does not depend on the offset.
 *
 * The original implementation only began counting "fresh bits" after the
 * 9-bit window had filled, which left the first 8 candidate positions of
 * every block ineligible: offsets 0-7 scored 0 matches while offset 8 scored
 * 1. Note that this could not be caught through the suite's p-values, because
 * the same code produces both compared samples and the error cancels; it has
 * to be checked against the statistic directly.
 *
 * Build and run:  make test-nonperiodic-boundary
 */

#include "test_func.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define DIM 148
#define N_INTS 8              /* 32*8 = 256 bits, 8 blocks of M = 32 bits */
#define BLOCKS 8
#define M_BITS 32
#define TEMPLATE_LEN 9

extern test_func nonperiodic;

/* Write BLOCKS blocks of M_BITS bits; each block is all ones except for one
 * copy of 000000001 starting at `offset`. Bits are emitted LSB-first per
 * 32-bit word, matching g_int32_lsb(). */
#define PAD 8   /* write more blocks than the statistic reads, so the
                 * generator never hits end of file mid-call */
static int write_case(const char *path, int offset) {
  unsigned char buf[PAD * BLOCKS * M_BITS / 8];
  memset(buf, 0, sizeof buf);
  for (int b = 0; b < PAD * BLOCKS; b++) {
    for (int i = 0; i < M_BITS; i++) {
      int bit = 1;
      if (i >= offset && i < offset + TEMPLATE_LEN) {
        bit = (i == offset + TEMPLATE_LEN - 1) ? 1 : 0;
      }
      if (bit) {
        long idx = (long)b * M_BITS + i;
        buf[idx / 8] |= (unsigned char)(1U << (idx % 8));
      }
    }
  }
  FILE *f = fopen(path, "wb");
  if (!f) return 0;
  size_t n = fwrite(buf, 1, sizeof buf, f);
  fclose(f);
  return n == sizeof buf;
}

int main(void) {
  const char *path = "tmp_nonperiodic_boundary.bin";
  int param[10] = {0};
  double real_param[10] = {0};
  param[2] = DIM;
  param[3] = N_INTS;

  long double baseline = 0.0L;
  int have_baseline = 0, failures = 0, checked = 0;

  printf("test 36 boundary: one template per block, varying its offset\n");
  for (int offset = 0; offset <= M_BITS - TEMPLATE_LEN; offset++) {
    if (!write_case(path, offset)) {
      printf("  could not write %s\n", path);
      return 2;
    }
    PRG gen;
    if (!g_create_file(&gen, (char *)path)) {
      printf("  could not open %s as a generator\n", path);
      return 2;
    }
    long double value[DIM];
    unsigned long hash = 0;
    if (!nonperiodic(value, &hash, gen, param, real_param, false)) {
      printf("  offset %2d: statistic returned false\n", offset);
      failures++;
      continue;
    }
    checked++;
    if (!have_baseline) {
      baseline = value[0];
      have_baseline = 1;
    } else if (value[0] != baseline) {
      printf("  offset %2d: value %.18Lf differs from offset 0 (%.18Lf)\n",
             offset, value[0], baseline);
      failures++;
    }
  }
  remove(path);

  printf("  checked %d offsets\n", checked);
  if (failures) {
    printf("FAIL: the count depends on where the template sits in the block.\n");
    return 1;
  }
  printf("ok: every offset gives the same count.\n");
  return 0;
}
