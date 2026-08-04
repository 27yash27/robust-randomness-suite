#include "test_func.h"
#include <math.h>

/*
 * NIST 800-22 Runs Test (test #37 in this harness).
 *
 * Counts the number V of "runs" -- maximal subsequences of identical bits --
 * in the n = 32*param[3] bit stream. Under H0 the expected number of runs
 * given the observed proportion pi of 1-bits is 2*n*pi*(1-pi); the
 * standardized deviation
 *
 *     |V - 2*n*pi*(1-pi)| / (2*pi*(1-pi)*sqrt(2*n))
 *
 * is normally distributed and the two-sided p-value is reported via erfc.
 *
 * Distinct from Knuth-Diehard "knuth_runs" (test 7), which counts ascending
 * and descending runs of 32-bit integers rather than bit-level transitions.
 *
 * NIST recommends running monobit (test 20) first; if the proportion of 1s
 * is too far from 0.5 (|pi - 0.5| > 2/sqrt(n)), the chi-square approximation
 * breaks down and the test returns p = 0.
 */

#define RUNS_NIST_DIMENSION 1

bool runs_nist(long double *value, unsigned long *hash, PRG gen, int *param,
               double *real_param, bool debug) {
  (void)real_param;
  assert(param[2] == RUNS_NIST_DIMENSION);
  long n_ints = param[3];
  assert(n_ints >= 1);
  long n = 32L * n_ints;

  long count_ones = 0;
  long V = 1; /* runs count */
  int prev_bit = -1;

  for (long i = 0; i < n_ints; i++) {
    unsigned int next;
    if (!g_int32_lsb(&next, gen)) {
      return false;
    }
    for (int b = 0; b < 32; b++) {
      int bit = (int)((next >> b) & 1U);
      if (bit == 1) {
        count_ones++;
      }
      if (prev_bit == -1) {
        prev_bit = bit;
      } else if (bit != prev_bit) {
        V++;
        prev_bit = bit;
      }
    }
  }

  double pi_hat = (double)count_ones / (double)n;
  double tau = 2.0 / sqrt((double)n);

  double p_value;
  if (fabs(pi_hat - 0.5) > tau) {
    /* Pre-test failure: bit proportion is too far from 0.5 */
    p_value = 0.0;
    if (debug) {
      printf("Runs (NIST): pi=%.6f failed pre-test (tau=%.6f)\n", pi_hat, tau);
    }
  } else {
    double erfc_arg = fabs((double)V - 2.0 * (double)n * pi_hat * (1.0 - pi_hat)) /
                      (2.0 * pi_hat * (1.0 - pi_hat) * sqrt(2.0 * (double)n));
    p_value = erfc(erfc_arg);
    if (debug) {
      printf("Runs (NIST): pi=%.6f V=%ld arg=%.6f p=%.6f\n", pi_hat, V,
             erfc_arg, p_value);
    }
  }
  value[0] = (long double)p_value;

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
