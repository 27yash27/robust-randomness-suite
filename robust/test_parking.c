#include "test_func.h"
#include <gsl/gsl_cdf.h>
#include <gsl/gsl_math.h>

/*
 * Diehard Parking Lot Test
 *
 * 1. Simulates parking 12,000 "cars" in a 100x100 square.
 * 2. A car is parked if it does not overlap with any previously parked car.
 * 3. Overlap condition used by this implementation:
 *    |x_i - x_j| < 1 AND |y_i - y_j| < 1 (axis-aligned unit-square exclusion).
 * 4. Successes K should be normally distributed:
 *    Mean = 3523.0, Sigma = 21.9.
 * 5. Reads 2 * NUM_ATTEMPTS = 24000 32-bit integers.
 */

#define NUM_ATTEMPTS 12000
#define GRID_SIZE 100.0
#define MEAN 3523.0
#define SIGMA 21.9
#define UINT32_SCALE 4294967296.0 // 2^32, maps integers to [0,1)

typedef struct {
  double x;
  double y;
} Car;

bool parking(long double *value, unsigned long *hash, PRG gen, int *param,
             double *real_param, bool debug) {
  assert(param[2] == 1);                       // Returns one value
  assert(param[3] == NUM_ATTEMPTS * 2);        // 2 integers per attempt

  Car *parked_cars = (Car *)malloc(NUM_ATTEMPTS * sizeof(Car));
  if (!parked_cars)
    return false;

  int num_parked = 0;

  for (int i = 0; i < NUM_ATTEMPTS; i++) {
    unsigned int rx, ry;
    if (!g_int32_lsb(&rx, gen) || !g_int32_lsb(&ry, gen)) {
      free(parked_cars);
      return false;
    }

    double x = ((double)rx / UINT32_SCALE) * GRID_SIZE;
    double y = ((double)ry / UINT32_SCALE) * GRID_SIZE;

    bool overlap = false;
    for (int j = 0; j < num_parked; j++) {
      if (fabs(x - parked_cars[j].x) < 1.0 &&
          fabs(y - parked_cars[j].y) < 1.0) {
        overlap = true;
        break;
      }
    }

    if (!overlap) {
      parked_cars[num_parked].x = x;
      parked_cars[num_parked].y = y;
      num_parked++;
    }
  }

  *value =
      (long double)gsl_cdf_ugaussian_P(((double)num_parked - MEAN) / SIGMA);

  if (debug) {
    printf("Parked cars: %d, p-value: %10.8Lf\n", num_parked, *value);
  }

  unsigned int h1, h2;
  if (!g_int32_lsb(&h1, gen) || !g_int32_lsb(&h2, gen)) {
    free(parked_cars);
    return false;
  }
  *hash = (((unsigned long)h2) << 32) + (unsigned long)h1;

  free(parked_cars);
  return true;
}
