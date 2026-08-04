#include "test_func.h"
#include <gsl/gsl_math.h>

/*
 * Diehard DNA Test
 *
 * This test considers 10-letter words from an alphabet of four "letters" (C, G,
 * A, T). Each letter is determined by two designated bits from the sequence of
 * random integers being tested.
 *
 * The DNA test examines a string of 2^21 overlapping 10-letter words (from 2^21
 * + 9 32-bit integers).
 *
 * There are 2^20 possible unique words. The number of missing words should be
 * normally distributed with mean 141,909 and sigma 339.
 */

#define ALPHABET_SIZE 4
#define WORD_LEN 10
#define NUM_POSITIONS 31 // 32 - 2 + 1 = 31 possible positions for 2 bits
#define BYTES_PER_WORD                                                         \
  4 // upper rounding of NUM_POSITIONS / 8 = 3.875 -> 4 bytes
#define NINTS (1 << 21) + 9
#define MEAN 141909.33
#define SIGMA 339.1578

bool dna(long double *value, unsigned long *hash, PRG gen, int *param,
         double *real_param, bool debug) {
  assert(param[2] == NUM_POSITIONS); // dimension is 31
  assert(param[3] == NINTS);         // number of read integers

  byt *bitset;
  // bitset size: (2^20 words) * (BYTES_PER_WORD bytes per word)
  // Each word has 31 bits allocated (one per starting position)
  bitset = (byt *)malloc((1 << 20) * BYTES_PER_WORD);
  if (bitset == NULL)
    return (false);

  for (long i = 0; i < (1 << 20) * BYTES_PER_WORD; i++) {
    bitset[i] = (byt)0;
  }

#define ADD_WORD(word, pos)                                                    \
  bitset[(word) * BYTES_PER_WORD + ((pos) / 8)] |= (byt)(1 << ((pos) % 8))
#define IS_WORD(word, pos)                                                     \
  ((bitset[(word) * BYTES_PER_WORD + ((pos) / 8)] &                            \
    ((byt)(1 << ((pos) % 8)))) != 0)

  unsigned int buffer[10];
  // initial fill of the buffer
  for (int i = 0; i < 9; i++) {
    if (!g_int32_lsb(&buffer[i], gen)) {
      free(bitset);
      return (false);
    }
  }

  for (long i = 0; i < (1 << 21); i++) {
    // Read the 10th integer
    if (!g_int32_lsb(&buffer[9], gen)) {
      free(bitset);
      return (false);
    }

    // Process 31 positions
    for (int pos = 0; pos < NUM_POSITIONS; pos++) {
      unsigned int word = 0;
      for (int k = 0; k < 10; k++) {
        // Extract 2 bits at position 'pos'
        unsigned int bits = (buffer[k] >> pos) & 0x3;
        word = (word << 2) | bits;
      }
      ADD_WORD(word, pos);
    }

    // Shift buffer
    for (int k = 0; k < 9; k++) {
      buffer[k] = buffer[k + 1];
    }
  }

  // Count missing words for each position
  long missing_counts[NUM_POSITIONS];
  for (int p = 0; p < NUM_POSITIONS; p++)
    missing_counts[p] = 0;

  for (int w = 0; w < (1 << 20); w++) {
    for (int p = 0; p < NUM_POSITIONS; p++) {
      if (!IS_WORD(w, p)) {
        missing_counts[p]++;
      }
    }
  }

  // Calculate p-values
  for (int p = 0; p < NUM_POSITIONS; p++) {
    double raw = (double)missing_counts[p];
    double normalized = gsl_cdf_ugaussian_P((raw - MEAN) / SIGMA);
    value[p] = (long double)normalized;
  }

  // Generate hash for tie-breaking
  unsigned int h1, h2;
  if ((!g_int32_lsb(&h1, gen)) || (!g_int32_lsb(&h2, gen))) {
    free(bitset);
    return (false);
  }
  *hash = (((unsigned long)h2) << 32) + ((unsigned long)h1);

  if (debug) {
    printf("DNA Test Results (p-values):\n");
    for (int p = 0; p < NUM_POSITIONS; p++) {
      printf("%10.5Lf ", value[p]);
      if ((p + 1) % 5 == 0)
        printf("\n");
    }
    printf("\n");
  }

  free(bitset);
  return (true);
}
