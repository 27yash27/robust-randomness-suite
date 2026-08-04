#include "test_func.h"
#include <gsl/gsl_cdf.h>
#include <gsl/gsl_math.h>
#include <math.h>

/*
 * Diehard Squeeze Test
 *
 * 1. Start with k = 2^31.
 * 2. Repeatedly let k = ceil(k * U), where U is a uniform random number.
 * 3. Count steps j to reach k=1.
 * 4. For this integer recurrence, j has mean/variance determined by harmonic
 *    sums (not Poisson): for n = 2^31-1, E[j] = 1 + H_n and Var(j)=H_n+H_n^(2).
 * 5. Repeat 100,000 times and use the sample mean of j, converted to a normal
 *    p-value with CLT scaling.
 */

#define NUM_RUNS 100000
#define START_K 2147483648.0 // 2^31
#define UINT32_SCALE 4294967296.0 // 2^32
#define EULER_GAMMA 0.5772156649015329

static inline double harmonic_1_asymptotic(double n) {
  // H_n = ln(n) + gamma + 1/(2n) - 1/(12 n^2) + O(n^-4)
  const double inv_n = 1.0 / n;
  return log(n) + EULER_GAMMA + 0.5 * inv_n - (inv_n * inv_n) / 12.0;
}

static inline double harmonic_2_asymptotic(double n) {
  // H_n^(2) = pi^2/6 - 1/n + 1/(2 n^2) + O(n^-3)
  const double inv_n = 1.0 / n;
  return (M_PI * M_PI) / 6.0 - inv_n + 0.5 * inv_n * inv_n;
}

bool squeeze(long double *value, unsigned long *hash, PRG gen, int *param,
             double *real_param, bool debug) {
  assert(param[2] == 1); // Returns one value
  assert(param[3] == 0); // fixed-size test; -n is not used

  long double sum_j = 0.0L;

  for (int i = 0; i < NUM_RUNS; i++) {
    double k = START_K;
    int j = 0;
    while (k > 1.0) {
      unsigned int u;
      if (!g_int32_lsb(&u, gen))
        return false;
      // Map to open interval (0,1): avoids endpoint artifacts at 0 and 1.
      double rand_u = ((double)u + 0.5) / UINT32_SCALE;
      k = ceil(k * rand_u);
      j++;
    }
    sum_j += (long double)j;
  }

  const double n = START_K - 1.0; // recurrence state count n = 2^31 - 1
  const double harmonic1 = harmonic_1_asymptotic(n);
  const double harmonic2 = harmonic_2_asymptotic(n);
  const double mean_j = 1.0 + harmonic1;
  const double var_j = harmonic1 + harmonic2;

  const double sample_mean = (double)(sum_j / (long double)NUM_RUNS);
  const double se = sqrt(var_j / (double)NUM_RUNS);
  *value = (long double)gsl_cdf_ugaussian_P((sample_mean - mean_j) / se);

  if (debug) {
    printf("Squeeze mean(j)=%.6f, expected=%.6f, se=%.6g, p-value=%10.8Lf\n",
           sample_mean, mean_j, se, *value);
  }

  unsigned int h1, h2;
  if (!g_int32_lsb(&h1, gen) || !g_int32_lsb(&h2, gen))
    return false;
  *hash = (((unsigned long)h2) << 32) + (unsigned long)h1;

  return true;
}
