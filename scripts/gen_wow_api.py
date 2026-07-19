#!/usr/bin/env python3
"""Turn an in-game /papidump into a version-accurate luacheck std.

Reads the PeaversAPIDump SavedVariables file and writes
    build/<FLAVOR>/<BUILD>/wow-globals.lua   (a Lua module returning { read_globals = {...} })
which config/luacheckrc.base.lua loads automatically when present (else it falls back to
its curated list, so deleting the generated file is always safe). The flavor (mainline,
era, mists, ...) is derived from the dump's in-game projectId, so run /papidump once per
client (retail, Classic Era, MoP Classic, ...) and re-run this once per dump.

Usage:
    python3 scripts/gen_wow_api.py                  # auto-locate the newest dump
    python3 scripts/gen_wow_api.py --sv PATH        # explicit SavedVariables file
    python3 scripts/gen_wow_api.py --wow-root DIR   # search a specific WoW install
    python3 scripts/gen_wow_api.py --flavor era     # force the flavor (else auto-derived)

Workflow:
    1. In-game: enable "Peavers API Dump", /papidump, then /reload.
    2. python3 scripts/gen_wow_api.py
    3. luacheck now checks against the real client API.
"""
import argparse
import glob
import os
import re
import sys

# flavor.py lives alongside this script; when run as `python3 scripts/gen_wow_api.py`
# the script dir is already on sys.path, and gen_luals_defs inserts it before importing us.
import flavor

# Standard Lua libs/globals: leave these to luacheck's built-in lua51 std (keeps its
# stricter field checking for string/table/math/etc.). WoW extras (strsplit, wipe...)
# are NOT here, so they still get captured from _G.
# NOTE: not 'bit' — luacheck's lua51 std has no bit library, so we keep WoW's from _G.
DENY = {
    "_G", "_VERSION", "assert", "collectgarbage", "dofile", "error", "getfenv",
    "getmetatable", "ipairs", "load", "loadfile", "loadstring", "module", "next",
    "pairs", "pcall", "print", "rawequal", "rawget", "rawlen", "rawset", "require",
    "select", "setfenv", "setmetatable", "tonumber", "tostring", "type", "unpack",
    "xpcall", "string", "table", "math", "os", "io", "coroutine", "debug",
}

# The dump addon's own globals — never emit these into the shared std.
SELF_PREFIXES = ("PeaversAPIDump", "SLASH_PAPIDUMP")

# Globals belonging to OTHER addons that were loaded when the dump was taken. A dump only
# sees _G, so it cannot tell Blizzard's API from an addon's leaked globals — anything left
# here gets baked into the shared std and silently whitelisted for every addon we lint,
# which both hides our own pollution and lets typo'd cross-addon references pass.
#
# Take dumps with ONLY the dump addon enabled. This list is the backstop for when that
# slips: add the offending addon's prefixes rather than re-dumping.
FOREIGN_PREFIXES = (
    "MAXFPSBK", "OPTION_MAXFPSBK",   # third-party FPS addon, present in the 12.0.7 dump
    "Peavers", "BetterTogether",     # our own addons: never part of the WoW API
)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Base WoW install dirs across platforms. Each flavor lives in its own sub-root
# (_retail_, _classic_era_, _classic_, ...), so we expand the bases by every flavor's
# wow_root from flavors.json — find_sv then picks the most recently dumped client and
# the flavor is derived from the dump's own projectId/build, not from which root it came.
WOW_BASES = [
    "/Applications/World of Warcraft",
    os.path.expanduser("~/Applications/World of Warcraft"),
    r"C:\Program Files (x86)\World of Warcraft",
]


def _wow_roots():
    roots = []
    sub_roots = {f.get("wow_root") for f in flavor.load_flavors() if f.get("wow_root")}
    for base in WOW_BASES:
        for sub in sorted(sub_roots):
            roots.append(os.path.join(base, sub))
    return roots


# Kept as a module constant for back-compat (imported by gen_luals_defs).
WOW_ROOTS = _wow_roots()


def find_sv(explicit, wow_root):
    if explicit:
        return explicit
    roots = [wow_root] if wow_root else WOW_ROOTS
    candidates = []
    for root in roots:
        if not root:
            continue
        pattern = os.path.join(root, "WTF", "Account", "*", "SavedVariables",
                               "PeaversAPIDump.lua")
        candidates.extend(glob.glob(pattern))
    if not candidates:
        return None
    return max(candidates, key=os.path.getmtime)


def extract(text, key):
    m = re.search(r'\["%s"\]\s*=\s*"([^"]*)"' % re.escape(key), text)
    return m.group(1) if m else None


def build_tag_of(text):
    """The interface build number (e.g. '120007') from the dump's build string."""
    build = extract(text, "build") or "unknown"
    bm = re.search(r"interface\s+(\d+)", build)
    return build, (bm.group(1) if bm else "unknown")


def resolve_flavor(text, override=None):
    """Derive the flavor id for a dump: explicit override, then in-game projectId
    (authoritative), then interface-number range, finally mainline."""
    if override:
        return override
    by_pid = flavor.flavor_from_project_id(extract(text, "projectId"))
    if by_pid:
        return by_pid
    _, build_tag = build_tag_of(text)
    return flavor.flavor_from_interface(build_tag) or flavor.DEFAULT_FLAVOR


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sv", help="explicit path to PeaversAPIDump.lua")
    ap.add_argument("--wow-root", help="WoW install sub-root directory to search")
    ap.add_argument("--flavor", choices=flavor.canonical_flavors(),
                    help="force the flavor (default: derive from the dump's projectId/build)")
    args = ap.parse_args()

    sv = find_sv(args.sv, args.wow_root)
    if not sv or not os.path.exists(sv):
        sys.exit("No PeaversAPIDump.lua found. Run /papidump then /reload in-game first.\n"
                 "Searched: " + ", ".join(WOW_ROOTS))
    print("Reading %s" % sv, file=sys.stderr)

    with open(sv, encoding="utf-8", errors="replace") as fh:
        text = fh.read()

    raw = extract(text, "globals")
    if raw is None:
        sys.exit("Could not find the 'globals' field in the dump.")
    build, build_tag = build_tag_of(text)
    flavor_id = resolve_flavor(text, args.flavor)

    # Captured value has literal \n separators (WoW escapes newlines in SV strings).
    ids = [i for i in raw.split("\\n") if i]

    plain = set()
    namespaces = {}  # head -> set of fields
    for ident in ids:
        if ident.startswith(SELF_PREFIXES) or ident.startswith(FOREIGN_PREFIXES):
            continue
        if "." not in ident:
            if ident not in DENY:
                plain.add(ident)
        else:
            head, field = ident.split(".", 1)
            if head in DENY:
                continue
            namespaces.setdefault(head, set()).add(field)

    # A name that has descended fields is emitted as a namespace table, not a plain global.
    plain -= set(namespaces)

    lines = [
        "-- AUTO-GENERATED by scripts/gen_wow_api.py from an in-game /papidump. Do not edit.",
        "-- Flavor: %s  Client build: %s" % (flavor_id, build),
        "return {",
        "  read_globals = {",
    ]
    for name in sorted(plain):
        lines.append('    "%s",' % name)
    for name in sorted(namespaces):
        fields = ", ".join('"%s"' % f for f in sorted(namespaces[name]))
        lines.append("    %s = { fields = { %s } }," % (name, fields))
    lines += ["  },", "}", ""]

    out_dir = os.path.join(REPO_ROOT, "build", flavor_id, build_tag)
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "wow-globals.lua")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print("Wrote %s: %d globals + %d namespaces (flavor %s, build %s)"
          % (out, len(plain), len(namespaces), flavor_id, build), file=sys.stderr)


if __name__ == "__main__":
    main()
