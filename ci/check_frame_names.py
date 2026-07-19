#!/usr/bin/env python3
"""Flag globally-named frames whose name is not addon-prefixed, as reviewdog rdjson.

    python3 check_frame_names.py [ADDON_DIR] > framenames.rdjson

Why this exists as its own tier: luacheck cannot see these. `CreateFrame("Frame", "Name", ...)`
puts "Name" into _G at *runtime*, so no amount of static global analysis in luacheck reports
it — flipping allow_defined_top catches assignments, never frame names. This is the vector
that actually floods _G: naming a *templated* frame also creates a named global for every
child the template defines, so one CreateFrame call can mint 30 globals (see
BetterTogetherPanel -> BetterTogetherPanelInsetScrollBarThumbTexture, and 28 more).

Codes:
  NS001 (ERROR)   named frame whose name lacks an approved prefix — collision risk with
                  other addons. This is the one worth failing a build over.
  NS002 (INFO)    named frame built from a template — also creates named children. Prefer an
                  anonymous frame (pass nil) unless the name is genuinely required.

A global name is only genuinely required when something outside Lua resolves it by string:
Bindings.xml, XML template `parentKey`/inherits references, or another addon's documented
integration point. Everything else should be anonymous and held in a local.

Approved prefixes default to the addon's own directory name. Addons using a short alias
(PDS_, PSB...) declare it in an optional .wowlint.json beside the TOC:

    { "framePrefixes": ["PDS_"] }
"""
import json
import os
import re
import sys

# CreateFrame(<type>, <name> ...) — we only care about the second argument. A string literal
# there is a global name; nil / a variable / an omitted arg is anonymous and always fine.
CALL = re.compile(
    r"""CreateFrame\s*\(\s*
        (?:"[^"]*"|'[^']*'|\[\[.*?\]\])   # arg 1: frame type
        \s*,\s*
        (?P<q>["'])(?P<name>[^"']*)(?P=q)  # arg 2: a *literal* name -> a global
    """,
    re.VERBOSE,
)

SKIP_DIRS = {"Libs", "libs", "Templates", ".release", "tools", ".git", "build", "vendor"}


def approved_prefixes(addon_dir):
    prefixes = [os.path.basename(os.path.abspath(addon_dir))]
    cfg = os.path.join(addon_dir, ".wowlint.json")
    if os.path.isfile(cfg):
        try:
            with open(cfg, encoding="utf-8") as fh:
                extra = json.load(fh).get("framePrefixes") or []
            prefixes.extend(str(p) for p in extra)
        except (OSError, ValueError) as exc:
            print("warning: could not read %s: %s" % (cfg, exc), file=sys.stderr)
    return prefixes


def lua_files(addon_dir):
    for root, dirs, files in os.walk(addon_dir):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in sorted(files):
            if fn.endswith(".lua"):
                yield os.path.join(root, fn)


def diagnose(addon_dir, prefixes):
    out = []
    for path in lua_files(addon_dir):
        rel = os.path.relpath(path, addon_dir)
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                lines = fh.readlines()
        except OSError as exc:
            print("warning: could not read %s: %s" % (path, exc), file=sys.stderr)
            continue
        for n, text in enumerate(lines, 1):
            for m in CALL.finditer(text):
                name = m.group("name")
                col = m.start("name") + 1
                if not name.startswith(tuple(prefixes)):
                    out.append((rel, n, col, "ERROR", "NS001",
                                "frame name %r is not addon-prefixed, so it collides with any "
                                "other addon using the same name; prefix it (%s...) or pass nil "
                                "for an anonymous frame" % (name, prefixes[0])))
                elif "Template" in text[m.end():]:
                    out.append((rel, n, col, "INFO", "NS002",
                                "named frame %r uses a template, so WoW also creates a global "
                                "for every named child the template defines; pass nil unless "
                                "the name is resolved by string somewhere" % name))
    return out


def main():
    addon_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    prefixes = approved_prefixes(addon_dir)
    diagnostics = [
        {
            "message": msg,
            "location": {"path": path,
                         "range": {"start": {"line": line, "column": col}}},
            "severity": sev,
            "code": {"value": code},
        }
        for path, line, col, sev, code, msg in diagnose(addon_dir, prefixes)
    ]
    json.dump({"source": {"name": "frame-names"}, "diagnostics": diagnostics}, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
