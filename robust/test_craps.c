#include "test_func.h"
#include <math.h>
#include <gsl/gsl_cdf.h>

/*
 * Diehard Craps test.
 *
 * The test simulates 200,000 games of craps using the generator's 32-bit
 * integer stream. Each integer is converted to one die throw exactly as in the
 * original Diehard description: map x to floor(6 * x / 2^32) + 1.
 *
 * It returns two KS-friendly coordinates:
 *   value[0]: two-sided normal p-value for the total number of wins
 *   value[1]: chi-square p-value for the throws-per-game histogram
 *             with bins 1, 2, ..., 20, and 21 meaning "21 or more throws"
 */

#define CRAPS_DIMENSION 2
#define CRAPS_GAMES 200000L
#define CRAPS_THROW_BINS 21
#define CRAPS_WIN_PROB (244.0 / 495.0)

static bool craps_probs_initialized = false;
static double craps_throw_prob[CRAPS_THROW_BINS + 1];

static int craps_die_from_uint32(unsigned int x) {
  return 1 + (int)(6.0 * ((double)x / 4294967296.0));
}

static bool craps_roll_sum(int *sum, PRG gen) {
  unsigned int x1, x2;
  if (!g_int32_lsb(&x1, gen) || !g_int32_lsb(&x2, gen)) {
    return false;
  }
  *sum = craps_die_from_uint32(x1) + craps_die_from_uint32(x2);
  return true;
}

static void craps_init_probs(void) {
  const int point_mult[6] = {3, 4, 5, 5, 4, 3};

  craps_throw_prob[1] = 12.0 / 36.0;

  for (int throws = 2; throws < CRAPS_THROW_BINS; throws++) {
    double prob = 0.0;
    for (int i = 0; i < 6; i++) {
      const double c = (double)point_mult[i];
      const double establish = c / 36.0;
      const double continue_prob = (30.0 - c) / 36.0;
      const double resolve_prob = (6.0 + c) / 36.0;
      prob += establish * pow(continue_prob, (double)(throws - 2)) * resolve_prob;
    }
    craps_throw_prob[throws] = prob;
  }

  craps_throw_prob[CRAPS_THROW_BINS] = 1.0;
  for (int throws = 1; throws < CRAPS_THROW_BINS; throws++) {
    craps_throw_prob[CRAPS_THROW_BINS] -= craps_throw_prob[throws];
  }

  craps_probs_initialized = true;
}

bool craps(long double *value, unsigned long *hash, PRG gen, int *param,
           double *real_param, bool debug) {
  long wins = 0;
  long throw_counts[CRAPS_THROW_BINS + 1];
  const double mean_wins = CRAPS_GAMES * CRAPS_WIN_PROB;
  const double sigma_wins =
      sqrt(CRAPS_GAMES * CRAPS_WIN_PROB * (1.0 - CRAPS_WIN_PROB));
  double chisq = 0.0;

  (void)real_param;
  assert(param[2] == CRAPS_DIMENSION);
  assert(param[3] == 0);

  if (!craps_probs_initialized) {
    // The harness drives tests sequentially, so one-time lazy init is enough.
    craps_init_probs();
  }

  for (int i = 0; i <= CRAPS_THROW_BINS; i++) {
    throw_counts[i] = 0;
  }

  for (long game = 0; game < CRAPS_GAMES; game++) {
    int roll_sum;
    int point = 0;
    int throws = 1;

    if (!craps_roll_sum(&roll_sum, gen)) {
      return false;
    }

    if (roll_sum == 7 || roll_sum == 11) {
      wins++;
    } else if (roll_sum == 2 || roll_sum == 3 || roll_sum == 12) {
      /* immediate loss */
    } else {
      point = roll_sum;
      while (true) {
        throws++;
        if (!craps_roll_sum(&roll_sum, gen)) {
          return false;
        }
        if (roll_sum == point) {
          wins++;
          break;
        }
        if (roll_sum == 7) {
          break;
        }
      }
    }

    if (throws > CRAPS_THROW_BINS) {
      throws = CRAPS_THROW_BINS;
    }
    throw_counts[throws]++;
  }

  {
    const double z = fabs(((double)wins - mean_wins) / sigma_wins);
    value[0] = 2.0L * gsl_cdf_ugaussian_Q(z);
  }

  for (int throws = 1; throws <= CRAPS_THROW_BINS; throws++) {
    const double expected = CRAPS_GAMES * craps_throw_prob[throws];
    const double diff = (double)throw_counts[throws] - expected;
    chisq += (diff * diff) / expected;
  }
  value[1] = gsl_cdf_chisq_Q((double)chisq, (double)(CRAPS_THROW_BINS - 1));

  {
    unsigned int h1, h2;
    if (!g_int32_lsb(&h1, gen) || !g_int32_lsb(&h2, gen)) {
      return false;
    }
    *hash = (((unsigned long)h2) << 32) + (unsigned long)h1;
  }

  if (debug) {
    printf("Craps wins: %ld (p-value %.12Lf)\n", wins, value[0]);
    printf("Craps throws chi-square: %.12f (p-value %.12Lf)\n", chisq,
           value[1]);
  }

  return true;
}
