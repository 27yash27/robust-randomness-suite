#include "test_func.h"
#include <gsl/gsl_sf.h>
#include <math.h>

/*
 * NIST 800-22 Approximate Entropy Test (test #40 in this harness).
 *
 * For block length m and bit-stream length n = 32*param[3], compute
 *
 *     phi(m)   = (1/n) * sum_i C^m_i * log(C^m_i)
 *     phi(m+1) = (1/n) * sum_i C^(m+1)_i * log(C^(m+1)_i)
 *     ApEn     = phi(m) - phi(m+1)
 *     chi^2    = 2 * n * (log(2) - ApEn)
 *
 * where C^m_i is the empirical frequency of the i-th m-bit pattern in the
 * cyclically extended bitstream. The test reports the upper-tail chi-square
 * p-value with 2^(m-1) degrees of freedom (NIST SP 800-22 Sec. 2.12).
 *
 * Streaming implementation: rolling pattern accumulators advance bit-by-bit;
 * the only persistent storage is two histograms of sizes 2^m and 2^(m+1)
 * plus a buffer of the first m+1 bits for cyclic wrap-around. Memory is
 * independent of the input length, so the test scales to multi-GB sweeps
 * (for m = 10 the histograms together take ~24 KB regardless of n).
 *
 * Block length defaults to m = 10 (good for n in [10000, 10^6]) and may be
 * overridden via param[4]. NIST recommends m <= floor(log2(n)) - 5.
 */

#define APEN_DIMENSION 1
#define APEN_DEFAULT_M 10

bool approximate_entropy(long double *value, unsigned long *hash, PRG gen,
                         int *param, double *real_param, bool debug) {
  (void)real_param;
  assert(param[2] == APEN_DIMENSION);
  long n_ints = param[3];
  assert(n_ints >= 1);
  long n = 32L * n_ints;

  int m = (param[4] > 0) ? param[4] : APEN_DEFAULT_M;
  if (m < 2 || m > 16) {
    return false;
  }
  if (n < (long)(m + 2)) {
    return false; /* not enough bits to even seed the rolling patterns */
  }
  if ((double)m > log2((double)n) - 5.0 && debug) {
    printf("ApEn: m=%d may be too large for n=%ld bits\n", m, n);
  }

  long pow2m = 1L << m;
  long pow2m1 = 1L << (m + 1);
  unsigned long mask_m = (unsigned long)(pow2m - 1L);
  unsigned long mask_m1 = (unsigned long)(pow2m1 - 1L);

  long *cnt_m = (long *)calloc((size_t)pow2m, sizeof(long));
  long *cnt_m1 = (long *)calloc((size_t)pow2m1, sizeof(long));
  unsigned char *saved =
      (unsigned char *)malloc((size_t)(m + 1) * sizeof(unsigned char));
  if (cnt_m == NULL || cnt_m1 == NULL || saved == NULL) {
    free(cnt_m);
    free(cnt_m1);
    free(saved);
    return false;
  }

  /* 32-bit fetch buffer drives the bit stream. */
  unsigned int bit_buf = 0;
  int bit_buf_pos = 32;
  long bits_read = 0;

#define APEN_FETCH_BIT(out_var)                                                \
  do {                                                                         \
    if (bit_buf_pos == 32) {                                                   \
      if (!g_int32_lsb(&bit_buf, gen)) {                                       \
        free(cnt_m);                                                           \
        free(cnt_m1);                                                          \
        free(saved);                                                           \
        return false;                                                          \
      }                                                                        \
      bit_buf_pos = 0;                                                         \
    }                                                                          \
    (out_var) = (unsigned char)((bit_buf >> bit_buf_pos) & 1U);                \
    bit_buf_pos++;                                                             \
    bits_read++;                                                               \
  } while (0)

  /* Seed: read first m+1 bits, save them for cyclic wrap, build initial
   * patterns at position i = 0:
   *   pat_m  = bits[0..m-1]
   *   pat_m1 = bits[0..m]    (one bit ahead of pat_m) */
  unsigned long pat_m = 0UL;
  unsigned long pat_m1 = 0UL;
  for (int j = 0; j < m + 1; j++) {
    unsigned char b;
    APEN_FETCH_BIT(b);
    saved[j] = b;
    if (j < m) {
      pat_m = ((pat_m << 1) | (unsigned long)b) & mask_m;
    }
    pat_m1 = ((pat_m1 << 1) | (unsigned long)b) & mask_m1;
  }

  /* Main loop: count both patterns at every cyclic position 0..n-1. After
   * counting at position i, advance both to position i+1:
   *   pat_m gains the bit currently at the LSB of pat_m1 (= bits[i+m]).
   *   pat_m1 gains a fresh bit (bits[i+m+1] = bits[bits_read]).
   * For i in the last m positions, that fresh bit comes from saved[]. */
  for (long i = 0; i < n; i++) {
    cnt_m[pat_m]++;
    cnt_m1[pat_m1]++;
    if (i == n - 1) {
      break;
    }
    unsigned long bit_for_m = pat_m1 & 1UL; /* = bits[i+m] */
    pat_m = ((pat_m << 1) | bit_for_m) & mask_m;

    unsigned char bit_for_m1;
    if (bits_read < n) {
      APEN_FETCH_BIT(bit_for_m1);
    } else {
      /* Cyclic wrap: bit_for_m1 = saved[(bits_read) - n] */
      bit_for_m1 = saved[bits_read - n];
      bits_read++;
    }
    pat_m1 = ((pat_m1 << 1) | (unsigned long)bit_for_m1) & mask_m1;
  }

#undef APEN_FETCH_BIT

  /* Drain any remaining bits in bit_buf for stream alignment, plus any
   * unread param[3] words (none expected in practice — bits_read should be
   * exactly n by here). */
  long words_used = (n + 31) / 32;
  for (long i = words_used; i < n_ints; i++) {
    unsigned int discard;
    if (!g_int32_lsb(&discard, gen)) {
      free(cnt_m);
      free(cnt_m1);
      free(saved);
      return false;
    }
  }

  /* phi(m) = (1/n) * sum_i count_m[i] * log(count_m[i] / n) */
  double inv_n = 1.0 / (double)n;
  double sum_m = 0.0;
  for (long i = 0; i < pow2m; i++) {
    if (cnt_m[i] > 0) {
      sum_m += (double)cnt_m[i] * log((double)cnt_m[i] * inv_n);
    }
  }
  double phi_m = sum_m * inv_n;

  double sum_m1 = 0.0;
  for (long i = 0; i < pow2m1; i++) {
    if (cnt_m1[i] > 0) {
      sum_m1 += (double)cnt_m1[i] * log((double)cnt_m1[i] * inv_n);
    }
  }
  double phi_m1 = sum_m1 * inv_n;

  free(cnt_m);
  free(cnt_m1);
  free(saved);

  double apen = phi_m - phi_m1;
  double chi2 = 2.0 * (double)n * (log(2.0) - apen);
  double dof = (double)(1L << (m - 1));
  value[0] = (long double)gsl_sf_gamma_inc_Q(dof, chi2 / 2.0);

  if (debug) {
    printf("ApEn m=%d phi(m)=%.6f phi(m+1)=%.6f ApEn=%.6f chi2=%.6f p=%.6Lf\n",
           m, phi_m, phi_m1, apen, chi2, value[0]);
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
