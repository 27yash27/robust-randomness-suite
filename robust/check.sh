#!/bin/sh
# check.sh -- smoke test for a fresh build. Run it as "make check".
#
# Uses only files committed to this repository, plus a small throwaway etalon
# read from /dev/urandom, so it works on a clean checkout with no setup.
#
# Three checks:
#   1. the generator layer still matches the committed golden output
#   2. a good generator passes            (data.e.32, the binary digits of e)
#   3. a bad generator is detected        (data.e, the same digits as ASCII text)
#
# Check 2 also catches the KS underflow bug described in CHANGES-vs-upstream.md:
# a p-value of exactly 1.0 fails here rather than reading as a clean pass.

cd "$(dirname "$0")" || exit 1

RTEST=./rtest
if [ ! -x "$RTEST" ]; then
  echo "FAIL: no rtest binary. Run 'make' first."
  exit 1
fi

ETAL="${TMPDIR:-/tmp}/rtest_check_etalon.$$"
trap 'rm -f "$ETAL" tmp.out' EXIT
head -c 4000000 /dev/urandom > "$ETAL"

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

# run_test TEST DIM N P FILE -> prints the first p-value
run_test() {
  "$RTEST" -x -f "$5" -e "$ETAL" -p "$4" -q "$4" -d "$2" -n "$3" -t "$1" -r 1 \
    2>/dev/null | head -1 | tr -d ' '
}

echo "2. good generator should pass (data.e.32, binary digits of e)"
p=$(run_test 0 1 0 20 ../data/data.e.32)
verdict=$(awk -v p="$p" 'BEGIN{
  if (p == "" )            print "empty";
  else if (p+0 >= 0.9999)  print "high";
  else if (p+0 <= 0.0001)  print "low";
  else                     print "ok";
}')
case "$verdict" in
  ok)    echo "   ok (p = $p)" ;;
  high)  echo "   FAIL: p = $p. A p-value at or near 1.0 usually means the KS"
         echo "         routine underflowed. See CHANGES-vs-upstream.md."
         fails=$((fails + 1)) ;;
  low)   echo "   FAIL: p = $p. A known-good generator was rejected."
         fails=$((fails + 1)) ;;
  *)     echo "   FAIL: no p-value returned."; fails=$((fails + 1)) ;;
esac

echo "3. bad generator should be detected (data.e, the same digits as ASCII)"
p=$(run_test 0 1 0 20 ../data/data.e)
verdict=$(awk -v p="$p" 'BEGIN{
  if (p == "")            print "empty";
  else if (p+0 < 0.000001) print "ok";
  else                     print "missed";
}')
case "$verdict" in
  ok)     echo "   ok (p = $p)" ;;
  missed) echo "   FAIL: p = $p. ASCII text should be detected easily;"
          echo "         the test lost its sensitivity."
          fails=$((fails + 1)) ;;
  *)      echo "   FAIL: no p-value returned."; fails=$((fails + 1)) ;;
esac

echo
if [ "$fails" -eq 0 ]; then
  echo "All checks passed."
  exit 0
fi
echo "$fails check(s) failed."
exit 1
