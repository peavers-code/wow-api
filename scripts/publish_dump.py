#!/usr/bin/env python3
"""Turn an in-game /papidump into a wow-api pull request in one command.

Run it on the machine where you ran /papidump (then /reload), from anywhere inside this
checkout:

    python3 scripts/publish_dump.py                 # auto-locate the newest dump
    python3 scripts/publish_dump.py --sv PATH       # explicit SavedVariables file
    python3 scripts/publish_dump.py --dry-run       # generate and show the diff, no git writes

It:
    1. checks the working tree is clean, fetches origin, and starts a branch off origin/master
    2. runs gen_wow_api.py and gen_luals_defs.py (same --sv/--wow-root/--flavor options)
    3. checks the three generated files exist and name the same client build
    4. for a new newest mainline build, points config/luarc.base.json at it
    5. commits, pushes, and opens the PR with gh (prints a compare link when gh is missing)

The branch is chore/<flavor>-<build>-defs. Once the PR merges, AddonSentry still has to be
redeployed, re-pinned and rescanned onto the build; the weekly addon health check does that.
"""
import argparse
import datetime
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
LUARC = os.path.join("config", "luarc.base.json")
GENERATED = ("wow-globals.lua", os.path.join("luals", "wow-api.lua"),
             os.path.join("luals", "wow-globals.lua"))


def git(*args, capture=True, check=True):
    res = subprocess.run(["git", "-C", REPO_ROOT, *args], text=True,
                         capture_output=capture)
    if check and res.returncode != 0:
        sys.exit("git %s failed:\n%s" % (" ".join(args), (res.stderr or "").strip()))
    return (res.stdout or "").strip()


def generated_builds():
    """(flavor, build) pairs whose build/<flavor>/<build>/ has new or changed files."""
    out = git("status", "--porcelain", "--untracked-files=all", "--", "build")
    found = set()
    for line in out.splitlines():
        m = re.match(r"build/([^/]+)/(\d+)/", line[3:].strip().strip('"'))
        if m:
            found.add((m.group(1), m.group(2)))
    return sorted(found)


def header_build(path):
    """The 'Client build: X interface N' stamp a generator wrote, or None."""
    with open(path, encoding="utf-8", errors="replace") as fh:
        head = fh.read(400)
    m = re.search(r"Client build:\s*(.+?interface\s+\d+)", head)
    return m.group(1) if m else None


def point_luarc_at(build):
    """Move the mainline build path in config/luarc.base.json forward to `build`."""
    path = os.path.join(REPO_ROOT, LUARC)
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    m = re.search(r"build/mainline/(\d+)/luals", text)
    if not m or int(m.group(1)) >= int(build):
        return False
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text.replace(m.group(0), "build/mainline/%s/luals" % build))
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sv", help="explicit path to PeaversAPIDump.lua")
    ap.add_argument("--wow-root", help="WoW install sub-root directory to search")
    ap.add_argument("--flavor", help="force the flavor (default: derived from the dump)")
    ap.add_argument("--dry-run", action="store_true",
                    help="generate and print the diff; leave git untouched")
    args = ap.parse_args()

    if git("status", "--porcelain"):
        sys.exit("Working tree has uncommitted changes; commit or stash them first.")

    original = git("rev-parse", "--abbrev-ref", "HEAD")
    start = None
    if not args.dry_run:
        git("fetch", "origin", "master", capture=False)
        start = "dump-%s" % datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        git("checkout", "-q", "-b", start, "origin/master")

    gen_args = []
    for opt in ("sv", "wow_root", "flavor"):
        if getattr(args, opt):
            gen_args += ["--" + opt.replace("_", "-"), getattr(args, opt)]
    for script in ("gen_wow_api.py", "gen_luals_defs.py"):
        res = subprocess.run([sys.executable, os.path.join(HERE, script), *gen_args])
        if res.returncode != 0:
            sys.exit("%s failed; you are on branch %s (git checkout %s to go back)"
                     % (script, start or original, original))

    builds = generated_builds()
    if not builds:
        if start:
            git("checkout", "-q", original)
            git("branch", "-q", "-D", start)
        sys.exit("The dump matches what is already committed; nothing to publish.")
    if len(builds) > 1:
        sys.exit("Expected one build to change, got %s" % builds)
    flavor_id, build = builds[0]
    build_dir = os.path.join(REPO_ROOT, "build", flavor_id, build)

    stamps = set()
    for rel in GENERATED:
        path = os.path.join(build_dir, rel)
        if not os.path.exists(path):
            sys.exit("Missing %s; the generators did not finish." % path)
        stamp = header_build(path)
        if stamp:
            stamps.add(stamp)
    if len(stamps) > 1:
        sys.exit("Generated files disagree on the client build: %s" % sorted(stamps))
    client = stamps.pop() if stamps else "interface %s" % build
    is_new = not git("ls-tree", "origin/master", "build/%s/%s" % (flavor_id, build))

    changed = [os.path.join("build", flavor_id, build)]
    if flavor_id == "mainline" and point_luarc_at(build):
        changed.append(LUARC)

    print("\n%s %s: %s" % ("Adding" if is_new else "Refreshing", flavor_id, client))
    print(git("status", "--short", "--", *changed))
    if args.dry_run:
        print("\n--dry-run: nothing committed. Revert with: git checkout -- . && git clean -fd build")
        return

    today = datetime.date.today().isoformat()
    title = "chore(build): %s %s %s from %s dump" % (
        "add" if is_new else "refresh", flavor_id, build, today)
    body = ("Generated from an in-game /papidump (%s) with gen_wow_api.py and gen_luals_defs.py."
            % client)
    branch = "chore/%s-%s-defs" % (flavor_id, build)
    git("branch", "-m", branch)
    git("add", "--", *changed)
    git("commit", "-q", "-m", title, "-m", body)
    git("push", "-u", "origin", branch, capture=False)

    if shutil.which("gh"):
        res = subprocess.run(["gh", "pr", "create", "--base", "master", "--head", branch,
                              "--title", title, "--body", body], cwd=REPO_ROOT)
        if res.returncode == 0:
            return
    remote = git("remote", "get-url", "origin")
    slug = re.sub(r"(^.*github\.com[:/])|(\.git$)", "", remote)
    print("\nOpen the PR at: https://github.com/%s/compare/master...%s?expand=1" % (slug, branch))


if __name__ == "__main__":
    main()
