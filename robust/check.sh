#!/bin/sh
# check.sh -- smoke test for a fresh build. Run it as "make check".
#
# Uses only files committed to this repository, so every run is byte-for-byte
# repeatable and the expected values below can be compared exactly.
#
# Three checks:
#   1. the generator layer still matches the committed golden output
#   2. a good generator passes            (data.e.32, the binary digits of e)
#   3. a bad generator is detected        (data.e, the same digits as ASCII text)
#   4. test 36 counts a template wherever it sits in a block
#
# Checks 2 and 3 compare against exact recorded values rather than a range,
# since the inputs are committed and the computation is deterministic. A
# mismatch means the build or a statistic changed, not that the generator is
# good or bad.
#
# Check 4 calls the statistic directly, because whether a counting error of
# this kind shows up in a p-value depends on the input.

cd "$(dirname "$0")" || exit 1

RTEST=./rtest
if [ ! -x "$RTEST" ]; then
  echo "FAIL: no rtest binary. Run 'make' first."
  exit 1
fi

trap 'rm -f tmp.out' EXIT

# Committed control pair, both derived from the digits of e:
#   data.e.32  the digits in binary, which should look random
#   data.e     the same digits as ASCII text, which should not
GOOD=../data/data.e.32
BAD=../data/data.e
REF=../data/data.e

# Recorded on a known-good build. These are exact, not approximate.
GOOD_EXPECTED=0.831969610796326586
BAD_EXPECTED=0.000000000014509394

fails=0

echo "1. generator layer against committed golden output"
if [ -x ./test-generators ]; then
  ./test-generators > tmp.out 2>/dev/null || true
  if diff -q test-generators.out tmp.out > /dev/null 2>&1; then
    echo "   ok"
  else
    echo "   FAIL: output differs from test-generators.out"
    fails=$((fails + 1))
  fi
else
  echo "   skipped (run 'make test-generators' to enable)"
fi

# control TESTED -> prints the first p-value of test 20 against the reference
control() {
  "$RTEST" -x -f "$1" -e "$REF" -t 20 -d 1 -n 100 -p 20 -q 20 -r 1 \
    2>/dev/null | head -1 | tr -d ' '
}

echo "2. good generator should pass (data.e.32, binary digits of e)"
p=$(control "$GOOD")
if [ "$p" = "$GOOD_EXPECTED" ]; then
  echo "   ok (p = $p)"
elif [ -z "$p" ]; then
  echo "   FAIL: no p-value returned."
  fails=$((fails + 1))
else
  echo "   FAIL: p = $p, expected $GOOD_EXPECTED."
  echo "         The inputs are committed, so this run should be exact."
  fails=$((fails + 1))
fi

echo "3. bad generator should be detected (data.e, the same digits as ASCII)"
p=$(control "$BAD")
if [ "$p" = "$BAD_EXPECTED" ]; then
  echo "   ok (p = $p)"
elif [ -z "$p" ]; then
  echo "   FAIL: no p-value returned."
  fails=$((fails + 1))
else
  echo "   FAIL: p = $p, expected $BAD_EXPECTED."
  fails=$((fails + 1))
fi

echo "4. test 36 counts a template at every offset in a block"
if [ -x ./test-nonperiodic-boundary ]; then
  if ./test-nonperiodic-boundary > /dev/null 2>&1; then
    echo "   ok"
  else
    echo "   FAIL: the count depends on where the template sits in the block."
    echo "         Run ./test-nonperiodic-boundary for the offsets that differ."
    fails=$((fails + 1))
  fi
else
  echo "   skipped (run 'make test-nonperiodic-boundary' to enable)"
fi

echo
if [ "$fails" -eq 0 ]; then
  echo "All checks passed."
  exit 0
fi
echo "$fails check(s) failed."
exit 1
