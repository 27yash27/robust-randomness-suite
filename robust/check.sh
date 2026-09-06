#!/bin/sh
# check.sh -- smoke test for a fresh build. Run it as "make check".
#
# Uses only files committed to this repository, so the inputs are identical
# everywhere. The controls run with -k, the exact multiprecision routine, whose
# output is far more portable than the default kernel's: the default differs
# between macOS and Linux around the 16th digit because long double is 8 bytes
# on Apple Silicon and 16 on x86-64. Values are still compared with a relative
# tolerance rather than as strings, since no floating-point result is
# guaranteed identical across platforms and compilers.
#
# Three checks:
#   1. the generator layer still matches the committed golden output
#   2. a good input passes                (data.e.32, the binary digits of e)
#   3. a bad input is detected            (data.e, the same digits as ASCII text)
#
# The two committed files are the same digits in different encodings, so they
# are not independent sources. That is adequate for a build tripwire, which is
# all this is; it is not a statement about either file's randomness.
#   4. test 36 counts a template wherever it sits in a block
#
# A mismatch in checks 2 or 3 means the build or a statistic changed, not that
# the generator under test is good or bad.
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
# Each control is compared against the other file, never against itself: running
# a file as its own etalon is not the two-sample construction at all.
GOOD_REF=../data/data.e
BAD_REF=../data/data.e.32

# Recorded on a known-good build, using -k. Compared with the relative
# tolerance below, not character for character.
GOOD_EXPECTED=0.831969610796326475
BAD_EXPECTED=0.000000000014508889
TOLERANCE=1e-9

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
# control TESTED REFERENCE -> the first p-value of test 20
control() {
  "$RTEST" -k -x -f "$1" -e "$2" -t 20 -d 1 -n 100 -p 20 -q 20 -r 1 \
    2>/dev/null | head -1 | tr -d ' '
}

# close GOT EXPECTED -> "yes" when they agree to within TOLERANCE, relative for
# values away from zero and absolute very close to it
close() {
  awk -v got="$1" -v want="$2" -v tol="$TOLERANCE" 'BEGIN{
    if (got == "") { print "no"; exit }
    d = got - want; if (d < 0) d = -d;
    scale = (want < 0 ? -want : want);
    if (scale < 1e-300) { print (d <= tol) ? "yes" : "no"; exit }
    print (d / scale <= tol) ? "yes" : "no";
  }'
}

echo "2. good generator should pass (data.e.32, binary digits of e)"
p=$(control "$GOOD" "$GOOD_REF")
if [ "$(close "$p" "$GOOD_EXPECTED")" = "yes" ]; then
  echo "   ok (p = $p)"
elif [ -z "$p" ]; then
  echo "   FAIL: no p-value returned."
  fails=$((fails + 1))
else
  echo "   FAIL: p = $p, expected $GOOD_EXPECTED (relative tolerance $TOLERANCE)."
  fails=$((fails + 1))
fi

echo "3. bad generator should be detected (data.e, the same digits as ASCII)"
p=$(control "$BAD" "$BAD_REF")
if [ "$(close "$p" "$BAD_EXPECTED")" = "yes" ]; then
  echo "   ok (p = $p)"
elif [ -z "$p" ]; then
  echo "   FAIL: no p-value returned."
  fails=$((fails + 1))
else
  echo "   FAIL: p = $p, expected $BAD_EXPECTED (relative tolerance $TOLERANCE)."
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
