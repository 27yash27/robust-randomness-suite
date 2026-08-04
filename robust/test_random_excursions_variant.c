#include "test_func.h"
#include <math.h>

/*
 * NIST 800-22 Random Excursions Variant Test (test #33 in this harness).
 *
 * Builds the same +/-1 cumulative-sum walk S_0, ..., S_{n-1} from
 * n = 32*param[3] bits as the Random Excursions test, but reduces each
 * non-zero state x in {-9,...,-1,1,...,9} to a single visit count and a
 * normal p-value
 *
 *     p_value(x) = erfc( |xi(x) - J| / sqrt( 2*J*(4*|x|-2) ) )
 *
 * where xi(x) is the total number of indices i with S[i]==x and J is the
 * number of zero-crossings (cycles). Returns the 18-tuple of p-values, one
 * per state. Aborts with false (parse_error) when J is below the standard
 * NIST minimum of max(0.005*sqrt(n), 500).
 *
 * Same J-heavy-tail caveat as test_random_excursions: size n_ints >= 200_000
 * for reliable batches.
 */

#define REV_DIMENSION 18
#define REV_NUM_STATES 18

static const int rev_state_values[REV_NUM_STATES] = {
    -9, -8, -7, -6, -5, -4, -3, -2, -1, 1, 2, 3, 4, 5, 6, 7, 8, 9};

bool random_excursions_variant(long double *value, unsigned long *hash,
                               PRG gen, int *param, double *real_param,
                               bool debug) {
  (void)real_param;
  assert(param[2] == REV_DIMENSION);
  long n_ints = param[3];
  assert(n_ints >= 1);
  long n = 32L * n_ints;

  /* Counts of visits to each of the 18 target states; zero-crossings J. */
  long counts[REV_NUM_STATES];
  for (int i = 0; i < REV_NUM_STATES; i++) {
    counts[i] = 0;
  }

  long sum = 0;
  long J = 0;
  long last_S = 0;

  for (long i = 0; i < n_ints; i++) {
    unsigned int next;
    if (!g_int32_lsb(&next, gen)) {
      return false;
    }
    for (int b = 0; b < 32; b++) {
      int xi = (int)((next >> b) & 1U);
      sum += (xi == 1) ? 1 : -1;
      if (sum >= -9 && sum <= 9 && sum != 0) {
        counts[(sum < 0) ? (sum + 9) : (sum + 8)]++;
      }
      if (sum == 0) {
        J++;
      }
      last_S = sum;
    }
  }
  if (last_S != 0) {
    J++;
  }

  double constraint = 0.005 * sqrt((double)n);
  if (constraint < 500.0) {
    constraint = 500.0;
  }
  if ((double)J < constraint) {
    if (debug) {
      printf("Random excursions variant: too few cycles (J=%ld < %f)\n", J,
             constraint);
    }
    return false;
  }

  for (int s = 0; s < REV_NUM_STATES; s++) {
    int x = rev_state_values[s];
    int abs_x = (x < 0) ? -x : x;
    double denom = sqrt(2.0 * (double)J * (4.0 * (double)abs_x - 2.0));
    double p = erfc(fabs((double)counts[s] - (double)J) / denom);
    value[s] = (long double)p;
    if (debug) {
      printf("Random excursions variant x=%2d count=%ld p=%.6Lf\n", x,
             counts[s], value[s]);
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
