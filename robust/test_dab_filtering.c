#include "test_func.h"
#include <math.h>
#include <gsl/gsl_cdf.h>

/*
 * Dieharder DAB filtering test, adapted to the robust two-sample KS harness.
 *
 * We read blocks of 8 independent 32-bit integers, map them to centered
 * uniforms in (-1/2, 1/2), and apply the zero-sum filter
 *   h = {+1, +1, +1, +1, -1, -1, -1, -1}.
 *
 * For a block output Y = sum h_i X_i with X_i ~ U(-1/2, 1/2), we have
 *   E[Y^2] = 2/3
 *   E[Y^4] = 19/15
 * so Var(Y^2) = 19/15 - (2/3)^2 = 37/45.
 *
 * Using non-overlapping blocks makes the squared outputs independent, so for
 * S = sum_j Y_j^2 over B blocks, the standardized statistic
 *   Z = (S - B * 2/3) / sqrt(B * 37/45)
 * is approximately N(0,1) for moderate B. In practice this means n should be
 * comfortably larger than one block; this implementation requires at least
 * 100 blocks before using the normal approximation. We return the corresponding
 * two-sided normal p-value as the scalar consumed by the KS framework.
 */

#define DAB_FILTERING_DIMENSION 1
#define DAB_FILTERING_WIDTH 8
#define DAB_FILTERING_MIN_BLOCKS 100
#define DAB_FILTERING_MEAN_SQ (2.0 / 3.0)
#define DAB_FILTERING_VAR_SQ (37.0 / 45.0)
#define UINT32_SCALE 4294967296.0

static double dab_filtering_centered_uniform(unsigned int x) {
  return ((double)x / UINT32_SCALE) - 0.5;
}

bool dab_filtering(long double *value, unsigned long *hash, PRG gen, int *param,
                   double *real_param, bool debug) {
  long n = param[3];
  long blocks;
  double sumsq = 0.0;

  (void)real_param;

  if (param[2] != DAB_FILTERING_DIMENSION || n < DAB_FILTERING_WIDTH ||
      (n % DAB_FILTERING_WIDTH) != 0) {
    return false;
  }

  blocks = n / DAB_FILTERING_WIDTH;
  if (blocks < DAB_FILTERING_MIN_BLOCKS) {
    return false;
  }

  for (long block = 0; block < blocks; block++) {
    double filtered = 0.0;

    for (int i = 0; i < DAB_FILTERING_WIDTH; i++) {
      unsigned int next;
      double x;

      if (!g_int32_lsb(&next, gen)) {
        return false;
      }

      x = dab_filtering_centered_uniform(next);
      if (i < DAB_FILTERING_WIDTH / 2) {
        filtered += x;
      } else {
        filtered -= x;
      }
    }

    sumsq += filtered * filtered;
  }

  {
    const double expected = (double)blocks * DAB_FILTERING_MEAN_SQ;
    const double variance = (double)blocks * DAB_FILTERING_VAR_SQ;
    const double z = (sumsq - expected) / sqrt(variance);
    value[0] = 2.0 * gsl_cdf_ugaussian_Q(fabs(z));

    if (debug) {
      printf("DAB filtering n=%ld blocks=%ld sumsq=%.12f z=%.12f p-value=%.12Lf\n",
             n, blocks, sumsq, z, value[0]);
    }
  }

  {
    unsigned int h1, h2;
    if (!g_int32_lsb(&h1, gen) || !g_int32_lsb(&h2, gen)) {
      return false;
    }
    *hash = (((unsigned long)h2) << 32) + (unsigned long)h1;
  }

  if (debug) {
    print64(*hash);
    printf("\n");
  }

  return true;
}
