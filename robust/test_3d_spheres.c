#include "test_func.h"
#include <math.h>

/*
 * Diehard 3D Spheres Test (test #34 in this harness).
 *
 * Drop N points uniformly in the cube [0,1000]^3 and find the minimum
 * pairwise Euclidean distance d_min. Marsaglia showed that for large N the
 * scaled volume of the smallest exclusion sphere
 *
 *     U = 1 - exp(-N*(N-1)*(2*pi/3)*d_min^3 / V)
 *
 * is approximately uniform on [0,1]. Equivalently, p = 1 - exp(-d^3/mean)
 * with mean = 3*V / (2*pi*N*(N-1)). For the canonical Diehard parameters
 * N = 4000 and V = 10^9 this reduces to mean ~= 29.85.
 *
 * The harness reads param[3] = 3*N integers from the generator. The mean is
 * recomputed from the actual N rather than hard-coded so the test remains
 * correct under non-canonical sample sizes (e.g. sweeps with N != 4000).
 *
 * Distance search: a uniform 3D grid with cell side = cbrt(V/N) (so each
 * cell holds ~1 point on average) reduces the naive O(N^2) sweep to
 * O(N * 27) average comparisons. This makes the test viable for
 * multi-million-point sweeps where the original O(N^2) cost would dominate.
 * For uniform random data E[d_min] ~ 0.05 * cell_size, so the 27-neighbour
 * scan is virtually guaranteed to find the true minimum; a fall-back to
 * brute force is invoked if the grid happens to report d_min >= cell_size.
 */

#define SPHERES_DIMENSION 1
#define SPHERES_DEFAULT_N 4000
#define SPHERES_BOX_SIDE 1000.0
#define SPHERES_BOX_VOLUME (SPHERES_BOX_SIDE * SPHERES_BOX_SIDE * SPHERES_BOX_SIDE)
#define SPHERES_UINT32_SCALE 4294967296.0 /* 2^32 */

static double spheres_brute_min_sq(const double *xs, const double *ys,
                                   const double *zs, long N) {
  double min_sq = INFINITY;
  for (long i = 0; i < N - 1; i++) {
    double xi = xs[i], yi = ys[i], zi = zs[i];
    for (long j = i + 1; j < N; j++) {
      double dx = xi - xs[j];
      double dy = yi - ys[j];
      double dz = zi - zs[j];
      double d2 = dx * dx + dy * dy + dz * dz;
      if (d2 < min_sq) {
        min_sq = d2;
      }
    }
  }
  return min_sq;
}

static double spheres_grid_min_sq(const double *xs, const double *ys,
                                  const double *zs, long N, double box_side,
                                  double *out_cell_size) {
  /* cell_size such that on average ~1 point per cell. Add a small floor so
   * that for tiny N we don't end up with a single huge cell. */
  double target = pow(box_side * box_side * box_side / (double)N, 1.0 / 3.0);
  if (target < 1.0) {
    target = 1.0;
  }
  long G = (long)ceil(box_side / target);
  if (G < 2) {
    G = 2;
  }
  double cell_size = box_side / (double)G;
  *out_cell_size = cell_size;

  long total_cells = G * G * G;
  long *cell_first = (long *)malloc((size_t)total_cells * sizeof(long));
  long *cell_next = (long *)malloc((size_t)N * sizeof(long));
  if (cell_first == NULL || cell_next == NULL) {
    free(cell_first);
    free(cell_next);
    return INFINITY; /* signals fallback */
  }
  for (long i = 0; i < total_cells; i++) {
    cell_first[i] = -1;
  }

  /* Bucket each point into a cell using chained linked lists. */
  for (long i = 0; i < N; i++) {
    long cx = (long)(xs[i] / cell_size);
    long cy = (long)(ys[i] / cell_size);
    long cz = (long)(zs[i] / cell_size);
    if (cx >= G) cx = G - 1;
    if (cy >= G) cy = G - 1;
    if (cz >= G) cz = G - 1;
    if (cx < 0) cx = 0;
    if (cy < 0) cy = 0;
    if (cz < 0) cz = 0;
    long cidx = (cx * G + cy) * G + cz;
    cell_next[i] = cell_first[cidx];
    cell_first[cidx] = i;
  }

  double min_sq = INFINITY;
  for (long i = 0; i < N; i++) {
    double xi = xs[i], yi = ys[i], zi = zs[i];
    long cx = (long)(xi / cell_size);
    long cy = (long)(yi / cell_size);
    long cz = (long)(zi / cell_size);
    if (cx >= G) cx = G - 1;
    if (cy >= G) cy = G - 1;
    if (cz >= G) cz = G - 1;
    for (int dx_i = -1; dx_i <= 1; dx_i++) {
      long ncx = cx + dx_i;
      if (ncx < 0 || ncx >= G) continue;
      for (int dy_i = -1; dy_i <= 1; dy_i++) {
        long ncy = cy + dy_i;
        if (ncy < 0 || ncy >= G) continue;
        for (int dz_i = -1; dz_i <= 1; dz_i++) {
          long ncz = cz + dz_i;
          if (ncz < 0 || ncz >= G) continue;
          long cidx = (ncx * G + ncy) * G + ncz;
          for (long j = cell_first[cidx]; j != -1; j = cell_next[j]) {
            if (j <= i) continue; /* ordered comparison avoids double work */
            double dx_d = xi - xs[j];
            double dy_d = yi - ys[j];
            double dz_d = zi - zs[j];
            double d2 = dx_d * dx_d + dy_d * dy_d + dz_d * dz_d;
            if (d2 < min_sq) {
              min_sq = d2;
            }
          }
        }
      }
    }
  }

  free(cell_first);
  free(cell_next);
  return min_sq;
}

bool test_3d_spheres(long double *value, unsigned long *hash, PRG gen,
                     int *param, double *real_param, bool debug) {
  (void)real_param;
  assert(param[2] == SPHERES_DIMENSION);
  long n_ints = param[3];
  assert(n_ints >= 6);
  assert(n_ints % 3 == 0);
  long N = n_ints / 3;

  double *xs = (double *)malloc((size_t)N * sizeof(double));
  double *ys = (double *)malloc((size_t)N * sizeof(double));
  double *zs = (double *)malloc((size_t)N * sizeof(double));
  if (xs == NULL || ys == NULL || zs == NULL) {
    free(xs);
    free(ys);
    free(zs);
    return false;
  }

  for (long i = 0; i < N; i++) {
    unsigned int rx, ry, rz;
    if (!g_int32_lsb(&rx, gen) || !g_int32_lsb(&ry, gen) ||
        !g_int32_lsb(&rz, gen)) {
      free(xs);
      free(ys);
      free(zs);
      return false;
    }
    xs[i] = ((double)rx / SPHERES_UINT32_SCALE) * SPHERES_BOX_SIDE;
    ys[i] = ((double)ry / SPHERES_UINT32_SCALE) * SPHERES_BOX_SIDE;
    zs[i] = ((double)rz / SPHERES_UINT32_SCALE) * SPHERES_BOX_SIDE;
  }

  double min_sq;
  double cell_size = 0.0;
  if (N < 8) {
    /* Below ~8 points the grid bookkeeping is silly; fall straight back. */
    min_sq = spheres_brute_min_sq(xs, ys, zs, N);
  } else {
    min_sq = spheres_grid_min_sq(xs, ys, zs, N, SPHERES_BOX_SIDE, &cell_size);
    /* Defensive fall-back: if grid pass found nothing useful or reports a
     * minimum not smaller than the cell side (rare for uniform data), redo
     * with the brute-force sweep so we never return a wrong answer. */
    if (!isfinite(min_sq) ||
        (cell_size > 0.0 && min_sq >= cell_size * cell_size)) {
      if (debug) {
        printf("3D spheres: grid result min_sq=%.6f >= cell^2=%.6f, "
               "falling back to brute force\n",
               min_sq, cell_size * cell_size);
      }
      min_sq = spheres_brute_min_sq(xs, ys, zs, N);
    }
  }

  double d_min = sqrt(min_sq);
  double d_cubed = d_min * d_min * d_min;
  double mean = 3.0 * SPHERES_BOX_VOLUME /
                (2.0 * M_PI * (double)N * (double)(N - 1));
  double p_value = -expm1(-d_cubed / mean);
  if (p_value < 0.0) {
    p_value = 0.0;
  } else if (p_value > 1.0) {
    p_value = 1.0;
  }
  value[0] = (long double)p_value;

  if (debug) {
    printf("3D spheres N=%ld d_min=%.6f d^3=%.6f mean=%.6f cell=%.4f "
           "p=%.6Lf\n",
           N, d_min, d_cubed, mean, cell_size, value[0]);
  }

  free(xs);
  free(ys);
  free(zs);

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
