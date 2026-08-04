#include "test_func.h"
#include <gsl/gsl_sf.h>
#include <math.h>

/*
 * NIST 800-22 Longest Run of Ones in a Block (test #38 in this harness).
 *
 * The n = 32*param[3] bit stream is split into N = n/M blocks of length M;
 * for each block the length of the longest run of consecutive 1s is recorded
 * and binned into K+1 categories. A chi-square statistic against tabulated
 * NIST probabilities (SP 800-22 Sec. 2.4) gives the p-value.
 *
 * Block size M is chosen by the standard NIST schedule:
 *   n <    6272 -> M = 8,    K = 3, bins {<=1, 2, 3, >=4}
 *   n <  750000 -> M = 128,  K = 5, bins {<=4, 5, 6, 7, 8, >=9}
 *   otherwise   -> M = 10000,K = 6, bins {<=10, 11, 12, 13, 14, 15, >=16}
 *
 * Aborts (returns false) when n < 128, the documented minimum length.
 */

#define LONGEST_RUN_DIMENSION 1

bool longest_run(long double *value, unsigned long *hash, PRG gen, int *param,
                 double *real_param, bool debug) {
  (void)real_param;
  assert(param[2] == LONGEST_RUN_DIMENSION);
  long n_ints = param[3];
  assert(n_ints >= 1);
  long n = 32L * n_ints;
  if (n < 128) {
    return false;
  }

  int K, M;
  int V[7];
  double pi[7];

  if (n < 6272) {
    K = 3;
    M = 8;
    V[0] = 1; V[1] = 2; V[2] = 3; V[3] = 4;
    pi[0] = 0.21484375;
    pi[1] = 0.3671875;
    pi[2] = 0.23046875;
    pi[3] = 0.1875;
  } else if (n < 750000) {
    K = 5;
    M = 128;
    V[0] = 4; V[1] = 5; V[2] = 6; V[3] = 7; V[4] = 8; V[5] = 9;
    pi[0] = 0.1174035788;
    pi[1] = 0.242955959;
    pi[2] = 0.249363483;
    pi[3] = 0.17517706;
    pi[4] = 0.102701071;
    pi[5] = 0.112398847;
  } else {
    K = 6;
    M = 10000;
    V[0] = 10; V[1] = 11; V[2] = 12; V[3] = 13; V[4] = 14; V[5] = 15; V[6] = 16;
    pi[0] = 0.0882;
    pi[1] = 0.2092;
    pi[2] = 0.2483;
    pi[3] = 0.1933;
    pi[4] = 0.1208;
    pi[5] = 0.0675;
    pi[6] = 0.0727;
  }

  long N = n / (long)M;
  if (N < 1) {
    return false;
  }

  unsigned int nu[7] = {0, 0, 0, 0, 0, 0, 0};

  /* Stream bits block-by-block to avoid allocating the full bit array. */
  unsigned int bit_buf = 0;
  int bit_buf_pos = 32;
  long bits_consumed = 0;
  long bits_to_use = N * (long)M;

  int run = 0;
  int v_n_obs = 0;
  long block_pos = 0;

  while (bits_consumed < bits_to_use) {
    if (bit_buf_pos == 32) {
      if (!g_int32_lsb(&bit_buf, gen)) {
        return false;
      }
      bit_buf_pos = 0;
    }
    int bit = (int)((bit_buf >> bit_buf_pos) & 1U);
    bit_buf_pos++;
    bits_consumed++;

    if (bit == 1) {
      run++;
      if (run > v_n_obs) {
        v_n_obs = run;
      }
    } else {
      run = 0;
    }

    block_pos++;
    if (block_pos == M) {
      /* End of block: bin v_n_obs */
      if (v_n_obs < V[0]) {
        nu[0]++;
      } else if (v_n_obs > V[K]) {
        nu[K]++;
      } else {
        for (int j = 0; j <= K; j++) {
          if (v_n_obs == V[j]) {
            nu[j]++;
            break;
          }
        }
      }
      block_pos = 0;
      run = 0;
      v_n_obs = 0;
    }
  }

  /* Drain the rest of param[3] worth of words so the harness's
   * "param[3] integers consumed" convention is respected. */
  long words_used = (bits_consumed + 31) / 32;
  for (long i = words_used; i < n_ints; i++) {
    unsigned int discard;
    if (!g_int32_lsb(&discard, gen)) {
      return false;
    }
  }

  double chi2 = 0.0;
  for (int i = 0; i <= K; i++) {
    double expected = (double)N * pi[i];
    double diff = (double)nu[i] - expected;
    chi2 += diff * diff / expected;
  }

  value[0] = (long double)gsl_sf_gamma_inc_Q((double)K / 2.0, chi2 / 2.0);

  if (debug) {
    printf("Longest run: N=%ld M=%d K=%d chi2=%.6f p=%.6Lf\n", N, M, K, chi2,
           value[0]);
    printf("  nu: ");
    for (int i = 0; i <= K; i++) {
      printf("%u ", nu[i]);
    }
    printf("\n");
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
