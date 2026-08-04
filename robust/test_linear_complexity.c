#include "test_func.h"
#include <math.h>
#include <gsl/gsl_cdf.h>

/*
 * NIST-style Linear Complexity test adapted to the robust two-sample KS
 * harness. The test reads param[3] 32-bit integers, interprets the resulting
 * 32*n bits as a bitstream, splits it into blocks of size M = param[4], and
 * computes the Berlekamp-Massey linear complexity for each block. The block
 * statistics are binned exactly as in the NIST STS linear-complexity test,
 * yielding a chi-square statistic with 6 degrees of freedom and one
 * approximately uniform p-value.
 *
 * Streaming implementation: only one block of M bits and the BM workspace
 * (4 * (M+1) bytes) are held at any time. The previous version cached all
 * param[3] words to support arbitrary block alignment; this version refills
 * a 32-bit fetch buffer on demand and decodes bits sequentially into the
 * per-block array. Memory is O(M) regardless of input size, so the test
 * scales to multi-GB sweeps.
 */

#define LINEAR_COMPLEXITY_DIMENSION 1
#define LINEAR_COMPLEXITY_BINS 7
#define LINEAR_COMPLEXITY_MIN_BLOCKS 100

static const double linear_complexity_pi[LINEAR_COMPLEXITY_BINS] = {
    0.01047, 0.03125, 0.12500, 0.50000, 0.25000, 0.06250, 0.020833};

static int linear_complexity_berlekamp_massey(const unsigned char *block_bits,
                                              long m, unsigned char *b,
                                              unsigned char *c,
                                              unsigned char *p,
                                              unsigned char *t) {
  long L = 0;
  long N_ = 0;
  long m_index = -1;

  memset(b, 0, (size_t)(m + 1) * sizeof(unsigned char));
  memset(c, 0, (size_t)(m + 1) * sizeof(unsigned char));
  memset(p, 0, (size_t)(m + 1) * sizeof(unsigned char));
  memset(t, 0, (size_t)(m + 1) * sizeof(unsigned char));

  b[0] = 1;
  c[0] = 1;

  while (N_ < m) {
    int d = block_bits[N_];
    for (long i = 1; i <= L; i++) {
      d ^= (c[i] & block_bits[N_ - i]);
    }

    if (d != 0) {
      memset(p, 0, (size_t)(m + 1) * sizeof(unsigned char));
      memcpy(t, c, (size_t)(m + 1) * sizeof(unsigned char));

      for (long j = 0; j <= m; j++) {
        long idx;
        if (b[j] == 0) {
          continue;
        }
        idx = j + N_ - m_index;
        if (idx >= 0 && idx <= m) {
          p[idx] = 1;
        }
      }

      for (long i = 0; i <= m; i++) {
        c[i] ^= p[i];
      }

      if (L <= N_ / 2) {
        L = N_ + 1 - L;
        m_index = N_;
        memcpy(b, t, (size_t)(m + 1) * sizeof(unsigned char));
      }
    }

    N_++;
  }

  return (int)L;
}

static double linear_complexity_mean(long m) {
  const int sign = ((m + 1) % 2 == 0) ? 1 : -1;
  return ((double)m / 2.0) + (9.0 + (double)sign) / 36.0 -
         (((double)m / 3.0) + (2.0 / 9.0)) / pow(2.0, (double)m);
}

static double linear_complexity_statistic(int L, long m) {
  const double mean = linear_complexity_mean(m);
  const int sign = (m % 2 == 0) ? 1 : -1;
  return (double)sign * ((double)L - mean) + 2.0 / 9.0;
}

bool linear_complexity(long double *value, unsigned long *hash, PRG gen,
                       int *param, double *real_param, bool debug) {
  long n = param[3];
  long m = param[4];
  unsigned char *block_bits = NULL;
  unsigned char *b = NULL;
  unsigned char *c = NULL;
  unsigned char *p = NULL;
  unsigned char *t = NULL;
  long total_bits;
  long num_blocks;
  double nu[LINEAR_COMPLEXITY_BINS];
  double chi2 = 0.0;

  (void)real_param;

  if (param[2] != LINEAR_COMPLEXITY_DIMENSION || n < 1 || m < 2) {
    return false;
  }

  if (n > LONG_MAX / 32) {
    return false;
  }
  total_bits = 32 * n;
  num_blocks = total_bits / m;
  if (num_blocks < LINEAR_COMPLEXITY_MIN_BLOCKS) {
    return false;
  }

  block_bits = (unsigned char *)malloc((size_t)m * sizeof(unsigned char));
  b = (unsigned char *)calloc((size_t)(m + 1), sizeof(unsigned char));
  c = (unsigned char *)calloc((size_t)(m + 1), sizeof(unsigned char));
  p = (unsigned char *)calloc((size_t)(m + 1), sizeof(unsigned char));
  t = (unsigned char *)calloc((size_t)(m + 1), sizeof(unsigned char));
  if (block_bits == NULL || b == NULL || c == NULL || p == NULL ||
      t == NULL) {
    free(block_bits);
    free(b);
    free(c);
    free(p);
    free(t);
    return false;
  }

  for (int i = 0; i < LINEAR_COMPLEXITY_BINS; i++) {
    nu[i] = 0.0;
  }

  /* Streaming bit reader: refill a 32-bit fetch buffer on demand. The
   * previous version cached all n words; we need only one block at a time. */
  unsigned int bit_buf = 0;
  int bit_buf_pos = 32;
  long words_consumed = 0;

#define LC_FETCH_BIT(out_var)                                                  \
  do {                                                                         \
    if (bit_buf_pos == 32) {                                                   \
      if (!g_int32_lsb(&bit_buf, gen)) {                                       \
        free(block_bits);                                                      \
        free(b);                                                               \
        free(c);                                                               \
        free(p);                                                               \
        free(t);                                                               \
        return false;                                                          \
      }                                                                        \
      words_consumed++;                                                        \
      bit_buf_pos = 0;                                                         \
    }                                                                          \
    (out_var) = (unsigned char)((bit_buf >> bit_buf_pos) & 1U);                \
    bit_buf_pos++;                                                             \
  } while (0)

  for (long block = 0; block < num_blocks; block++) {
    double T_;
    int L;

    for (long j = 0; j < m; j++) {
      LC_FETCH_BIT(block_bits[j]);
    }

    L = linear_complexity_berlekamp_massey(block_bits, m, b, c, p, t);
    T_ = linear_complexity_statistic(L, m);

    if (T_ <= -2.5) {
      nu[0]++;
    } else if (T_ <= -1.5) {
      nu[1]++;
    } else if (T_ <= -0.5) {
      nu[2]++;
    } else if (T_ <= 0.5) {
      nu[3]++;
    } else if (T_ <= 1.5) {
      nu[4]++;
    } else if (T_ <= 2.5) {
      nu[5]++;
    } else {
      nu[6]++;
    }
  }

#undef LC_FETCH_BIT

  /* Drain the unused tail of param[3] words so the harness's "param[3]
   * integers consumed" convention is preserved. The previous version always
   * consumed exactly n words; preserve that behaviour. */
  for (long i = words_consumed; i < n; i++) {
    unsigned int discard;
    if (!g_int32_lsb(&discard, gen)) {
      free(block_bits);
      free(b);
      free(c);
      free(p);
      free(t);
      return false;
    }
  }

  for (int i = 0; i < LINEAR_COMPLEXITY_BINS; i++) {
    const double expected = (double)num_blocks * linear_complexity_pi[i];
    const double diff = nu[i] - expected;
    chi2 += diff * diff / expected;
  }

  value[0] = (long double)gsl_cdf_chisq_Q(chi2, 6.0);

  if (debug) {
    printf("Linear complexity n=%ld ints M=%ld bits blocks=%ld chi2=%.12f p-value=%.12Lf\n",
           n, m, num_blocks, chi2, value[0]);
  }

  free(block_bits);
  free(b);
  free(c);
  free(p);
  free(t);

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
