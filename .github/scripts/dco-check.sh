#!/usr/bin/env bash
# Check that every non-merge commit in BASE..HEAD carries a Signed-off-by trailer
# that matches the commit author. Usage: dco-check.sh BASE_SHA HEAD_SHA
set -euo pipefail

base="${1:?base sha required}"
head="${2:?head sha required}"

fail=0
checked=0
for sha in $(git rev-list --no-merges "${base}..${head}"); do
  checked=$((checked + 1))
  author="$(git show -s --format='%an <%ae>' "$sha")"
  trailers="$(git show -s --format='%(trailers:key=Signed-off-by,valueonly)' "$sha")"
  if [ -z "$trailers" ]; then
    echo "::error::commit ${sha:0:12} has no Signed-off-by line"
    fail=1
  elif ! grep -qiF -- "$author" <<<"$trailers"; then
    echo "::error::commit ${sha:0:12} is signed off, but not by its author (${author})"
    fail=1
  fi
done

if [ "$fail" -ne 0 ]; then
  echo "Sign off each commit with 'git commit -s'. To fix existing commits:"
  echo "  git rebase --signoff ${base}"
  exit 1
fi
echo "DCO check passed for ${checked} commit(s)."
