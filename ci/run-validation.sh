#!/usr/bin/env bash
# Validate one addon with both tiers and emit reviewdog rdjson. Used by the reusable CI
# workflow and runnable locally for a dry run.
#
#   Env:
#     WOW_API_DIR        path to the wow-api package        (default: ../wow-api)
#     REVIEWDOG_REPORTER reviewdog -reporter value          (unset = local dry run, no post)
#     CHECK_LEVEL        LuaLS level: Error|Warning|Hint    (default: Warning)
#     FAIL_LEVEL         reviewdog -fail-level: error|any   (default: error)
#
#   Run from an addon directory:
#     ../wow-api/ci/run-validation.sh
set -uo pipefail

ADDON_DIR="$(pwd)"
WOW_API_DIR="${WOW_API_DIR:-../wow-api}"
CHECK_LEVEL="${CHECK_LEVEL:-Warning}"
FAIL_LEVEL="${FAIL_LEVEL:-error}"
CI_DIR="$WOW_API_DIR/ci"
OUT="$ADDON_DIR/.validate"
mkdir -p "$OUT"

targets=()
[ -d src ] && targets+=(src)
[ -f Changelog.lua ] && targets+=(Changelog.lua)
[ ${#targets[@]} -eq 0 ] && targets+=(.)

echo "::group::luacheck (existence)" 2>/dev/null || echo "== luacheck (existence) =="
luacheck "${targets[@]}" --formatter plain --codes 2>/dev/null \
  | python3 "$CI_DIR/luacheck_to_rdjson.py" > "$OUT/luacheck.rdjson"
echo "::endgroup::" 2>/dev/null || true

echo "::group::lua-language-server (signatures)" 2>/dev/null || echo "== lua-language-server (signatures) =="
LOGDIR="$OUT/luals-log"; META="$OUT/luals-meta"; mkdir -p "$LOGDIR" "$META"; CHECK="$LOGDIR/check.json"; rm -f "$CHECK"
# --metapath must be writable: LuaLS generates the runtime's builtin-type meta there. It defaults
# next to the executable, which is read-only in some sandboxes (e.g. a Lambda container's /opt),
# and without it every `---@param x string` becomes an "undefined-doc-name" false positive.
args=(--check . --checklevel="$CHECK_LEVEL" --check_format=json
      --check_out_path="$CHECK" --logpath="$LOGDIR" --metapath="$META")
[ -f .luarc.json ] && args+=(--configpath="$ADDON_DIR/.luarc.json")
lua-language-server "${args[@]}" >/dev/null 2>&1 || true
python3 "$CI_DIR/luals_to_rdjson.py" "$CHECK" "$ADDON_DIR" > "$OUT/luals.rdjson"
echo "::endgroup::" 2>/dev/null || true

lc=$(python3 -c "import json;print(len(json.load(open('$OUT/luacheck.rdjson'))['diagnostics']))")
ls_=$(python3 -c "import json;print(len(json.load(open('$OUT/luals.rdjson'))['diagnostics']))")
echo "luacheck: $lc finding(s) | lua-language-server: $ls_ finding(s)"

# REPORT_MODE selects how findings surface:
#   pr    -> reviewdog inline review comments (pull_request events)
#   issue -> upsert one tracking issue per repo (push/master + workflow_dispatch)
#   dry   -> local run: just write rdjson + summary, never post or fail (default)
MODE="${REPORT_MODE:-dry}"

case "$MODE" in
  pr)
    command -v reviewdog >/dev/null 2>&1 || { echo "reviewdog not on PATH"; exit 0; }
    # Inline PR comments on the diff. Errors fail (FAIL_LEVEL); warnings annotate only.
    rc=0
    reviewdog -f=rdjson -name=luacheck -reporter=github-pr-review -filter-mode=added \
      -fail-level="$FAIL_LEVEL" < "$OUT/luacheck.rdjson" || rc=$?
    reviewdog -f=rdjson -name=lua-language-server -reporter=github-pr-review -filter-mode=added \
      -fail-level="$FAIL_LEVEL" < "$OUT/luals.rdjson" || rc=$?
    exit $rc
    ;;
  issue)
    # Upsert the per-repo tracking issue (auto-closes when clean). Never fails the build.
    python3 "$CI_DIR/report_issue.py" "$OUT/luacheck.rdjson" "$OUT/luals.rdjson"
    exit 0
    ;;
  *)
    echo "(dry run: set REPORT_MODE=pr|issue to post; rdjson written to $OUT/)"
    exit 0
    ;;
esac
