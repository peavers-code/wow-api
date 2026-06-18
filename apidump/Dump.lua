--[[ Peavers API Dump (dev-only)
  A throwaway tool that snapshots the *live* client API so our static analysis matches
  the exact game build, instead of a hand-maintained guess. NOT shipped with any addon.

  Promoted from BetterTogether/tools/apidump so every Peavers addon shares one dumper.

  Usage in-game:
    1. Enable "Peavers API Dump" at the character-select AddOns screen.
       (Ideally disable other addons first, so their globals don't leak into the dump.)
    2. /papidump
    3. /reload   (WoW only flushes SavedVariables to disk on reload/logout)
    4. Back in the repo: python3 wow-api/scripts/gen_wow_api.py   (luacheck globals)
                         python3 wow-api/scripts/gen_luals_defs.py (LuaLS signatures)

  Multi-flavor: each WoW edition (retail, Classic Era, MoP Classic, ...) ships its own
  API surface, so run the above once PER CLIENT. The sibling TOCs (PeaversAPIDump_Vanilla,
  _Mists, _Cata, _Wrath) let this addon load on each client; the dump records WOW_PROJECT_ID
  so the generators sort the output under build/<FLAVOR>/<BUILD>/ automatically.

  Two products land in SavedVariables (PeaversAPIDumpDB):
    .globals  — newline-joined identifiers: top-level globals plus one level of fields
                for C_*/Enum/*Util/*Mixin/SOUNDKIT namespaces. Feeds luacheck (existence).
    .emmylua  — an EmmyLua/LuaLS annotation file (as text) built from APIDocumentation:
                function stubs with @param/@return. Feeds the Lua Language Server.
  Both are quote-free text so they serialize with only \n escapes (trivial to extract).
]]

-- ---------------------------------------------------------------------------
-- 1. Global identifier list (for luacheck existence checking)
-- ---------------------------------------------------------------------------
local IDENT = "^[%a_][%w_]*$"

-- Namespaces we descend one level into so luacheck can catch field typos
-- (e.g. C_Timer.Aftr). Plain global tables stay lenient (any field allowed).
local function descend(name)
  return name:match("^C_")
      or name == "Enum" or name == "Constants" or name == "SOUNDKIT"
      or name:match("Util$") or name:match("Mixin$")
end

local function collectGlobals()
  local out = {}
  for k, v in pairs(_G) do
    if type(k) == "string" and k:match(IDENT) then
      out[#out + 1] = k
      if type(v) == "table" and descend(k) then
        -- pcall: a few engine tables are protected and error on iteration.
        pcall(function()
          for fk in pairs(v) do
            if type(fk) == "string" and fk:match(IDENT) then
              out[#out + 1] = k .. "." .. fk
            end
          end
        end)
      end
    end
  end
  table.sort(out)
  return table.concat(out, "\n")
end

-- ---------------------------------------------------------------------------
-- 2. EmmyLua annotations from APIDocumentation (for LuaLS signature checking)
-- ---------------------------------------------------------------------------
-- WoW documentation type -> Lua type. Anything unmapped becomes `any` so LuaLS
-- doesn't flag thousands of "undefined type" notes for engine-specific classes.
local TYPE_MAP = {
  bool = "boolean", boolean = "boolean",
  cstring = "string", string = "string", luaString = "string",
  number = "number", luaIndex = "number", luaNumber = "number",
  table = "table", luaTable = "table",
  ["function"] = "function", luaFunction = "function",
  luaValue = "any",
}
local function mapType(t)
  if not t then return "any" end
  return TYPE_MAP[t] or "any"
end

local function sanitize(name, i)
  if type(name) ~= "string" or not name:match(IDENT) then return "arg" .. i end
  -- avoid Lua reserved words as parameter names
  local reserved = { ["end"] = true, ["function"] = true, ["local"] = true,
    ["true"] = true, ["false"] = true, ["nil"] = true, ["and"] = true,
    ["or"] = true, ["not"] = true, ["if"] = true, ["then"] = true,
    ["else"] = true, ["for"] = true, ["in"] = true, ["do"] = true,
    ["while"] = true, ["repeat"] = true, ["return"] = true }
  if reserved[name] then return name .. "_" end
  return name
end

local function collectEmmy()
  local lines = { "---@meta", "-- Generated from in-game APIDocumentation. Do not edit." }
  if type(APIDocumentation) ~= "table" or type(APIDocumentation.systems) ~= "table" then
    lines[#lines + 1] = "-- APIDocumentation unavailable (is Blizzard_APIDocumentation loaded? try /api)."
    return table.concat(lines, "\n")
  end

  local nsSeen = {}
  local body = {}
  for _, sys in ipairs(APIDocumentation.systems) do
    local ns = sys.Namespace
    if type(ns) == "string" and ns:match(IDENT) and not nsSeen[ns] then
      nsSeen[ns] = true
      lines[#lines + 1] = ns .. " = {}"
    end
    for _, fn in ipairs(sys.Functions or {}) do
      if type(fn) == "table" and type(fn.Name) == "string" and fn.Name:match(IDENT) then
        local args = {}
        for i, a in ipairs(fn.Arguments or {}) do
          local an = sanitize(a.Name, i)
          args[#args + 1] = an
          body[#body + 1] = "---@param " .. an .. (a.Nilable and "?" or "") .. " " .. mapType(a.Type)
        end
        for i, r in ipairs(fn.Returns or {}) do
          body[#body + 1] = "---@return " .. mapType(r.Type) .. " " .. sanitize(r.Name, i)
        end
        local full = (ns and ns ~= "") and (ns .. "." .. fn.Name) or fn.Name
        body[#body + 1] = "function " .. full .. "(" .. table.concat(args, ", ") .. ") end"
      end
    end
  end

  for _, l in ipairs(body) do lines[#lines + 1] = l end
  return table.concat(lines, "\n")
end

-- ---------------------------------------------------------------------------
local function loadAddon(name)
  if C_AddOns and C_AddOns.LoadAddOn then return pcall(C_AddOns.LoadAddOn, name) end
  if LoadAddOn then return pcall(LoadAddOn, name) end
  return false
end

-- The signature data is empty unless the docs are loaded. The framework lives in
-- Blizzard_APIDocumentation, but the actual API tables are registered by the (huge,
-- load-on-demand) Blizzard_APIDocumentationGenerated addon — the same thing /api pulls
-- in. APIDocumentation_LoadUI() is Blizzard's canonical loader; fall back to direct loads.
local function ensureDocs()
  if APIDocumentation_LoadUI then pcall(APIDocumentation_LoadUI) end
  loadAddon("Blizzard_APIDocumentation")
  loadAddon("Blizzard_APIDocumentationGenerated")
end

SLASH_PAPIDUMP1 = "/papidump"
SlashCmdList["PAPIDUMP"] = function()
  ensureDocs()
  local sysCount = (type(APIDocumentation) == "table" and type(APIDocumentation.systems) == "table")
    and #APIDocumentation.systems or 0
  print("|cff00ff00PAPIDump|r APIDocumentation: "
    .. (type(APIDocumentation) == "table" and "present" or "MISSING")
    .. ", systems = " .. sysCount)
  local major, _, _, interface = GetBuildInfo()
  -- WOW_PROJECT_ID is the authoritative flavor signal (mainline/era/mists/...). The
  -- generators map this numeric id to a flavor via config/flavors.json, so capture it
  -- raw rather than mapping in-Lua (keeps one mapping table). May be nil on very old
  -- clients; fall back to the interface-number range there.
  local projectId = WOW_PROJECT_ID
  local globals = collectGlobals()
  local emmy = collectEmmy()
  PeaversAPIDumpDB = {
    build = tostring(major) .. " interface " .. tostring(interface),
    projectId = tostring(projectId),
    globalCount = select(2, globals:gsub("\n", "\n")) + 1,
    globals = globals,
    emmylua = emmy,
  }
  print("|cff00ff00PAPIDump|r captured "
    .. PeaversAPIDumpDB.globalCount .. " globals + "
    .. select(2, emmy:gsub("\nfunction ", "")) .. " documented functions for build "
    .. PeaversAPIDumpDB.build .. " (WOW_PROJECT_ID " .. PeaversAPIDumpDB.projectId .. ").")
  print("Now type |cffffff00/reload|r to flush it to SavedVariables, then run the generators.")
end
