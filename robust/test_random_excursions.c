#include "test_func.h"
#include <gsl/gsl_cdf.h>
#include <gsl/gsl_sf.h>
#include <math.h>

/*
 * NIST 800-22 Random Excursions Test (test #32 in this harness).
 *
 * The bitstream from param[3] consecutive 32-bit integers is mapped to a
 * +/-1 random walk S_0, S_1, ..., S_{n-1} with n = 32*param[3]. The walk is
 * partitioned into cycles by the zero-crossings of the partial sum. For each
 * non-zero state x in {-4,-3,-2,-1,1,2,3,4} and each cycle, the test counts
 * the number of visits to x; the resulting empirical histogram (binned at
 * 0,1,2,3,4,>=5) is compared against the theoretical distribution from
 * NIST SP 800-22 (Section 2.14) via a chi-square statistic. The output is the
 * 8-tuple of upper-tail p-values, one per state.
 *
 * Streaming implementation: rather than storing the full S[] array and
 * walking cycles afterwards, we accumulate per-cycle visit counters online
 * and merge them into the histogram each time S returns to zero. Memory is
 * O(1) regardless of input size, so this test scales to multi-GB sweeps.
 *
 * If the walk produces too few cycles to make the chi-square approximation
 * reliable (J < max(0.005*sqrt(n), 500)), the test returns false so that the
 * harness records a parse_error rather than a misleading p-value.
 *
 * NOTE: J (zero-crossing count) is heavy-tailed for random walks --
 * empirically the per-sample J fluctuates by 5-10x even on /dev/urandom.
 * Because the rtest harness aborts an entire batch when a single test
 * invocation returns false, sweeps must size n_ints large enough that
 * J >= 500 holds with very high probability. Recommend n_ints >= 200_000
 * (E[J] ~ 2000, so J < 500 is rare); n_ints = 100_000 will produce
 * intermittent batch failures.
 */

#define RE_DIMENSION 8
#define RE_NUM_STATES 8
#define RE_NUM_BINS 6

static const int re_state_values[RE_NUM_STATES] = {-4, -3, -2, -1, 1, 2, 3, 4};

/* pi[|x|][k]: probability that state x is visited exactly k times in a cycle,
 * for k = 0,1,2,3,4,>=5. Rows indexed by |x| from 1 to 4. */
static const double re_pi[5][RE_NUM_BINS] = {
    {0.0, 0.0, 0.0, 0.0, 0.0, 0.0},
    {0.5000000000, 0.25000000000, 0.12500000000, 0.06250000000, 0.03125000000, 0.0312500000},
    {0.7500000000, 0.06250000000, 0.04687500000, 0.03515625000, 0.02636718750, 0.0791015625},
    {0.8333333333, 0.02777777778, 0.02314814815, 0.01929012346, 0.01607510288, 0.0803755143},
    {0.8750000000, 0.01562500000, 0.01367187500, 0.01196289063, 0.01046752930, 0.0732727051}};

static inline void re_flush_cycle(int counter[RE_NUM_STATES],
                                  double nu[RE_NUM_BINS][RE_NUM_STATES]) {
  for (int s = 0; s < RE_NUM_STATES; s++) {
    int c = counter[s];
    if (c >= 5) {
      nu[5][s] += 1.0;
    } else {
      nu[c][s] += 1.0;
    }
    counter[s] = 0;
  }
}

bool random_excursions(long double *value, unsigned long *hash, PRG gen,
                       int *param, double *real_param, bool debug) {
  (void)real_param;
  assert(param[2] == RE_DIMENSION);
  long n_ints = param[3];
  assert(n_ints >= 1);
  long n = 32L * n_ints;

  long sum = 0;
  long J = 0; /* number of completed cycles (zero crossings) */
  int counter[RE_NUM_STATES] = {0, 0, 0, 0, 0, 0, 0, 0};
  double nu[RE_NUM_BINS][RE_NUM_STATES];
  for (int k = 0; k < RE_NUM_BINS; k++) {
    for (int s = 0; s < RE_NUM_STATES; s++) {
      nu[k][s] = 0.0;
    }
  }

  /* Single-pass: stream bits, update the running sum, accumulate per-cycle
   * visit counters, and flush them into nu[][] at every zero-crossing. */
  for (long i = 0; i < n_ints; i++) {
    unsigned int next;
    if (!g_int32_lsb(&next, gen)) {
      return false;
    }
    for (int b = 0; b < 32; b++) {
      int xi = (int)((next >> b) & 1U); /* 0 or 1 */
      sum += (xi == 1) ? 1 : -1;
      if (sum >= 1 && sum <= 4) {
        counter[(int)sum + 3]++;
      } else if (sum >= -4 && sum <= -1) {
        counter[(int)sum + 4]++;
      } else if (sum == 0) {
        re_flush_cycle(counter, nu);
        J++;
      }
    }
  }
  /* If the walk ended above or below zero, the trailing partial cycle still
   * counts in NIST's cycle accounting. */
  if (sum != 0) {
    re_flush_cycle(counter, nu);
    J++;
  }

  double constraint = 0.005 * sqrt((double)n);
  if (constraint < 500.0) {
    constraint = 500.0;
  }
  if ((double)J < constraint) {
    if (debug) {
      printf("Random excursions: too few cycles (J=%ld < %f), aborting\n", J,
             constraint);
    }
    return false;
  }

  for (int s = 0; s < RE_NUM_STATES; s++) {
    int x = re_state_values[s];
    int abs_x = (x < 0) ? -x : x;
    double chi2 = 0.0;
    for (int k = 0; k < RE_NUM_BINS; k++) {
      double expected = (double)J * re_pi[abs_x][k];
      double diff = nu[k][s] - expected;
      chi2 += diff * diff / expected;
    }
    value[s] = (long double)gsl_sf_gamma_inc_Q(2.5, chi2 / 2.0);
    if (debug) {
      printf("Random excursions x=%2d chi2=%.6f p=%.6Lf\n", x, chi2, value[s]);
    }
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
