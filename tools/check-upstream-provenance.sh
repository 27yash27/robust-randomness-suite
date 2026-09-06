#!/bin/sh
# Compare this tree against upstream rtest and print, for every tracked file,
# whether it is identical to upstream, modified from it, or new here.
#
#   tools/check-upstream-provenance.sh [path-to-upstream-clone]
#
# With no argument it clones the pinned upstream revision into a temporary
# directory. Exits non-zero if the set of modified files differs from the set
# recorded in CHANGES-vs-upstream.md.

UPSTREAM_URL=https://github.com/alexander-shen/rtest.git
UPSTREAM_SHA=6ae81dcec44d5cbe46c7bc58620c275a7cfa3c1d

cd "$(dirname "$0")/.." || exit 1

if [ -n "$1" ]; then
  UP="$1"
else
  UP="$(mktemp -d)"
  echo "cloning upstream $UPSTREAM_SHA ..."
  git clone -q "$UPSTREAM_URL" "$UP" || exit 1
  (cd "$UP" && git checkout -q "$UPSTREAM_SHA") || exit 1
fi

echo "upstream: $UPSTREAM_SHA"
echo

same=0; modified=""; new=0
for f in $(git ls-files); do
  case "$f" in
    reproducibility/*|scripts/*|tools/*|LICENSING.md|CHANGES-vs-upstream.md) continue ;;
  esac
  if [ -f "$UP/$f" ]; then
    if cmp -s "$f" "$UP/$f"; then
      same=$((same + 1))
    else
      modified="$modified $f"
    fi
  else
    new=$((new + 1))
  fi
done

echo "identical to upstream : $same"
echo "modified from upstream:$modified"
echo "new in this repository: $new (see CHANGES-vs-upstream.md)"

expected=" README.md robust/Makefile robust/test_func.c robust/test_func.h"
expected_same=113
expected_new=29

rc=0
if [ "$modified" != "$expected" ]; then
  echo
  echo "MISMATCH: the modified set is not the one CHANGES-vs-upstream.md records."
  echo "expected:$expected"
  rc=1
fi

# The counts are quoted in CHANGES-vs-upstream.md and in README.md, so they are
# checked too: without this they go stale silently the next time a file is added.
if [ "$same" != "$expected_same" ] || [ "$new" != "$expected_new" ]; then
  echo
  echo "MISMATCH: counts are $same identical / $new new,"
  echo "but CHANGES-vs-upstream.md records $expected_same identical / $expected_new new."
  echo "Update that file (and the count in README.md) or this script."
  rc=1
fi

if [ "$rc" -ne 0 ]; then
  exit 1
fi
echo
echo "The modified set and the counts match CHANGES-vs-upstream.md."
