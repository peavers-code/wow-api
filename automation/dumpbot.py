#!/usr/bin/env python3
"""dumpbot — unattended daily multi-flavor WoW API dumper.

For each configured client (clients.json), in sequence:
  1. note the current PeaversAPIDump SavedVariables mtime (stale-guard),
  2. launch the client and drive it past login -> char select -> in-world via navigate.ahk,
     (the apidump-auto companion addon then dumps and Quit()s, flushing SavedVariables),
  3. poll until that client's SavedVariables file is freshly written (or time out),
  4. run scripts/gen_wow_api.py + gen_luals_defs.py to regenerate build/<flavor>/<build>/,
  5. record the per-client outcome.
Then stage build/<flavor>/ for the flavors that refreshed and commit + push to the wow-api repo
(only successful flavors are staged, so a stuck/failed client never clobbers good committed defs).

Designed for a dedicated Windows dump server run daily by Task Scheduler (see README.md). Driving
the client with synthetic input is against Blizzard's ToS — dev tooling, own accounts, own risk.

  python automation/dumpbot.py                  # full run (launch, generate, commit, push)
  python automation/dumpbot.py --dry-run        # no launch/AHK/push: generate from existing SVs,
                                                #   print the commit it WOULD make
  python automation/dumpbot.py --config PATH    # alternate clients.json
  python automation/dumpbot.py --no-push        # generate + commit locally, skip push
"""
import argparse
import glob
import json
import os
import subprocess
import sys
import time

AUTOMATION_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(AUTOMATION_DIR)           # the wow-api repo root
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
sys.path.insert(0, SCRIPTS_DIR)
import flavor          # noqa: E402  shared flavor resolution (config/flavors.json)
import gen_wow_api as gw  # noqa: E402  reuse extract/build_tag_of/resolve_flavor

DEFAULT_TIMEOUT = 300      # seconds to wait for a client to dump + quit
POLL_INTERVAL = 5          # seconds between SavedVariables freshness checks
SV_NAME = "PeaversAPIDump.lua"


# --- config ----------------------------------------------------------------
def load_config(path):
    with open(path, encoding="utf-8") as fh:
        cfg = json.load(fh)
    if isinstance(cfg, list):           # bare list of clients is allowed
        cfg = {"clients": cfg}
    cfg.setdefault("clients", [])
    cfg.setdefault("ahk_exe", "AutoHotkey.exe")
    cfg.setdefault("default_timeout", DEFAULT_TIMEOUT)
    return cfg


# --- SavedVariables ---------------------------------------------------------
def find_sv(wow_root):
    """Newest PeaversAPIDump.lua under <wow_root>/WTF/Account/*/SavedVariables/, or None."""
    pattern = os.path.join(wow_root, "WTF", "Account", "*", "SavedVariables", SV_NAME)
    candidates = glob.glob(pattern)
    return max(candidates, key=os.path.getmtime) if candidates else None


def sv_mtime(wow_root):
    sv = find_sv(wow_root)
    return os.path.getmtime(sv) if sv else 0.0


def read_sv_meta(sv, override=None):
    """(flavor, build_tag) for a dumped SavedVariables file, via the same logic the generators use."""
    with open(sv, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    _, build_tag = gw.build_tag_of(text)
    return gw.resolve_flavor(text, override), build_tag


# --- client launch + navigation --------------------------------------------
def launch_client(entry):
    exe = entry["exe"]
    return subprocess.Popen([exe], cwd=os.path.dirname(exe) or None)


def navigate(cfg, entry, log):
    """Run navigate.ahk to click through login -> character select -> Enter World. The AHK script
    takes per-client timing args; absent AutoHotkey (e.g. a dev box) is a soft failure we log."""
    nav = entry.get("navigate", {})
    ahk_script = os.path.join(AUTOMATION_DIR, "navigate.ahk")
    args = [cfg["ahk_exe"], ahk_script,
            str(nav.get("login_wait", 25)), str(nav.get("char_wait", 15)),
            str(nav.get("enters", 2)), nav.get("window_title", "World of Warcraft")]
    try:
        subprocess.run(args, check=False)
    except FileNotFoundError:
        log(f"  ! AutoHotkey not found ({cfg['ahk_exe']}); skipping navigation")


def terminate(proc, entry, log):
    """Best-effort: ensure the client process is gone before the next entry."""
    try:
        if proc and proc.poll() is None:
            proc.terminate()
    except Exception as e:  # noqa: BLE001
        log(f"  ! terminate failed (non-fatal): {e}")
    image = os.path.basename(entry["exe"])
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/F", "/IM", image], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# --- generators -------------------------------------------------------------
def run_generators(flavor_id, wow_root, log):
    """Regenerate build/<flavor>/<build>/ from the freshly-dumped SV. Returns True on success."""
    common = ["--flavor", flavor_id, "--wow-root", wow_root]
    for script in ("gen_wow_api.py", "gen_luals_defs.py"):
        cmd = [sys.executable, os.path.join(SCRIPTS_DIR, script), *common]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.stderr.strip():
            for line in res.stderr.strip().splitlines():
                log(f"    {script}: {line}")
        if res.returncode != 0:
            log(f"  ! {script} failed (rc={res.returncode})")
            return False
    return True


# --- per-client orchestration ----------------------------------------------
def process_entry(cfg, entry, log, dry_run):
    name = entry.get("name") or entry.get("flavor") or entry["exe"]
    wow_root = entry["wow_root"]
    override = entry.get("flavor")
    log(f"- {name} ({wow_root})")

    if dry_run:
        sv = find_sv(wow_root)
        if not sv:
            return {"name": name, "status": "FAILED", "reason": "no existing SavedVariables (dry-run)"}
    else:
        before = sv_mtime(wow_root)
        proc = launch_client(entry)
        navigate(cfg, entry, log)
        timeout = entry.get("timeout", cfg["default_timeout"])
        deadline = time.monotonic() + timeout
        sv = None
        while time.monotonic() < deadline:
            time.sleep(POLL_INTERVAL)
            if sv_mtime(wow_root) > before:
                sv = find_sv(wow_root)
                break
        terminate(proc, entry, log)
        if not sv:
            return {"name": name, "status": "FAILED",
                    "reason": f"no fresh dump within {timeout}s (client stuck at login?)"}

    flavor_id, build = read_sv_meta(sv, override)
    log(f"  dumped flavor={flavor_id} build={build}")
    if not run_generators(flavor_id, wow_root, log):
        return {"name": name, "status": "FAILED", "flavor": flavor_id, "build": build,
                "reason": "generator error"}
    return {"name": name, "status": "OK", "flavor": flavor_id, "build": build}


# --- git --------------------------------------------------------------------
def git(*args, check=True):
    return subprocess.run(["git", "-C", REPO_ROOT, *args], capture_output=True, text=True,
                          check=check)


def commit_and_push(results, log, dry_run, push):
    refreshed = [r for r in results if r["status"] == "OK"]
    if not refreshed:
        log("no flavors refreshed; nothing to commit")
        return
    for r in sorted({x["flavor"] for x in refreshed}):
        git("add", os.path.join("build", r))
    if git("diff", "--cached", "--quiet", check=False).returncode == 0:
        log("build defs unchanged; nothing to commit")
        return
    summary = " ".join(f"{r['flavor']}={r['build']}" for r in refreshed)
    message = f"chore(build): refresh defs {summary} [dumpbot]"
    if dry_run:
        log(f"[dry-run] would commit: {message}")
        log("[dry-run] staged diff:\n" + git("diff", "--cached", "--stat", check=False).stdout)
        git("reset", check=False)  # leave the index clean after a dry run
        return
    git("commit", "-m", message)
    log(f"committed: {message}")
    if push:
        git("push", "origin", "HEAD")
        log("pushed to origin")
    else:
        log("--no-push: left commit local")


# --- main -------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=os.path.join(AUTOMATION_DIR, "clients.json"))
    ap.add_argument("--dry-run", action="store_true",
                    help="skip launch/AHK/push: generate from existing SVs, print intended commit")
    ap.add_argument("--no-push", action="store_true", help="commit locally but do not push")
    args = ap.parse_args()

    if not os.path.exists(args.config):
        sys.exit(f"no config: {args.config} (copy clients.example.json to clients.json)")
    cfg = load_config(args.config)
    if not cfg["clients"]:
        sys.exit("clients.json has no clients")

    def log(msg):
        print(msg, flush=True)

    log(f"dumpbot: {len(cfg['clients'])} client(s){' [DRY RUN]' if args.dry_run else ''}")
    results = []
    for entry in cfg["clients"]:
        try:
            results.append(process_entry(cfg, entry, log, args.dry_run))
        except Exception as e:  # noqa: BLE001 — one client must not abort the rest
            results.append({"name": entry.get("name", "?"), "status": "FAILED", "reason": repr(e)})
            log(f"  ! error: {e!r}")

    commit_and_push(results, log, args.dry_run, push=not args.no_push)

    ok = sum(1 for r in results if r["status"] == "OK")
    failed = [r for r in results if r["status"] != "OK"]
    log(f"\nsummary: {ok} ok, {len(failed)} failed")
    for r in failed:
        log(f"  FAILED {r['name']}: {r.get('reason', '?')}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
