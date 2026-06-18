# build/ — generated, flavor- and build-tagged API definitions

Each `build/<FLAVOR>/<INTERFACE>/` holds the defs generated from an in-game `/papidump` for
that WoW edition + client build. **Committed** so addons and CI validate without a live client.

`<FLAVOR>` is one of `mainline` (retail), `era` (Classic Era / Vanilla), `mists` (MoP
Classic), `cata`, `wrath`, `tbc` — see `../config/flavors.json`. The flavor is derived from
the dump's in-game `WOW_PROJECT_ID`, so each client sorts itself into the right directory.

    build/mainline/120007/
      wow-globals.lua        luacheck stds.wow (existence + C_*/Enum field checking)
      luals/wow-api.lua       LuaLS signatures (from APIDocumentation)
      luals/wow-globals.lua   LuaLS `any` existence stubs
    build/era/11507/...       (same layout, from a Classic Era /papidump)
    build/mists/50500/...     (same layout, from a MoP Classic /papidump)

Old builds within a flavor stay for addons still pinned to a prior Interface version;
"newest build within a flavor" (highest interface number) wins, which also naturally
prefers a PTR/Beta build when one is published under that flavor.

Populate per client (run /papidump + /reload in each, then once per dump):
    python3 ../scripts/gen_wow_api.py  &&  python3 ../scripts/gen_luals_defs.py
Force the flavor with `--flavor era` if the dump's projectId can't be mapped. Until a flavor
has a dump, validation falls back to the curated list in config/luacheckrc.base.lua +
config/curated-globals.lua. See ../README.md.
