# wow-api — shared WoW API validation for Peavers addons

One place that holds the **WoW client API definitions** and the **tooling** that validates
every Peavers addon's Lua against them. Three layers of confidence without launching the game:

| Layer | Catches | Tool | Source of truth |
|---|---|---|---|
| **Existence** | syntax errors, undefined globals, `C_*`/`Enum` field typos | luacheck | `build/<BUILD>/wow-globals.lua` (from `/papidump`) + curated fallback |
| **Signatures** | wrong arg/return types, undefined fields, nil-safety | lua-language-server | `vendor/ketho` (community) + `build/<BUILD>/luals` (build-exact) |
| **Namespace** | globally-named frames that leak into `_G` | `ci/check_frame_names.py` | the addon's own name + optional `.wowlint.json` |

### Being a good `_G` citizen

Addons share one global namespace, and a colliding name breaks whichever addon loads second.
Two rules, each enforced by a different layer, because neither catches the other's vector:

- **Assignments** — `luacheckrc.base.lua` sets `allow_defined_top = false`, so every global an
  addon creates must be declared in its `.luacheckrc`. That list is the addon's documented `_G`
  footprint; keep it short. Prefer the `local addonName, NS = ...` private table.
- **Frame names** — `CreateFrame("Frame", "Name", ...)` writes `Name` into `_G` at *runtime*,
  where no static analysis can see it, which is why it gets its own tier. Naming a *templated*
  frame is worse: WoW also creates a global per named child, so one call can mint 30 globals.
  Pass `nil` and hold the frame in a local unless something outside Lua resolves it by string
  (Bindings.xml, an XML `inherits`/`parentKey`, or a documented integration point).

Addons using a short alias declare it once beside the TOC:

```json
{ "framePrefixes": ["PDS_"] }
```

The API surface is **hybrid**: Ketho's community annotations give rich signatures for the
broad API; our in-game `/papidump` overlays build-exact existence and any private/undocumented
globals our addons actually use. Both are pinned to a client build (currently `120007`).

## Layout

```
wow-api/
  apidump/              PeaversAPIDump — dev-only in-game dumper (/papidump)
  vendor/ketho/         vendored Ketho/vscode-wow-api Annotations/Core (pinned, see VENDOR.md)
  build/<BUILD>/        generated, committed per client build
    wow-globals.lua       luacheck stds.wow
    luals/wow-api.lua     LuaLS signatures (from APIDocumentation)
    luals/wow-globals.lua LuaLS `any` existence stubs
  config/
    luacheckrc.base.lua   shared luacheck base (std, ignore, curated fallback) — addons extend
    luarc.base.json       shared LuaLS config base — addons mirror
  scripts/
    gen_wow_api.py        /papidump  -> build/<BUILD>/wow-globals.lua
    gen_luals_defs.py     /papidump  -> build/<BUILD>/luals/*
    lint.sh               run luacheck (existence) for an addon
    lsp_check.sh          run lua-language-server (signatures) for an addon
    check_frame_names.py  (in ci/) run the namespace tier for an addon
  peavers-commons.lua   LuaLS def for the PeaversCommons framework (cross-addon)
```

## Using it from an addon

Each addon has a thin `.luacheckrc` and `.luarc.json` that point here (default `../wow-api`,
override with `WOW_API_DIR`). See `BetterTogether/.luacheckrc` for the reference pattern.

```bash
cd SomeAddon
../wow-api/scripts/lint.sh          # luacheck: existence
../wow-api/scripts/lsp_check.sh     # LuaLS: signatures
```

Requires `luacheck` and `lua-language-server` on PATH:
`brew install luacheck lua-language-server` (macOS) — both are also fetched by the CI workflow.

## Refreshing the API when the client patches

This is the "update the dump when the game changes" workflow:

1. In-game: enable **Peavers API Dump** at character-select (install `apidump/` as the addon
   `PeaversAPIDump`), run `/papidump`, then `/reload` (WoW flushes SavedVariables on reload).
2. Regenerate:
   ```bash
   python3 scripts/gen_wow_api.py      # -> build/<newBUILD>/wow-globals.lua
   python3 scripts/gen_luals_defs.py   # -> build/<newBUILD>/luals/*
   ```
   The scripts auto-locate the newest `PeaversAPIDump.lua` SavedVariables across common WoW
   install paths (macOS/Windows); pass `--sv PATH` or `--wow-root DIR` to override.
3. Refresh the vendored Ketho annotations to match the patch (re-clone, copy `Annotations/Core`,
   update `vendor/ketho/VENDOR.md`).
4. Bump `BUILD` in `config/luacheckrc.base.lua` and the `build/<BUILD>` path in
   `config/luarc.base.json` (and each addon's `.luarc.json`). Commit the new `build/<BUILD>/`.
   Old builds stay for addons still on a prior Interface version.

## Limitations

- luacheck validates **existence**, not call correctness — the everyday gate. Field typos on
  `C_*` namespaces are only caught when `build/<BUILD>/wow-globals.lua` exists (the curated
  fallback declares `C_Timer` etc. leniently). LuaLS + Ketho catches those via `undefined-field`.
- LuaLS is happiest **live in an editor** (hovers, autocomplete, signature help). The headless
  `--check` form is for CI/spot checks and can be noisy on untyped cross-file `ns` tables.
- `CombatLogGetCurrentEventInfo` isn't in `_G` at dump time, so it's whitelisted by hand in
  both `config/luacheckrc.base.lua` and `config/luarc.base.json`.
