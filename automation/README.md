# dumpbot — automated daily multi-flavor API dumper

Unattended daily job for a dedicated Windows dump server. Per configured client it launches the
game, drives it past login → character select → in-world, the **apidump-auto** addon dumps the live
API and quits (flushing SavedVariables), then the generators regenerate `build/<flavor>/<build>/`
and the job commits + pushes the changes to the `wow-api` repo.

This keeps every flavor's API defs current without anyone running `/papidump` by hand.

> ⚠️ **Blizzard ToS:** automating the client with synthetic input violates the WoW Terms of Service.
> This is development tooling for your own accounts — run it at your own risk on a dedicated,
> non-primary account.

## Pieces

| File | Role |
|------|------|
| `dumpbot.py` | Orchestrator: loop clients → launch → navigate → wait for fresh dump → generate → commit/push |
| `navigate.ahk` | AutoHotkey v2 script: clicks through login → char select → Enter World |
| `clients.example.json` | Template config; copy to `clients.json` (gitignored, machine-specific) |
| `run-daily.ps1` | Task Scheduler wrapper (runs dumpbot, tees a dated log to `logs/`) |
| `../apidump/` | The `PeaversAPIDump` addon (`/papidump` + `PeaversAPIDump_Run()`) |
| `../apidump-auto/` | The `PeaversAPIDumpAuto` companion: dumps on login then `Quit()`s |

## One-time server setup

1. **Install the clients** you want to cover (Retail, Classic Era, current Classic progression).
   Note: Battle.net typically only lets Retail + Classic Era + the *current* progression coexist;
   PTR/Beta are separate installs. dumpbot covers whatever you list in `clients.json`.
2. **Install both addons** into *each* client's `Interface\AddOns\`:
   - copy `wow-api\apidump\` → `…\Interface\AddOns\PeaversAPIDump\`
   - copy `wow-api\apidump-auto\` → `…\Interface\AddOns\PeaversAPIDumpAuto\`
   - enable **both** at the character-select AddOns screen, and tick **"Load out of date AddOns"**.
   - ⚠️ Only do this on the dump server — `PeaversAPIDumpAuto` quits the game on login.
3. **Save Battle.net login** ("Remember Me") and **log into each client once**, picking the character
   you want, so "Enter World" targets the last character automatically.
4. **Install** [AutoHotkey v2](https://www.autohotkey.com/) and Python 3, plus this repo's git remote
   with push auth (a PAT in the remote URL or Windows Git Credential Manager) so `git push` is
   non-interactive.
5. **Configure** `clients.json` — copy `clients.example.json`, fix the exe paths / install roots, and
   tune each client's `navigate` waits (`login_wait`, `char_wait`, `enters`) for this machine.

## Run it

```
python automation\dumpbot.py            # full run: launch, generate, commit, push
python automation\dumpbot.py --dry-run  # no launch/push: generate from existing SVs, show the commit
python automation\dumpbot.py --no-push  # generate + commit locally, skip push
```

`--dry-run` is the safe way to validate config and the generate/commit logic without launching a
client (it leaves the git index clean and never pushes).

## Schedule (Windows Task Scheduler)

Create a daily task that runs:

```
powershell -ExecutionPolicy Bypass -File C:\path\to\wow-api\automation\run-daily.ps1
```

- Trigger: daily, off-peak (avoid patch-day login queues if you can).
- Run **whether the user is logged on or not**, **but** input automation needs a real interactive
  desktop — use an auto-logon kiosk account and keep the session unlocked, or run the task in that
  user's logged-in session. A locked/headless session will make `navigate.ahk` send keystrokes to
  nothing and the run will time out (logged as FAILED, no commit).

## How it stays safe

- **Stale-guard:** dumpbot records each client's SavedVariables mtime before launch and only proceeds
  if it advances — a client stuck at login/queue is marked FAILED and *that flavor is left untouched*,
  so a bad run never overwrites good committed defs.
- **Per-flavor staging:** only flavors that dumped successfully are `git add`ed; the commit message
  lists exactly what refreshed (e.g. `chore(build): refresh defs mainline=120010 era=11508 [dumpbot]`).
- **Logs + exit code:** every run writes `logs/dumpbot_<stamp>.log` and exits non-zero if any client
  failed — wire that to an alert if you want to be notified.

## Note: AddonSentry does not see new defs immediately

The AddonSentry worker bakes `build/` into its image (`COPY wow-api /opt/wow-api`). Pushing fresh defs
to git updates the source of truth, but a running worker only picks them up on its next image rebuild
/ deploy (or once the S3-refresh mechanism the Dockerfile describes is implemented). See the plan's
"Part D" follow-up.
