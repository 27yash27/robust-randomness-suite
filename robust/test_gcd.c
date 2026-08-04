#include "test_func.h"
#include <gsl/gsl_cdf.h>
#include <math.h>

/*
 * Diehard Marsaglia-and-Tsang GCD Test (test #35 in this harness).
 *
 * For each of M = param[3] independent pairs (u, v) of 32-bit unsigned
 * integers, run Euclid's algorithm to compute gcd(u, v) and count the number
 * of reduction steps k. The step-count k is, to a good approximation, normal
 * with constants determined empirically by sampling 5,000,000 pairs from
 * /dev/urandom (mean = 18.7587, sigma = 3.4060) -- the asymptotic Porter
 * formula gives ~18.7 for ln(2^32), in close agreement with the simulation.
 * Under H0 the standardized sample mean
 *
 *     Z = sqrt(M) * (mean_k - mu_k) / sigma_k
 *
 * is approximately N(0,1), and we report the two-sided p-value
 * 2 * Phi(-|Z|).
 *
 * The harness reads 2*M = 2*param[3] integers from the generator. Pairs in
 * which one operand is zero would produce a degenerate Euclidean step count
 * and are skipped (they have probability ~2^-32 each, so their effect on the
 * sample mean is negligible).
 */

#define GCD_DIMENSION 1
#define GCD_MEAN_K 18.7587
#define GCD_SIGMA_K 3.4060

static int gcd_steps(unsigned int u, unsigned int v) {
  int k = 0;
  while (v != 0U) {
    unsigned int r = u % v;
    u = v;
    v = r;
    k++;
  }
  return k;
}

bool gcd(long double *value, unsigned long *hash, PRG gen, int *param,
         double *real_param, bool debug) {
  (void)real_param;
  assert(param[2] == GCD_DIMENSION);
  long M = param[3];
  assert(M >= 1);

  long double sum_k = 0.0L;
  long usable = 0;

  for (long i = 0; i < M; i++) {
    unsigned int u, v;
    if (!g_int32_lsb(&u, gen) || !g_int32_lsb(&v, gen)) {
      return false;
    }
    if (u == 0U || v == 0U) {
      continue;
    }
    sum_k += (long double)gcd_steps(u, v);
    usable++;
  }

  if (usable < 1) {
    return false;
  }

  double mean_k = (double)(sum_k / (long double)usable);
  double se = GCD_SIGMA_K / sqrt((double)usable);
  double z = (mean_k - GCD_MEAN_K) / se;
  double p_value = 2.0 * gsl_cdf_ugaussian_Q(fabs(z));
  if (p_value > 1.0) {
    p_value = 1.0;
  }
  value[0] = (long double)p_value;

  if (debug) {
    printf("GCD pairs=%ld mean_k=%.6f Z=%.6f p=%.6Lf\n", usable, mean_k, z,
           value[0]);
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
