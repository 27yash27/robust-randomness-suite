#include "test_func.h"
#include <gsl/gsl_sf.h>
#include <math.h>

/*
 * NIST 800-22 Nonperiodic (Aperiodic) Template Matching Test (test #36 in
 * this harness).
 *
 * The 32*param[3] bit stream is split into N = 8 equal blocks of M bits.
 * For each of 148 length-9 non-periodic templates from NIST's reference
 * `templates/template9` file, count W_j(t) = number of non-overlapping
 * occurrences of template t in block j. Under H0 each template has
 *
 *     mu     = (M - m + 1) / 2^m
 *     sigma2 = M * (1/2^m - (2m-1)/2^(2m))
 *
 * and the chi-square statistic chi2(t) = sum_j (W_j(t) - mu)^2 / sigma2 is
 * approximately chi-square with N degrees of freedom. The test reports the
 * 148-tuple of upper-tail p-values, one per template (NIST SP 800-22
 * Sec. 2.7).
 *
 * Streaming implementation: a single shared 9-bit sliding window scans each
 * block once, without buffering the bitstream. The 148 templates are distinct
 * 9-bit values, so at most one of them can equal the window; a 512-entry
 * reverse lookup answers "which template is this?" in one array read instead
 * of a 148-way scan at every bit. The non-overlapping rule is then enforced
 * per template in O(1) through next_ok[] below. Per-block work is O(M),
 * about 1e6 operations at M = 1e6 where a per-bit scan over all templates
 * costs ~1.5e8.
 *
 * Templates are embedded in the source (verbatim transcription of
 * sts-2.1.2/templates/template9) so the test has no runtime file I/O and
 * does not depend on the working directory.
 */

#define NONP_DIMENSION 148
#define NONP_TEMPLATE_LEN 9
#define NONP_NUM_BLOCKS 8
#define NONP_NUM_TEMPLATES 148
#define NONP_TEMPLATE_MASK ((1U << NONP_TEMPLATE_LEN) - 1U)

/* The 148 length-9 templates from NIST sts-2.1.2/templates/template9.
 * Each template is encoded with the oldest bit at the highest position so
 * comparisons against the sliding window are direct equality checks. */
static const unsigned short nonp_templates[NONP_NUM_TEMPLATES] = {
    0x001, 0x003, 0x005, 0x007, 0x009, 0x00b, 0x00d, 0x00f,
    0x011, 0x013, 0x015, 0x017, 0x019, 0x01b, 0x01d, 0x01f,
    0x023, 0x025, 0x027, 0x029, 0x02b, 0x02d, 0x02f, 0x033,
    0x035, 0x037, 0x039, 0x03b, 0x03d, 0x03f, 0x043, 0x045,
    0x047, 0x04b, 0x04d, 0x04f, 0x053, 0x055, 0x057, 0x05b,
    0x05d, 0x05f, 0x065, 0x067, 0x06b, 0x06d, 0x06f, 0x075,
    0x077, 0x07b, 0x07d, 0x07f, 0x083, 0x087, 0x08b, 0x08f,
    0x093, 0x097, 0x09b, 0x09f, 0x0a3, 0x0a7, 0x0ab, 0x0af,
    0x0b3, 0x0b7, 0x0bb, 0x0bf, 0x0c7, 0x0cf, 0x0d7, 0x0df,
    0x0ef, 0x0ff, 0x100, 0x110, 0x120, 0x128, 0x130, 0x138,
    0x140, 0x144, 0x148, 0x14c, 0x150, 0x154, 0x158, 0x15c,
    0x160, 0x164, 0x168, 0x16c, 0x170, 0x174, 0x178, 0x17c,
    0x180, 0x182, 0x184, 0x188, 0x18a, 0x190, 0x192, 0x194,
    0x198, 0x19a, 0x1a0, 0x1a2, 0x1a4, 0x1a8, 0x1aa, 0x1ac,
    0x1b0, 0x1b2, 0x1b4, 0x1b8, 0x1ba, 0x1bc, 0x1c0, 0x1c2,
    0x1c4, 0x1c6, 0x1c8, 0x1ca, 0x1cc, 0x1d0, 0x1d2, 0x1d4,
    0x1d6, 0x1d8, 0x1da, 0x1dc, 0x1e0, 0x1e2, 0x1e4, 0x1e6,
    0x1e8, 0x1ea, 0x1ec, 0x1ee, 0x1f0, 0x1f2, 0x1f4, 0x1f6,
    0x1f8, 0x1fa, 0x1fc, 0x1fe
};

/* Reverse of nonp_templates: window value -> template index, or -1 for a
 * window that is not a template. The templates are 148 distinct values in
 * [0, 512), so this is a faithful inverse and at most one template can match
 * any given window. Built once on first use. */
#define NONP_WINDOW_VALUES (1 << NONP_TEMPLATE_LEN)
static short nonp_template_of_window[NONP_WINDOW_VALUES];
static bool nonp_lookup_ready = false;

static void nonp_build_lookup(void) {
  if (nonp_lookup_ready) {
    return;
  }
  for (int w = 0; w < NONP_WINDOW_VALUES; w++) {
    nonp_template_of_window[w] = -1;
  }
  for (int t = 0; t < NONP_NUM_TEMPLATES; t++) {
    /* A repeated template would make the lookup lossy and silently drop
     * counts, so assert distinctness rather than trust the transcription. */
    assert(nonp_template_of_window[nonp_templates[t]] == -1);
    nonp_template_of_window[nonp_templates[t]] = (short)t;
  }
  nonp_lookup_ready = true;
}

bool nonperiodic(long double *value, unsigned long *hash, PRG gen, int *param,
                 double *real_param, bool debug) {
  (void)real_param;
  assert(param[2] == NONP_DIMENSION);
  long n_ints = param[3];
  assert(n_ints >= 1);
  long n = 32L * n_ints;
  long M = n / NONP_NUM_BLOCKS;
  if (M < NONP_TEMPLATE_LEN + 1) {
    return false;
  }
  nonp_build_lookup();

  double m_d = (double)NONP_TEMPLATE_LEN;
  double mu = ((double)M - m_d + 1.0) / pow(2.0, m_d);
  double var = (double)M * (1.0 / pow(2.0, m_d) -
                            (2.0 * m_d - 1.0) / pow(2.0, 2.0 * m_d));
  if (var <= 0.0) {
    return false;
  }

  /* Per-template chi-square accumulators across the N blocks. */
  double chi2[NONP_NUM_TEMPLATES] = {0.0};
  /* Per-block, per-template state (reset at the start of each block). */
  long W[NONP_NUM_TEMPLATES];
  /* First position at which template t may match again, which enforces the
   * non-overlapping rule independently per template in O(1) per match rather
   * than O(templates) per bit. */
  long next_ok[NONP_NUM_TEMPLATES];

  /* 32-bit fetch buffer drives the bit stream. */
  unsigned int bit_buf = 0;
  int bit_buf_pos = 32;

  for (int blk = 0; blk < NONP_NUM_BLOCKS; blk++) {
    for (int t = 0; t < NONP_NUM_TEMPLATES; t++) {
      W[t] = 0;
      /* the window is complete at position NONP_TEMPLATE_LEN-1, which is the
       * earliest any template can match */
      next_ok[t] = NONP_TEMPLATE_LEN - 1;
    }
    unsigned int window = 0U;
    int bits_in_window = 0;

    for (long pos = 0; pos < M; pos++) {
      if (bit_buf_pos == 32) {
        if (!g_int32_lsb(&bit_buf, gen)) {
          return false;
        }
        bit_buf_pos = 0;
      }
      unsigned int bit = (bit_buf >> bit_buf_pos) & 1U;
      bit_buf_pos++;
      window = ((window << 1) | bit) & NONP_TEMPLATE_MASK;
      if (bits_in_window < NONP_TEMPLATE_LEN) {
        bits_in_window++;
      }
      /* A match needs a fully populated window as well as enough fresh bits
       * for this template. The two conditions differ early in a block and
       * after any match, so we can't collapse them.
       *
       * Freshness is held as the position of each template's last match rather
       * than a counter advanced on every bit: the counter form needed a
       * 148-way loop per bit. next_ok[t] is the first position at which
       * template t may match again, and it counts every consumed bit including
       * those that fill the initial window, so position 0 of each block is
       * eligible. */
      if (bits_in_window < NONP_TEMPLATE_LEN) {
        continue;
      }
      /* At most one template equals this window, so the lookup replaces the
       * scan over all 148 without changing which matches are counted. */
      int t = nonp_template_of_window[window];
      if (t >= 0 && pos >= next_ok[t]) {
        W[t]++;
        /* non-overlapping: NONP_TEMPLATE_LEN fresh bits before the next */
        next_ok[t] = pos + NONP_TEMPLATE_LEN;
      }
    }

    for (int t = 0; t < NONP_NUM_TEMPLATES; t++) {
      double diff = (double)W[t] - mu;
      chi2[t] += diff * diff / var;
    }

    if (debug && blk == 0) {
      printf("Nonperiodic block %d: W[0..3]= %ld %ld %ld %ld (mu=%.4f)\n", blk,
             W[0], W[1], W[2], W[3], mu);
    }
  }

  /* M*N == 32*n_ints, so all param[3] words are consumed. */

  for (int t = 0; t < NONP_NUM_TEMPLATES; t++) {
    value[t] = (long double)gsl_sf_gamma_inc_Q(
        (double)NONP_NUM_BLOCKS / 2.0, chi2[t] / 2.0);
  }

  if (debug) {
    long double pmin = 1.0L, pmax = 0.0L;
    for (int t = 0; t < NONP_NUM_TEMPLATES; t++) {
      if (value[t] < pmin) pmin = value[t];
      if (value[t] > pmax) pmax = value[t];
    }
    printf("Nonperiodic: 148 templates p-min=%.6Lf p-max=%.6Lf\n", pmin, pmax);
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
