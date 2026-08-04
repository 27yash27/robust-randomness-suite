#include "test_func.h"
#include <gsl/gsl_cdf.h>
#include <gsl/gsl_math.h>

/*
 * Diehard Count the 1s Test (Stream of Bytes)
 *
 * 1. Read successive bytes from the stream.
 * 2. Count the number of 1s in each byte (weight).
 * 3. Map weights to 5 letters:
 *    0, 1, 2 -> A (Prob 37/256)
 *    3       -> B (Prob 56/256)
 *    4       -> C (Prob 70/256)
 *    5       -> D (Prob 56/256)
 *    6, 7, 8 -> E (Prob 37/256)
 * 4. Form overlapping 5-letter words.
 * 5. There are 5^5 = 3125 possible words.
 * 6. Use 256,000 words.
 * 7. Apply chi-square test for overlapping words.
 *    For overlapping monkey tests, we use the formula from Marsaglia.
 */

#define NUM_WORDS 256000
#define ALPHABET_SIZE 5
#define WORD_LEN 5
#define NUM_CATEGORIES 3125  // 5^5
#define NUM_PREFIX_CATS  625 // 5^4 (4-letter prefixes)

// Mapping of byte weight to letter index (0-4)
static int weight_to_letter[9] = {0, 0, 0, 1, 2, 3, 4, 4, 4};
static double letter_prob[5] = {37.0 / 256.0, 56.0 / 256.0, 70.0 / 256.0,
                                56.0 / 256.0, 37.0 / 256.0};

// Precomputed weight for each byte (0-255)
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

bool count1s_stream(long double *value, unsigned long *hash, PRG gen,
                    int *param, double *real_param, bool debug) {
  if (!weights_init)
    init_weights();

  assert(param[2] == 1); // Returns one value
  assert(param[3] == 0); // fixed-size test; -n is not used

  long *counts = (long *)calloc(NUM_CATEGORIES, sizeof(long));
  if (!counts)
    return false;

  int word[5];
  // Warm up the word
  for (int i = 0; i < 4; i++) {
    byt b;
    if (!g_byte(&b, gen)) {
      free(counts);
      return false;
    }
    word[i] = weight_to_letter[byte_weights[b]];
  }

  for (long i = 0; i < NUM_WORDS; i++) {
    byt b;
    if (!g_byte(&b, gen)) {
      free(counts);
      return false;
    }
    word[4] = weight_to_letter[byte_weights[b]];

    // Calculate word index (base 5)
    int idx = 0;
    for (int j = 0; j < 5; j++) {
      idx = idx * ALPHABET_SIZE + word[j];
    }
    counts[idx]++;

    // Shift word
    for (int j = 0; j < 4; j++) {
      word[j] = word[j + 1];
    }
  }

  // Compute Q5: naive Pearson chi-square on 5-letter word counts.
  long double Q5 = 0;
  for (int i = 0; i < NUM_CATEGORIES; i++) {
    double p = 1.0;
    int temp = i;
    for (int j = 0; j < WORD_LEN; j++) {
      p *= letter_prob[temp % ALPHABET_SIZE];
      temp /= ALPHABET_SIZE;
    }
    double expected = (double)NUM_WORDS * p;
    double diff = (double)counts[i] - expected;
    Q5 += (diff * diff) / expected;
  }

  // Compute Q4: naive Pearson chi-square on 4-letter prefix counts.
  // The 4-letter prefix of word i has index i / ALPHABET_SIZE.
  // Marsaglia's correction: Q5 - Q4 ~ chi-square(5^5 - 5^4 = 2500),
  // accounting for the overlap dependence between successive 5-letter words.
  long count4[NUM_PREFIX_CATS];
  for (int i = 0; i < NUM_PREFIX_CATS; i++)
    count4[i] = 0;
  for (int i = 0; i < NUM_CATEGORIES; i++)
    count4[i / ALPHABET_SIZE] += counts[i];

  long double Q4 = 0;
  for (int i = 0; i < NUM_PREFIX_CATS; i++) {
    double p = 1.0;
    int temp = i;
    for (int j = 0; j < WORD_LEN - 1; j++) {
      p *= letter_prob[temp % ALPHABET_SIZE];
      temp /= ALPHABET_SIZE;
    }
    double expected = (double)NUM_WORDS * p;
    double diff = (double)count4[i] - expected;
    Q4 += (diff * diff) / expected;
  }

  int df = NUM_CATEGORIES - NUM_PREFIX_CATS; // = 2500
  *value = (long double)gsl_cdf_chisq_Q((double)(Q5 - Q4), (double)df);

  if (debug) {
    printf("Q5=%.4Lf  Q4=%.4Lf  Q5-Q4=%.4Lf  df=%d  p-value=%.8Lf\n",
           Q5, Q4, Q5 - Q4, df, *value);
  }

  // Hash
  unsigned int h1, h2;
  if (!g_int32_lsb(&h1, gen) || !g_int32_lsb(&h2, gen)) {
    free(counts);
    return false;
  }
  *hash = (((unsigned long)h2) << 32) + (unsigned long)h1;

  free(counts);
  return true;
}
