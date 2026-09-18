#!/usr/bin/env bash
# Validate one addon with all three tiers and emit reviewdog rdjson. Runnable locally, and
# the analysis core AddonSentry runs per job.
#
# This script produces rdjson and nothing else; posting is the caller's job. AddonSentry
# maps these files into GitHub Check Runs and inline PR comments (worker/rdjson_to_checks.py,
# worker/pr_comments.py), which superseded the reviewdog and tracking-issue paths that used
# to live here.
#
#   Env:
#     WOW_API_DIR        path to the wow-api package        (default: ../wow-api)
#     WOW_FLAVOR         flavor whose defs to use           (default: mainline; read by .luacheckrc)
#     WOW_BUILD          interface build under that flavor  (unset = curated fallback)
#     CHECK_LEVEL        LuaLS level: Error|Warning|Hint    (default: Warning)
#   WOW_FLAVOR/WOW_BUILD are consumed by the addon's .luacheckrc (via luacheckrc.base.lua);
#   the caller (AddonSentry) exports them per run to select build/<flavor>/<build>/.
#
#   Run from an addon directory:
#     ../wow-api/ci/run-validation.sh
set -uo pipefail

ADDON_DIR="$(pwd)"
WOW_API_DIR="${WOW_API_DIR:-../wow-api}"
CHECK_LEVEL="${CHECK_LEVEL:-Warning}"
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
LOGDIR="$OUT/luals-log"; mkdir -p "$LOGDIR"; CHECK="$LOGDIR/check.json"; rm -f "$CHECK"
# --metapath: LuaLS generates the runtime's builtin-type meta here. Two requirements:
#  1) writable — it defaults next to the executable, which is read-only in some sandboxes (e.g. a
#     Lambda container's /opt); without it every `---@param x string` is an undefined-doc-name.
#  2) OUTSIDE the checked workspace — those generated .lua meta files must not be picked up by
#     `--check .`, or LuaLS reports duplicate-doc-field/deprecated false positives against itself.
META="$(mktemp -d "${TMPDIR:-/tmp}/wow-api-luals-meta.XXXXXX")"
args=(--check . --checklevel="$CHECK_LEVEL" --check_format=json
      --check_out_path="$CHECK" --logpath="$LOGDIR" --metapath="$META")
[ -f .luarc.json ] && args+=(--configpath="$ADDON_DIR/.luarc.json")
lua-language-server "${args[@]}" >/dev/null 2>&1 || true
rm -rf "$META"
python3 "$CI_DIR/luals_to_rdjson.py" "$CHECK" "$ADDON_DIR" > "$OUT/luals.rdjson"
echo "::endgroup::" 2>/dev/null || true

echo "::group::frame names (_G pollution)" 2>/dev/null || echo "== frame names (_G pollution) =="
# Third tier: globally-named frames. luacheck cannot see these — CreateFrame puts the name
# into _G at runtime — so without this pass, the vector that actually floods the global
# namespace is completely unchecked. NS001 is an error, NS002 informational.
# A bad .wowlint.json exits non-zero here. Fail loudly rather than continue with an empty
# report, which would look identical to "this addon is clean".
if ! python3 "$CI_DIR/check_frame_names.py" "$ADDON_DIR" > "$OUT/framenames.rdjson"; then
  echo "frame-name check failed (see error above); not reporting partial results" >&2
  exit 1
fi
echo "::endgroup::" 2>/dev/null || true

count() { python3 -c "import json;print(len(json.load(open('$1'))['diagnostics']))"; }
lc=$(count "$OUT/luacheck.rdjson")
ls_=$(count "$OUT/luals.rdjson")
fn=$(count "$OUT/framenames.rdjson")
echo "luacheck: $lc finding(s) | lua-language-server: $ls_ finding(s) | frame-names: $fn finding(s)"

echo "(rdjson written to $OUT/)"
