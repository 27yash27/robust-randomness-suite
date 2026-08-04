#include "test_func.h"
#include <gsl/gsl_cdf.h>
#include <math.h>

/*
 * NIST 800-22 Cumulative Sums (Cusum) Test (test #39 in this harness).
 *
 * Builds the +/-1 random-walk partial sums S_k from the n = 32*param[3] bit
 * stream and tracks three running quantities in a single forward pass:
 *
 *     sup     = max_k S_k
 *     inf     = min_k S_k
 *     S_final = S_n
 *
 * From these three numbers both the forward and reverse maximum-excursion
 * statistics are determined:
 *
 *     z_fwd = max(sup, -inf)
 *     z_rev = max(sup - S_final, S_final - inf)
 *
 * Each is converted to a p-value via the closed-form NIST series
 *
 *     p = 1 - sum_{k=k_lo..k_hi} [Phi((4k+1)z/sqrt(n)) - Phi((4k-1)z/sqrt(n))]
 *           + sum_{k=k_lo'..k_hi'} [Phi((4k+3)z/sqrt(n)) - Phi((4k+1)z/sqrt(n))]
 *
 * with Phi the standard normal CDF (NIST SP 800-22 Sec. 2.13).
 *
 * Returns dimension = 2: value[0] = forward p-value, value[1] = reverse.
 *
 * Streaming implementation: O(1) memory regardless of input length.
 */

#define CUSUM_DIMENSION 2

static double cusum_pvalue(long n, long z) {
  if (z <= 0) {
    return 1.0;
  }
  double sqrt_n = sqrt((double)n);
  double sum1 = 0.0;
  double sum2 = 0.0;
  long k_lo, k_hi;

  k_lo = (-(long)n / z + 1) / 4;
  k_hi = ((long)n / z - 1) / 4;
  for (long k = k_lo; k <= k_hi; k++) {
    sum1 += gsl_cdf_ugaussian_P(((4.0 * (double)k + 1.0) * (double)z) / sqrt_n);
    sum1 -= gsl_cdf_ugaussian_P(((4.0 * (double)k - 1.0) * (double)z) / sqrt_n);
  }

  k_lo = (-(long)n / z - 3) / 4;
  k_hi = ((long)n / z - 1) / 4;
  for (long k = k_lo; k <= k_hi; k++) {
    sum2 += gsl_cdf_ugaussian_P(((4.0 * (double)k + 3.0) * (double)z) / sqrt_n);
    sum2 -= gsl_cdf_ugaussian_P(((4.0 * (double)k + 1.0) * (double)z) / sqrt_n);
  }

  double p = 1.0 - sum1 + sum2;
  if (p < 0.0) {
    p = 0.0;
  } else if (p > 1.0) {
    p = 1.0;
  }
  return p;
}

bool cusum(long double *value, unsigned long *hash, PRG gen, int *param,
           double *real_param, bool debug) {
  (void)real_param;
  assert(param[2] == CUSUM_DIMENSION);
  long n_ints = param[3];
  assert(n_ints >= 1);
  long n = 32L * n_ints;

  long S = 0;
  long sup = 0;
  long inf = 0;

  for (long i = 0; i < n_ints; i++) {
    unsigned int w;
    if (!g_int32_lsb(&w, gen)) {
      return false;
    }
    for (int b = 0; b < 32; b++) {
      int bit = (int)((w >> b) & 1U);
      S += (bit == 1) ? 1 : -1;
      if (S > sup) {
        sup = S;
      } else if (S < inf) {
        inf = S;
      }
    }
  }
  long S_final = S;
  long z_fwd = (sup > -inf) ? sup : -inf;
  long z_rev = (sup - S_final > S_final - inf) ? (sup - S_final)
                                               : (S_final - inf);

  value[0] = (long double)cusum_pvalue(n, z_fwd);
  value[1] = (long double)cusum_pvalue(n, z_rev);

  if (debug) {
    printf("Cusum n=%ld z_fwd=%ld z_rev=%ld p_fwd=%.6Lf p_rev=%.6Lf\n", n,
           z_fwd, z_rev, value[0], value[1]);
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
