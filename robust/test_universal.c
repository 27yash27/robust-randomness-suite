#include "test_func.h"
#include <math.h>

/*
 * Maurer's Universal Statistical Test (NIST 800-22, test #41 in this harness).
 *
 * Compresses the n = 32*param[3] bit stream conceptually by tracking the
 * distance (in L-bit blocks) between successive occurrences of every
 * possible L-bit pattern. Truly random data produces an average log-distance
 * close to a tabulated expected value; subtle compressibility lowers it.
 *
 * Block length L is selected from the NIST schedule based on n; given L,
 * the test uses Q = 10*2^L "initialization" blocks to seed the last-seen
 * table T[v] and K = floor(n/L) - Q "scoring" blocks. The final statistic
 *
 *     phi  = (1/K) * sum_{i=Q+1..Q+K} log2(i - T[v_i])
 *     z    = (phi - exp_value[L]) / (c * sqrt(variance[L] / K))
 *     p    = erfc(|z| / sqrt(2))
 *
 * with c the small-sample correction factor from Marsaglia's paper.
 * Requires n >= 387840 bits (12120 32-bit ints) for the smallest valid
 * L = 6; smaller inputs return false.
 *
 * Constants (expected_value[L], variance[L]) are taken verbatim from
 * NIST SP 800-22 Sec. 2.9.
 *
 * Streaming implementation: bits are pulled from the generator one 32-bit
 * word at a time and L-bit blocks are extracted from a 64-bit shift-buffer.
 * Persistent storage is just the last-seen table T[] (8*2^L bytes), so memory
 * stays under 512 KB even for the largest L=16 schedule.
 */

#define UNIVERSAL_DIMENSION 1

static const double universal_expected_value[17] = {
    0.0,         0.0,        0.0,        0.0,        0.0,
    0.0,         5.2177052,  6.1962507,  7.1836656,  8.1764248,
    9.1723243,  10.170032,  11.168765,  12.168070,  13.167693,
    14.167488, 15.167379};

static const double universal_variance[17] = {
    0.0,   0.0,   0.0,   0.0,   0.0,   0.0,   2.954, 3.125,
    3.238, 3.311, 3.356, 3.384, 3.401, 3.410, 3.416, 3.419, 3.421};

static int universal_choose_L(long n) {
  int L = 5;
  if (n >= 387840L)     L = 6;
  if (n >= 904960L)     L = 7;
  if (n >= 2068480L)    L = 8;
  if (n >= 4654080L)    L = 9;
  if (n >= 10342400L)   L = 10;
  if (n >= 22753280L)   L = 11;
  if (n >= 49643520L)   L = 12;
  if (n >= 107560960L)  L = 13;
  if (n >= 231669760L)  L = 14;
  if (n >= 496435200L)  L = 15;
  if (n >= 1059061760L) L = 16;
  return L;
}

bool universal(long double *value, unsigned long *hash, PRG gen, int *param,
               double *real_param, bool debug) {
  (void)real_param;
  assert(param[2] == UNIVERSAL_DIMENSION);
  long n_ints = param[3];
  assert(n_ints >= 1);
  long n = 32L * n_ints;

  int L = universal_choose_L(n);
  if (L < 6 || L > 16) {
    if (debug) {
      printf("Universal: L=%d outside [6,16]; n=%ld too small\n", L, n);
    }
    return false;
  }

  long pow2L = 1L << L;
  long Q = 10L * pow2L;
  long K = (n / (long)L) - Q;
  if (K < 1) {
    return false;
  }

  long *T = (long *)calloc((size_t)pow2L, sizeof(long));
  if (T == NULL) {
    return false;
  }

  /* 64-bit bit buffer; we always have at least L bits available before
   * extracting (refill from g_int32_lsb in 32-bit chunks). */
  unsigned long long buf = 0ULL;
  int buf_bits = 0;
  long ints_consumed = 0;
  unsigned long mask_L = (unsigned long)(pow2L - 1L);

#define UNIV_NEXT_BLOCK(out_var)                                               \
  do {                                                                         \
    while (buf_bits < L) {                                                     \
      unsigned int w;                                                          \
      if (!g_int32_lsb(&w, gen)) {                                             \
        free(T);                                                               \
        return false;                                                          \
      }                                                                        \
      ints_consumed++;                                                         \
      /* Append w as the LOW 32 bits of buf so older bits exit at the top */   \
      /* (LSB-first within w to match the harness convention). */              \
      buf |= ((unsigned long long)w) << buf_bits;                              \
      buf_bits += 32;                                                          \
    }                                                                          \
    (out_var) = (unsigned long)(buf & (unsigned long long)mask_L);             \
    buf >>= L;                                                                 \
    buf_bits -= L;                                                             \
  } while (0)

  /* Initialization phase: fill T with last position of each L-bit pattern. */
  for (long i = 1; i <= Q; i++) {
    unsigned long block;
    UNIV_NEXT_BLOCK(block);
    T[block] = i;
  }

  /* Scoring phase: accumulate log2(distance) over K blocks. */
  double sum = 0.0;
  for (long i = Q + 1; i <= Q + K; i++) {
    unsigned long block;
    UNIV_NEXT_BLOCK(block);
    long gap = i - T[block];
    sum += log2((double)gap);
    T[block] = i;
  }
  double phi = sum / (double)K;
  free(T);

#undef UNIV_NEXT_BLOCK

  /* Drain remaining param[3] words for harness alignment. */
  for (long i = ints_consumed; i < n_ints; i++) {
    unsigned int discard;
    if (!g_int32_lsb(&discard, gen)) {
      return false;
    }
  }

  /* Marsaglia's small-sample correction (NIST SP 800-22 Sec. 2.9). */
  double c = 0.7 - 0.8 / (double)L +
             (4.0 + 32.0 / (double)L) * pow((double)K, -3.0 / (double)L) / 15.0;
  double sigma = c * sqrt(universal_variance[L] / (double)K);
  double arg = fabs(phi - universal_expected_value[L]) / (sqrt(2.0) * sigma);
  double p_value = erfc(arg);
  if (p_value < 0.0) {
    p_value = 0.0;
  } else if (p_value > 1.0) {
    p_value = 1.0;
  }
  value[0] = (long double)p_value;

  if (debug) {
    printf("Universal L=%d Q=%ld K=%ld phi=%.6f exp=%.6f sigma=%.6g p=%.6Lf\n",
           L, Q, K, phi, universal_expected_value[L], sigma, value[0]);
  }

  unsigned int h1, h2;
  if ((!g_int32_lsb(&h1, gen)) || (!g_int32_lsb(&h2, gen))) {
    return false;
  }
  *hash = (((unsigned long)h2) << 32) + (unsigned long)h1;
  if (debug) {
    print64(*hash);
    printf("\n");
  }
  return true;
}
