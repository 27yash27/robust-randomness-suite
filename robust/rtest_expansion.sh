#!/bin/sh
# rtest_expansion.sh  GENERATOR  ETALON
#
# Runs the twenty expansion tests (numbers 22-41) in robust XOR mode, at the
# settings in scripts/robust_test_catalog.py. This is the counterpart to the
# upstream rtest1m.sh ... rtest10g.sh batteries, which cover the original tests
# (roughly 0-16) only.
#
# Both GENERATOR and ETALON must be binary files of raw bytes, and BOTH must be
# large enough to feed every test: XOR mode consumes the etalon at the same rate
# as the generator, and the heavy tests (DNA, OPERM5, Random Excursions) each
# use tens of MB. Use files of at least ~100 MB; 1 GB gives a clean full pass.
# The small data/data.e.32 shipped with the repo is only adequate for the
# lightest tests. A quick way to make suitable files:
#     head -c 200000000 /dev/urandom > etalon.bin
#
# Each test uses the most data-frugal sample size in the catalog. Raise -p/-q
# for more resolution, or use scripts/run_maximal_p_sweep.py to sweep a ceiling.
#
# Results are appended to  GENERATOR.expansion

if [ $# -ne 2 ]; then
  echo "usage: $0 GENERATOR ETALON   (both large binary files; see header)" >&2
  exit 1
fi

RTEST="$(dirname "$0")/rtest"
if [ ! -x "$RTEST" ]; then
  echo "rtest binary not found at $RTEST -- run 'make' in this directory first." >&2
  exit 1
fi

GEN="$1"; ETAL="$2"; OUT="$1.expansion"
: > "$OUT"

run() {  # label  test  dim  n  p  [modifier]
  echo "" >> "$OUT"
  echo "== t$2  $1 ==" >> "$OUT"
  if [ -n "$6" ]; then
    echo "$RTEST -x -f $GEN -e $ETAL -p $5 -q $5 -d $3 -n $4 -t $2 -m $6 -r 1" >> "$OUT"
    "$RTEST" -x -f "$GEN" -e "$ETAL" -p "$5" -q "$5" -d "$3" -n "$4" -t "$2" -m "$6" -r 1 >> "$OUT" 2>&1
  else
    echo "$RTEST -x -f $GEN -e $ETAL -p $5 -q $5 -d $3 -n $4 -t $2 -r 1" >> "$OUT"
    "$RTEST" -x -f "$GEN" -e "$ETAL" -p "$5" -q "$5" -d "$3" -n "$4" -t "$2" -r 1 >> "$OUT" 2>&1
  fi
}

#    label                              t   dim   n        p    [mod]
run "DNA"                               22  31    2097161  3
run "Count-the-1s (stream)"            23  1     0        100
run "Count-the-1s (bytes)"             24  4     0        10
run "Parking Lot"                      25  1     24000    10
run "Squeeze"                          26  1     0        2
run "OPERM5"                           27  1     1000000  5
run "Craps"                            28  2     0        5
run "DAB DCT"                          29  1     4096     5
run "DAB Filtering"                    30  1     4096     5
run "Linear Complexity"                31  1     4096     5    500
run "Random Excursions"                32  8     1000000  5
run "Random Excursions Variant"        33  18    1000000  5
run "3D Spheres"                       34  1     12000    5
run "Marsaglia-Tsang GCD"              35  1     50000    5
run "Nonperiodic Template Matching"    36  148   2000     5
run "Runs"                             37  1     100000   5
run "Longest Run of Ones"              38  1     100000   5
run "Cumulative Sums"                  39  2     100000   5
run "Approximate Entropy"              40  1     100000   5
run "Maurer's Universal"               41  1     100000   5

echo "" >> "$OUT"
echo "done -> $OUT"
