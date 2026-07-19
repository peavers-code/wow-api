#!/usr/bin/env python3
"""Build the Lua Language Server definition files from an in-game /papidump.

Writes (under build/<FLAVOR>/<BUILD>/luals/):
    wow-api.lua      signatures (@param/@return) for documented APIs
    wow-globals.lua  `any` stubs for EVERY global, so the thousands of FrameXML globals
                     not in APIDocumentation (CreateFrame, font objects, GetAchievementInfo,
                     ...) don't read as undefined. Existence-only; luacheck does strict
                     field checking, so LuaLS's job here is signatures + editor IX.

These sit UNDER the Ketho community annotations in workspace.library: Ketho provides rich
signatures for the broad API, this overlay adds build-exact existence + private globals.

Usage:
    python3 scripts/gen_luals_defs.py [--sv PATH] [--wow-root DIR] [--flavor era]
"""
import argparse
import os
import re
import sys

# Reuse the dump-locating + extraction helpers from the sibling generator.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import flavor  # noqa: E402
from gen_wow_api import (  # noqa: E402
    find_sv, extract, build_tag_of, resolve_flavor, SELF_PREFIXES, FOREIGN_PREFIXES,
    WOW_ROOTS, REPO_ROOT,
)


def unescape(v):
    # WoW SV strings escape backslash/newline/tab. Decode in an order that doesn't
    # re-interpret a literal "\n" produced by unescaping a real backslash.
    v = v.replace("\\\\", "\0")
    v = v.replace("\\n", "\n").replace("\\t", "\t")
    return v.replace("\0", "\\")


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

    build, build_tag = build_tag_of(text)
    flavor_id = resolve_flavor(text, args.flavor)
    out_dir = os.path.join(REPO_ROOT, "build", flavor_id, build_tag, "luals")
    os.makedirs(out_dir, exist_ok=True)

    # --- 1. Signatures -----------------------------------------------------
    emmy = extract(text, "emmylua")
    if emmy is None:
        sys.exit("Could not find the 'emmylua' field in the dump.")
    emmy = unescape(emmy)
    api_out = os.path.join(out_dir, "wow-api.lua")
    with open(api_out, "w", encoding="utf-8") as fh:
        fh.write(emmy if emmy.endswith("\n") else emmy + "\n")
    func_count = len(re.findall(r"(?m)^function ", emmy))

    # Names already defined by the signature file (documented namespaces + global funcs);
    # don't redeclare these as `any` or we'd clobber their real types.
    defined = set(re.findall(r"(?m)^(\w+) = \{\}", emmy))
    defined |= set(re.findall(r"(?m)^function (\w+)\(", emmy))

    # --- 2. Existence stubs for every other top-level global ---------------
    raw_globals = extract(text, "globals") or ""
    globals_list = [g for g in raw_globals.split("\\n") if g]
    lines = [
        "---@meta",
        "-- AUTO-GENERATED existence stubs from /papidump. Top-level globals not covered by",
        "-- APIDocumentation, declared as `any` so LuaLS knows they exist. Do not edit.",
    ]
    seen = set()
    count = 0
    for ident in globals_list:
        if "." in ident:
            continue  # top-level only
        if ident.startswith(SELF_PREFIXES) or ident.startswith(FOREIGN_PREFIXES):
            continue
        if ident in defined or ident in seen:
            continue
        seen.add(ident)
        lines.append("---@type any")
        lines.append("%s = nil" % ident)
        count += 1
    glob_out = os.path.join(out_dir, "wow-globals.lua")
    with open(glob_out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    print("Wrote %s (%d documented functions)" % (api_out, func_count), file=sys.stderr)
    print("Wrote %s (%d existence stubs)" % (glob_out, count), file=sys.stderr)


if __name__ == "__main__":
    main()
