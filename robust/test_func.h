#include "generators.h"
#include <gsl/gsl_math.h>
#include <gsl/gsl_cdf.h>
#include <gsl/gsl_randist.h>
#include <gsl/gsl_sf.h>
#include <gsl/gsl_errno.h>
#include <gsl/gsl_fft_complex.h>
#include <gsl/gsl_sort_uint.h>
#include <gsl/gsl_sort_int.h>
#include "../kolmogorov-smirnov/k1smirnov.h"

typedef bool test_func(long double *value, unsigned long *hash, PRG gen, int *param, double *real_param, bool debug);
//This is the type definition for possible test functions 
// Each of them determines a robust test 
// returns true if no errors; in this case 
// value[0..]= function values; 
// hash[0..]= additional hash values used in case of ties; 
// gen is the generator to be called;
// param[2...] are integer parameters determining the behavior
// of the function. Note that param[0] and param[1] are reserved 
// for the sample size and should not be used
// dimension=param[2] is the dimension of the output (input parameter
// that determines how many position is value[] and hash[] are filled) 
// param[3] is the amount of used data in some test-depending sense (if applicable)
// param[4..] have test-dependent meaning
// real_param[0..] also have test-dependent meaning
// debug causes printing additional information

typedef struct test_function
{
  test_func *reference;
  const char* description; // used for short messages
} test_function;

// Here the forward definitions of all test functions should be provided

test_func all_bytes;       
//0 dimension 1 size=auto [coupon collector time for bytes]

test_func all_16;          
//1 dimension 1 size=auto [coupon collector time for 16 ints]

test_func dummy_dimension;  
//2
// just for testing

test_func sts_serial;      
//3 dimension = a multiple of 3, at most 93 size number of ints processed [sts_serial.c]

test_func opso;  
//4 dimension = 23, size= 2097153 [diehard_opso.c]

test_func oqso;  
//5 dimension = 28, size= 2097155 [diehard_oqso.c]

test_func bytedistrib;      
//6 dimension = 1, uses 3*dize nints [DAB Byte Distribution Test, dab_bytedistrib.c]

test_func knuth_runs;    
//7 dimension = 2, uses size nints (>=10000 recommended) [diehard_runs.c]

test_func osums;           
//8 dimension = 1, uses 2*size-1 nints [diehard_sums.c, rejected as incorrect by dieharder]

test_func ent_8_16;
//9 dimension = 4 (ent8, chi8, ent16, chi16), uses size nints [ent ubuntu utility]

test_func fftest;
//10 dimension = 1 (number of peaks converted assuming normal approximation) [NIST FFT test]

test_func rank32x32;
//11 dimension =1 (chi-square value for the rank distribution of param[3] matrices 32*32 from 32*param[3] ints

test_func rank6x8;
//12 dimension =25 (chi-square value for the rank distribution of 6*8 matrices obtained 
//   in 25 positions from 6n random ints (25*param[3] matrices from 6*param[3] ints)

test_func bitstream_o;
//13 overlapped bitstream test; dimension =1, param[3] should be 2^21+19 = 2097171

test_func bitstream_n;
//14 non-overlapped bitstream test; dimension =1, param[3] should be 20*2^21 = 41943040

test_func lz_split;
//15 dimension = 1; recommended param[3]=31250; in this case conversion to uniform distibution happens

test_func birthdays;
//16 diehard/dieharder birthday test

test_func mindist2d;
//17 minimal 2d distance

test_func spectral;
//18 spectral test

test_func ksone;
//19 one-sample Kolmogorov-Smirnov test\

test_func monobit;
//20 dimension = 1,  uses 32*param[3] bits 

test_func nist_block;
//21 dimension = 1, paran[3]=number of blocks, param[4]=block size -- NIST section 2.2, 3.2

test_func dna;
// 22 dimension = 31, uses 2^21+9 ints [Diehard DNA test]

test_func count1s_stream;
// 23 dimension = 1, [Diehard Count the 1s in a stream of bytes]

test_func count1s_byte;
// 24 dimension = 4, [Diehard Count the 1s for chosen bytes]

test_func parking;
// 25 dimension = 1, [Diehard Parking lot test]

test_func squeeze;
// 26 dimension = 1, [Diehard Squeeze test]

test_func operm5;
// 27 dimension = 1, [Diehard OPERM5 overlapping 5-permutations test]

test_func craps;
// 28 dimension = 2, [Diehard Craps test]

test_func dab_dct;
// 29 dimension = 1, [Dieharder DAB DCT test, adapted]

test_func dab_filtering;
// 30 dimension = 1, [Dieharder DAB filtering test, adapted]

test_func linear_complexity;
// 31 dimension = 1, [Linear Complexity test]

test_func random_excursions;
// 32 dimension = 8, [NIST Random Excursions]

test_func random_excursions_variant;
// 33 dimension = 18, [NIST Random Excursions Variant]

test_func test_3d_spheres;
// 34 dimension = 1, [Diehard 3D Spheres]

test_func gcd;
// 35 dimension = 1, [Diehard Marsaglia and Tsang GCD]

test_func nonperiodic;
// 36 dimension = 148, [NIST Nonperiodic Template Matching, all 148 templates]

test_func runs_nist;
// 37 dimension = 1, [NIST Runs test (bit-level transitions)]

test_func longest_run;
// 38 dimension = 1, [NIST Longest Run of Ones in a Block]

test_func cusum;
// 39 dimension = 2, [NIST Cumulative Sums (forward + reverse)]

test_func approximate_entropy;
// 40 dimension = 1, [NIST Approximate Entropy], param[4] = m (default 10)

test_func universal;
// 41 dimension = 1, [Maurer's Universal Statistical Test], n>=387840 bits
