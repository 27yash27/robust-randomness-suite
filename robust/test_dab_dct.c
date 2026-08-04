#include "test_func.h"
#include <math.h>
#include <gsl/gsl_cdf.h>

/*
 * Dieharder DAB DCT (Discrete Cosine Transform), robustified for the
 * two-sample KS harness.
 *
 * The test reads n 32-bit integers, maps them to centered uniforms in
 * (-1/2, 1/2), applies an orthonormal DCT-II, and measures the low-frequency
 * spectral energy excluding the DC component. For random input this energy is
 * approximately chi-square distributed after scaling by the input variance
 * (1/12 for centered uniforms). The exact calibration is not critical for the
 * robust two-sample scheme, but returning a p-value-like scalar is convenient.
 *
 * Streaming implementation: only the m low-frequency DCT coefficients are
 * tracked (m <= DAB_DCT_MAX_FREQS = 64). For each streamed sample x_i we
 * accumulate the product x_i * cos(pi * (i + 0.5) * k / n) into the k-th
 * coefficient for k = 1..m. Memory is O(m) = constant rather than O(n), so
 * the test scales to 10 GB+ inputs without holding the data in RAM.
 */

#define DAB_DCT_DIMENSION 1
#define DAB_DCT_MAX_FREQS 64

static double dab_dct_alpha(long n, long k) {
  if (k == 0) {
    return sqrt(1.0 / (double)n);
  }
  return sqrt(2.0 / (double)n);
}

bool dab_dct(long double *value, unsigned long *hash, PRG gen, int *param,
             double *real_param, bool debug) {
  long n = param[3];
  long m;
  double coef[DAB_DCT_MAX_FREQS];
  double energy = 0.0;

  (void)real_param;
  if (param[2] != DAB_DCT_DIMENSION || n < 2) {
    return false;
  }

  m = n / 8;
  if (m < 1) {
    m = 1;
  }
  if (m > DAB_DCT_MAX_FREQS) {
    m = DAB_DCT_MAX_FREQS;
  }

  for (long k = 0; k < m; k++) {
    coef[k] = 0.0;
  }

  /* theta[k] = pi * (k+1) / n; pre-compute once to avoid n*m divisions. */
  double theta[DAB_DCT_MAX_FREQS];
  for (long k = 0; k < m; k++) {
    theta[k] = M_PI * (double)(k + 1) / (double)n;
  }

  for (long i = 0; i < n; i++) {
    unsigned int next;
    if (!g_int32_lsb(&next, gen)) {
      return false;
    }
    double x_i = ((double)next / 4294967296.0) - 0.5;
    double phase_base = (double)i + 0.5;
    for (long k = 0; k < m; k++) {
      coef[k] += x_i * cos(phase_base * theta[k]);
    }
  }

  for (long k = 0; k < m; k++) {
    double scaled = coef[k] * dab_dct_alpha(n, k + 1);
    energy += scaled * scaled;
  }

  value[0] = (long double)gsl_cdf_chisq_Q(12.0 * energy, (double)m);

  {
    unsigned int h1, h2;
    if (!g_int32_lsb(&h1, gen) || !g_int32_lsb(&h2, gen)) {
      return false;
    }
    *hash = (((unsigned long)h2) << 32) + (unsigned long)h1;
  }

  if (debug) {
    printf("DAB DCT n=%ld low-freq-count=%ld energy=%.12f p-value=%.12Lf\n",
           n, m, energy, value[0]);
  }

  return true;
}
