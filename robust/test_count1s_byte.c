#include "test_func.h"
#include <gsl/gsl_cdf.h>
#include <gsl/gsl_math.h>

/*
 * Diehard Count the 1s Test (Specific Byte)
 *
 * Similar to the stream test, but instead of successive bytes,
 * it selects one of the four bytes (0, 8, 16, or 24) from each
 * 32-bit integer.
 */

#define NUM_WORDS 256000
#define ALPHABET_SIZE 5
#define WORD_LEN 5
#define NUM_CATEGORIES  3125 // 5^5
#define NUM_PREFIX_CATS  625 // 5^4 (4-letter prefixes)
#define NUM_POSITIONS 4

static int weight_to_letter[9] = {0, 0, 0, 1, 2, 3, 4, 4, 4};
static double letter_prob[5] = {37.0 / 256.0, 56.0 / 256.0, 70.0 / 256.0,
                                56.0 / 256.0, 37.0 / 256.0};

static int byte_weights[256];
static bool weights_init = false;

static void init_weights() {
  for (int i = 0; i < 256; i++) {
    int w = 0;
    int n = i;
    while (n) {
      w += (n & 1);
      n >>= 1;
    }
    byte_weights[i] = w;
  }
  weights_init = true;
}

bool count1s_byte(long double *value, unsigned long *hash, PRG gen, int *param,
                  double *real_param, bool debug) {
  if (!weights_init)
    init_weights();

  assert(param[2] == NUM_POSITIONS); // Returns 4 values
  assert(param[3] == 0);             // fixed-size test; -n is not used

  long *counts[NUM_POSITIONS];
  for (int p = 0; p < NUM_POSITIONS; p++) {
    counts[p] = (long *)calloc(NUM_CATEGORIES, sizeof(long));
    if (!counts[p]) {
      for (int i = 0; i < p; i++)
        free(counts[i]);
      return false;
    }
  }

  int word[NUM_POSITIONS][5];
  // Warm up
  for (int i = 0; i < 4; i++) {
    unsigned int val;
    if (!g_int32_lsb(&val, gen)) {
      for (int p = 0; p < NUM_POSITIONS; p++)
        free(counts[p]);
      return false;
    }
    for (int p = 0; p < NUM_POSITIONS; p++) {
      byt b = (val >> (p * 8)) & 0xFF;
      word[p][i] = weight_to_letter[byte_weights[b]];
    }
  }

  for (long i = 0; i < NUM_WORDS; i++) {
    unsigned int val;
    if (!g_int32_lsb(&val, gen)) {
      for (int p = 0; p < NUM_POSITIONS; p++)
        free(counts[p]);
      return false;
    }

    for (int p = 0; p < NUM_POSITIONS; p++) {
      byt b = (val >> (p * 8)) & 0xFF;
      word[p][4] = weight_to_letter[byte_weights[b]];

      int idx = 0;
      for (int j = 0; j < 5; j++) {
        idx = idx * ALPHABET_SIZE + word[p][j];
      }
      counts[p][idx]++;

      for (int j = 0; j < 4; j++) {
        word[p][j] = word[p][j + 1];
      }
    }
  }

  for (int p = 0; p < NUM_POSITIONS; p++) {
    // Q5: naive Pearson chi-square on 5-letter word counts.
    long double Q5 = 0;
    for (int i = 0; i < NUM_CATEGORIES; i++) {
      double prob = 1.0;
      int temp = i;
      for (int j = 0; j < WORD_LEN; j++) {
        prob *= letter_prob[temp % ALPHABET_SIZE];
        temp /= ALPHABET_SIZE;
      }
      double expected = (double)NUM_WORDS * prob;
      double diff = (double)counts[p][i] - expected;
      Q5 += (diff * diff) / expected;
    }

    // Q4: naive Pearson chi-square on 4-letter prefix counts.
    // Marsaglia's correction: Q5 - Q4 ~ chi-square(5^5 - 5^4 = 2500).
    long count4[NUM_PREFIX_CATS];
    for (int i = 0; i < NUM_PREFIX_CATS; i++)
      count4[i] = 0;
    for (int i = 0; i < NUM_CATEGORIES; i++)
      count4[i / ALPHABET_SIZE] += counts[p][i];

    long double Q4 = 0;
    for (int i = 0; i < NUM_PREFIX_CATS; i++) {
      double prob = 1.0;
      int temp = i;
      for (int j = 0; j < WORD_LEN - 1; j++) {
        prob *= letter_prob[temp % ALPHABET_SIZE];
        temp /= ALPHABET_SIZE;
      }
      double expected = (double)NUM_WORDS * prob;
      double diff = (double)count4[i] - expected;
      Q4 += (diff * diff) / expected;
    }

    int df = NUM_CATEGORIES - NUM_PREFIX_CATS; // = 2500
    value[p] = (long double)gsl_cdf_chisq_Q((double)(Q5 - Q4), (double)df);

    if (debug) {
      printf("byte pos %d: Q5=%.4Lf  Q4=%.4Lf  Q5-Q4=%.4Lf  p-value=%.8Lf\n",
             p, Q5, Q4, Q5 - Q4, value[p]);
    }

    free(counts[p]);
  }

  unsigned int h1, h2;
  if (!g_int32_lsb(&h1, gen) || !g_int32_lsb(&h2, gen))
    return false;
  *hash = (((unsigned long)h2) << 32) + (unsigned long)h1;

  return true;
}
