#include "test_func.h"
#include <gsl/gsl_eigen.h>
#include <gsl/gsl_matrix.h>

/*
 * Diehard OPERM5 (Overlapping 5-permutations)
 *
 * This implementation follows the Diehard-style block formulation: read
 * 1,000 blocks of 1,000 32-bit integers, and for each block count the order
 * type of 1,000 circular windows of length 5. There are 5! = 120 possible
 * orderings, so the test accumulates 1,000,000 total observations and
 * evaluates the quadratic form based on the exact covariance of these
 * overlapping circular counts. The covariance has numerical rank 96, where
 * Diehard and Dieharder use 99. The difference is the circular window: closing
 * the sequence into a ring adds three linear constraints among the 120
 * permutation counts that an open window does not impose, so three further
 * eigenvalues vanish. The rank is asserted below, because a platform that
 * computes a different one would silently change every p-value from this test.
 *
 * For the robust two-sample KS framework we return the upper-tail chi-square
 * p-value as a single scalar. The exact normalization is not required for the
 * KS comparison, but keeping the usual p-value scale is convenient.
 */

#define OPERM5_DIMENSION 1
#define OPERM5_WINDOW 5
#define OPERM5_STATES 120
#define OPERM5_BLOCK_LEN 1000
#define OPERM5_NUM_BLOCKS 1000
#define OPERM5_NINTS ((long)OPERM5_BLOCK_LEN * (long)OPERM5_NUM_BLOCKS)
#define OPERM5_OBSERVATIONS_PER_BLOCK OPERM5_BLOCK_LEN
#define OPERM5_TOTAL_OBSERVATIONS OPERM5_NINTS
#define OPERM5_MAX_ITEMS 9

static bool operm5_initialized = false;
static bool operm5_init_ok = false;
/* Rank of the 120x120 covariance under the circular-window construction. */
#define OPERM5_EXPECTED_RANK 96
static int operm5_rank = 0;
static double operm5_factorial[OPERM5_MAX_ITEMS + 1];
static int operm5_perms[OPERM5_STATES][OPERM5_WINDOW];
static double operm5_pinv[OPERM5_STATES][OPERM5_STATES];

static void operm5_init_factorial(void) {
  operm5_factorial[0] = 1.0;
  for (int i = 1; i <= OPERM5_MAX_ITEMS; i++) {
    operm5_factorial[i] = operm5_factorial[i - 1] * (double)i;
  }
}

static void operm5_init_permutations(void) {
  int p[OPERM5_WINDOW] = {0, 1, 2, 3, 4};
  int idx = 0;

  while (true) {
    for (int i = 0; i < OPERM5_WINDOW; i++) {
      operm5_perms[idx][i] = p[i];
    }
    idx++;

    int i = OPERM5_WINDOW - 2;
    while (i >= 0 && p[i] >= p[i + 1]) {
      i--;
    }
    if (i < 0) {
      break;
    }

    int j = OPERM5_WINDOW - 1;
    while (p[j] <= p[i]) {
      j--;
    }
    int tmp = p[i];
    p[i] = p[j];
    p[j] = tmp;

    for (int a = i + 1, b = OPERM5_WINDOW - 1; a < b; a++, b--) {
      tmp = p[a];
      p[a] = p[b];
      p[b] = tmp;
    }
  }

  assert(idx == OPERM5_STATES);
}

static int operm5_rank_perm(const int perm[OPERM5_WINDOW]) {
  int avail[OPERM5_WINDOW] = {0, 1, 2, 3, 4};
  int remaining = OPERM5_WINDOW;
  int idx = 0;

  for (int i = 0; i < OPERM5_WINDOW; i++) {
    int pos = 0;
    while (pos < remaining && avail[pos] != perm[i]) {
      pos++;
    }
    assert(pos < remaining);
    idx = idx * remaining + pos;
    for (int j = pos; j + 1 < remaining; j++) {
      avail[j] = avail[j + 1];
    }
    remaining--;
  }
  return idx;
}

static int operm5_window_state(const unsigned int x[OPERM5_WINDOW]) {
  int order[OPERM5_WINDOW] = {0, 1, 2, 3, 4};

  for (int i = 1; i < OPERM5_WINDOW; i++) {
    int cur = order[i];
    int j = i - 1;
    while (j >= 0) {
      const unsigned int vj = x[order[j]];
      if (vj < x[cur] || (vj == x[cur] && order[j] < cur)) {
        break;
      }
      order[j + 1] = order[j];
      j--;
    }
    order[j + 1] = cur;
  }

  return operm5_rank_perm(order);
}

static unsigned long long operm5_count_extensions(const unsigned int pred[],
                                                  int n) {
  const int total_masks = 1 << n;
  unsigned long long dp[1 << OPERM5_MAX_ITEMS];

  for (int i = 0; i < total_masks; i++) {
    dp[i] = 0;
  }
  dp[0] = 1;

  for (int mask = 0; mask < total_masks; mask++) {
    if (dp[mask] == 0) {
      continue;
    }
    for (int v = 0; v < n; v++) {
      if ((mask & (1 << v)) != 0) {
        continue;
      }
      if ((pred[v] & (unsigned int)(~mask)) == 0U) {
        dp[mask | (1 << v)] += dp[mask];
      }
    }
  }

  return dp[total_masks - 1];
}

static double operm5_joint_probability(int idx_a, int idx_b, int lag) {
  const int n = OPERM5_WINDOW + lag;
  unsigned int pred[OPERM5_MAX_ITEMS];
  // The covariance model assumes continuous values; real 32-bit ties are
  // broken by position in operm5_window_state and are negligibly rare.

  for (int i = 0; i < n; i++) {
    pred[i] = 0U;
  }

  for (int later = 0; later < OPERM5_WINDOW; later++) {
    const int v_later = operm5_perms[idx_a][later];
    for (int earlier = 0; earlier < later; earlier++) {
      const int v_earlier = operm5_perms[idx_a][earlier];
      pred[v_later] |= (1U << v_earlier);
    }
  }

  for (int later = 0; later < OPERM5_WINDOW; later++) {
    const int v_later = lag + operm5_perms[idx_b][later];
    for (int earlier = 0; earlier < later; earlier++) {
      const int v_earlier = lag + operm5_perms[idx_b][earlier];
      pred[v_later] |= (1U << v_earlier);
    }
  }

  return (double)operm5_count_extensions(pred, n) / operm5_factorial[n];
}

static bool operm5_init_covariance(void) {
  const double p = 1.0 / (double)OPERM5_STATES;
  const size_t joint_size =
      (size_t)OPERM5_WINDOW * (size_t)OPERM5_STATES * (size_t)OPERM5_STATES;
  double max_eval = 0.0;
  double tol = 0.0;
  double *joint = (double *)malloc(joint_size * sizeof(double));
  gsl_matrix *cov = gsl_matrix_alloc(OPERM5_STATES, OPERM5_STATES);
  gsl_matrix *evec = gsl_matrix_alloc(OPERM5_STATES, OPERM5_STATES);
  gsl_vector *eval = gsl_vector_alloc(OPERM5_STATES);
  gsl_eigen_symmv_workspace *work = gsl_eigen_symmv_alloc(OPERM5_STATES);

  if (joint == NULL || cov == NULL || evec == NULL || eval == NULL || work == NULL)
    goto cleanup;

#define OPERM5_JOINT_AT(lag, a, b)                                             \
  joint[(((size_t)(lag) * (size_t)OPERM5_STATES) + (size_t)(a)) *              \
            (size_t)OPERM5_STATES +                                             \
        (size_t)(b)]

  for (int lag = 1; lag < OPERM5_WINDOW; lag++) {
    for (int a = 0; a < OPERM5_STATES; a++) {
      for (int b = 0; b < OPERM5_STATES; b++) {
        OPERM5_JOINT_AT(lag, a, b) = operm5_joint_probability(a, b, lag);
      }
    }
  }

  for (int a = 0; a < OPERM5_STATES; a++) {
    for (int b = 0; b < OPERM5_STATES; b++) {
      double entry =
          (double)OPERM5_OBSERVATIONS_PER_BLOCK * (((a == b) ? p : 0.0) - p * p);

      for (int lag = 1; lag < OPERM5_WINDOW; lag++) {
        const double pab = OPERM5_JOINT_AT(lag, a, b);
        const double pba = OPERM5_JOINT_AT(lag, b, a);
        entry += (double)OPERM5_OBSERVATIONS_PER_BLOCK *
                 (pab + pba - 2.0 * p * p);
      }
      entry *= (double)OPERM5_NUM_BLOCKS;
      gsl_matrix_set(cov, a, b, entry);
    }
  }

  if (gsl_eigen_symmv(cov, eval, evec, work) != 0) {
    goto cleanup;
  }

  gsl_eigen_symmv_sort(eval, evec, GSL_EIGEN_SORT_ABS_DESC);

  max_eval = fabs(gsl_vector_get(eval, 0));
  tol = (max_eval > 0.0) ? max_eval * 1e-12 : 1e-12;

  for (int i = 0; i < OPERM5_STATES; i++) {
    for (int j = 0; j < OPERM5_STATES; j++) {
      operm5_pinv[i][j] = 0.0;
    }
  }

  operm5_rank = 0;
  for (int k = 0; k < OPERM5_STATES; k++) {
    const double lambda = gsl_vector_get(eval, k);
    if (fabs(lambda) <= tol) {
      continue;
    }

    operm5_rank++;
    for (int i = 0; i < OPERM5_STATES; i++) {
      const double vik = gsl_matrix_get(evec, i, k);
      for (int j = 0; j < OPERM5_STATES; j++) {
        operm5_pinv[i][j] += vik * gsl_matrix_get(evec, j, k) / lambda;
      }
    }
  }

cleanup:
  if (joint != NULL)
    free(joint);
  if (cov != NULL)
    gsl_matrix_free(cov);
  if (evec != NULL)
    gsl_matrix_free(evec);
  if (eval != NULL)
    gsl_vector_free(eval);
  if (work != NULL)
    gsl_eigen_symmv_free(work);

  /* The rank is a property of the construction, not of the platform. If a
   * different GSL build puts a near-zero eigenvalue on the other side of the
   * tolerance, every p-value from this test shifts, so fail loudly instead. */
  if (operm5_rank != OPERM5_EXPECTED_RANK) {
    fprintf(stderr,
            "OPERM5: covariance rank %d, expected %d. The chi-square degrees of "
            "freedom would be wrong, so this test is disabled on this build.\n",
            operm5_rank, OPERM5_EXPECTED_RANK);
    return (false);
  }
  return (operm5_rank > 0);
}

static bool operm5_prepare(void) {
  if (operm5_initialized) {
    return operm5_init_ok;
  }

  operm5_initialized = true;
  operm5_init_factorial();
  operm5_init_permutations();
  operm5_init_ok = operm5_init_covariance();
  return operm5_init_ok;
}

bool operm5(long double *value, unsigned long *hash, PRG gen, int *param,
            double *real_param, bool debug) {
  long counts[OPERM5_STATES];
  unsigned int block[OPERM5_BLOCK_LEN];
  unsigned int window[OPERM5_WINDOW];
  double centered[OPERM5_STATES];
  double statistic = 0.0;
  const double expected =
      (double)OPERM5_TOTAL_OBSERVATIONS / (double)OPERM5_STATES;

  (void)real_param;
  assert(param[2] == OPERM5_DIMENSION);
  assert(param[3] == OPERM5_NINTS);

  if (!operm5_prepare()) {
    return false;
  }

  for (int i = 0; i < OPERM5_STATES; i++) {
    counts[i] = 0;
  }

  for (int blk = 0; blk < OPERM5_NUM_BLOCKS; blk++) {
    for (int i = 0; i < OPERM5_BLOCK_LEN; i++) {
      if (!g_int32_lsb(&block[i], gen)) {
        return false;
      }
    }

    for (int start = 0; start < OPERM5_BLOCK_LEN; start++) {
      for (int j = 0; j < OPERM5_WINDOW; j++) {
        window[j] = block[(start + j) % OPERM5_BLOCK_LEN];
      }
      counts[operm5_window_state(window)]++;
    }
  }

  for (int i = 0; i < OPERM5_STATES; i++) {
    centered[i] = (double)counts[i] - expected;
  }

  for (int i = 0; i < OPERM5_STATES; i++) {
    double row = 0.0;
    for (int j = 0; j < OPERM5_STATES; j++) {
      row += operm5_pinv[i][j] * centered[j];
    }
    statistic += centered[i] * row;
  }

  value[0] = (long double)gsl_cdf_chisq_Q(statistic, (double)operm5_rank);

  {
    unsigned int h1, h2;
    if ((!g_int32_lsb(&h1, gen)) || (!g_int32_lsb(&h2, gen))) {
      return false;
    }
    *hash = (((unsigned long)h2) << 32) + (unsigned long)h1;
  }

  if (debug) {
    printf("OPERM5 statistic: %.12f\n", statistic);
    printf("OPERM5 rank: %d\n", operm5_rank);
    printf("OPERM5 p-value: %.12Lf\n", value[0]);
  }

  return true;
}
