-- Shared luacheck base for all Peavers WoW addons.
--
-- A per-addon .luacheckrc loads this and gets: the lua51+wow standard, the project-wide
-- ignore/exclude policy, and stds.wow (the WoW global API). It then adds only that addon's
-- own globals. Usage from an addon's .luacheckrc:
--
--   local apiDir = os.getenv("WOW_API_DIR") or "../wow-api"
--   local base = assert(loadfile(apiDir .. "/config/luacheckrc.base.lua"))(apiDir)
--   std            = base.std
--   ignore         = base.ignore
--   exclude_files  = base.exclude
--   max_line_length = false
--   codestyle      = false
--   stds.wow       = base.wow
--   globals        = { "MyAddon", "MyAddonDB", "SLASH_MYADDON1", "SlashCmdList" }
--
-- The WoW API (stds.wow) has two sources, in priority order:
--   1. <apiDir>/build/<WOW_FLAVOR>/<WOW_BUILD>/wow-globals.lua — version-accurate, generated
--      from an in-game /papidump (see scripts/gen_wow_api.py). Used when the caller sets the
--      WOW_FLAVOR + WOW_BUILD env vars (AddonSentry does, per the addon's TOC flavor).
--   2. The curated fallback below — hand-maintained; covers the common surface so linting
--      works before anyone runs a dump (and whenever WOW_BUILD is unset). Extend as needed.

local apiDir = ... or "../wow-api"

-- Which flavor + interface build's generated defs to prefer, injected by the caller via
-- the environment (AddonSentry sets both per run, per the addon's TOC flavor). FLAVOR
-- defaults to mainline; if BUILD is unset (e.g. local dev with no dump for this flavor),
-- loadWowStd falls back to the curated floor below — exactly as before any dump exists.
local FLAVOR = os.getenv("WOW_FLAVOR") or "mainline"
local BUILD = os.getenv("WOW_BUILD")

-- ---------------------------------------------------------------------------
-- Curated fallback WoW std (used when no generated wow-globals.lua is present).
-- Migrated from BetterTogether/.luacheckrc so every addon shares one curated list.
-- ---------------------------------------------------------------------------
local curated = {
  read_globals = {
    -- Lua-ish helpers WoW exposes as bare globals (on top of the 5.1 std lib)
    "wipe", "tinsert", "tremove", "tContains", "unpack",
    "strsplit", "strjoin", "strtrim", "strmatch", "strfind", "strrep",
    "strlower", "strupper", "strconcat", "gsub", "format",
    "max", "min", "abs", "floor", "ceil", "mod", "date", "time",
    "geterrorhandler", "securecall", "issecure", "issecurevariable",
    "issecretvalue",

    string = { fields = { "split", "join", "trim" } },
    table  = { fields = { "wipe", "removemulti" } },
    math   = { fields = { "huge" } },
    bit    = { fields = { "band", "bor", "bxor", "bnot", "lshift", "rshift", "arshift", "tobit", "tohex" } },

    -- Time / numbers / enums
    "GetTime", "GetTimePreciseSec", "debugprofilestop", "GetFramerate", "BreakUpLargeNumbers",
    "Enum", "C_Texture",

    -- Core frame / UI
    "CreateFrame", "UIParent", "WorldFrame", "GameTooltip", "GameTooltip_Hide",
    "UISpecialFrames", "UIFrameFadeIn", "UIFrameFadeOut", "CreateColor",
    "CreateColorFromHexString", "Mixin", "CreateFromMixins", "hooksecurefunc",
    "GetCursorPosition", "GetPhysicalScreenSize", "InCombatLockdown",
    "C_Timer", "PlaySound", "PlaySoundFile", "SOUNDKIT",
    "PanelTemplates_SelectTab", "PanelTemplates_DeselectTab", "PanelTemplates_TabResize",
    "PanelTemplates_SetNumTabs", "PanelTemplates_SetTab", "PanelTemplates_GetSelectedTab",
    -- Load-on-demand FrameXML panels/namespaces (absent from _G at dump time, so /papidump
    -- can't see them, but they're real). Curated floor recovers them under the dump.
    "ColorPickerFrame", "PlayerSpellsFrame", "ClassTalentFrame", "InspectFrame",
    "InterfaceOptionsFrame", "C_Console",

    -- Name autocomplete
    "C_AutoComplete", "GetAutoCompleteResults", "AUTOCOMPLETE_FLAG_ALL",
    "AutoCompleteEditBox_SetAutoCompleteSource", "AutoCompleteEditBox_OnTextChanged",
    "AutoCompleteEditBox_OnChar", "AutoCompleteEditBox_OnKeyDown",
    "AutoCompleteEditBox_OnKeyUp", "AutoCompleteEditBox_OnEditFocusLost",
    "AutoCompleteEditBox_OnTabPressed", "AutoCompleteEditBox_OnEnterPressed",
    "AutoCompleteEditBox_OnEscapePressed",
    "GameFontNormal", "GameFontNormalLarge", "GameFontHighlight",
    "GameFontHighlightSmall", "GameFontDisable", "GameFontDisableSmall",
    "NumberFontNormal", "InterfaceOptions_AddCategory",
    "InterfaceOptionsFrame_OpenToCategory", "Settings", "SettingsPanel",

    -- Units / group
    "UnitName", "UnitExists", "UnitClass", "UnitLevel", "UnitGUID", "UnitIsUnit",
    "UnitFullName", "UnitInParty", "UnitInRaid", "UnitIsConnected", "UnitIsPlayer",
    "UnitHealth", "UnitHealthMax", "UnitPower", "UnitPowerMax", "UnitAffectingCombat",
    "UnitStat", "UnitGetTotalAbsorbs",
    "IsInRaid", "IsInGroup", "IsInInstance", "GetNumGroupMembers", "GetNumSubgroupMembers",
    "GetRealmName", "GetNormalizedRealmName", "UnitGroupRolesAssigned",
    "GetSpecialization", "GetSpecializationInfo", "GetSpecializationInfoByID",
    "C_SpecializationInfo", "GetNumSpecializationsForClassID",
    "GetSpecializationInfoForClassID", "GetNumClasses",
    "GetLocale", "GetCVar", "SetCVar", "GetCVarBool",

    -- Stats
    "GetCritChance", "GetSpellCritChance", "GetHaste", "GetMastery", "GetMasteryEffect",
    "GetVersatilityBonus", "GetCombatRating", "GetCombatRatingBonus", "GetDodgeChance",
    "GetParryChance", "GetBlockChance", "GetAvoidance", "GetSpeed", "GetLifesteal",

    -- Class / colour
    "RAID_CLASS_COLORS", "CLASS_ICON_TCOORDS", "LOCALIZED_CLASS_NAMES_MALE",
    "LOCALIZED_CLASS_NAMES_FEMALE", "GetClassInfo", "C_ClassColor",

    -- Items / inventory / container
    "GetItemInfo", "GetItemInfoInstant", "GetItemIcon", "GetItemCount",
    "GetInventoryItemLink", "GetInventoryItemDurability", "GetInventoryItemTexture",
    "GetInventorySlotInfo", "C_Item", "Item", "C_Container", "C_TooltipInfo", "C_CurrencyInfo",
    "GetMoney", "GetCoinTextureString", "GetItemStats", "GetAverageItemLevel",
    "GetWeaponEnchantInfo", "ITEM_QUALITY_COLORS", "TooltipUtil", "C_TradeSkillUI",
    "GetDetailedItemLevelInfo", "C_AttributeUtility", "C_Attributes", "C_Stats",
    "BACKPACK_CONTAINER", "NUM_BAG_SLOTS", "NUM_TOTAL_EQUIPPED_BAG_SLOTS",
    "INVSLOT_FIRST_EQUIPPED", "INVSLOT_LAST_EQUIPPED",
    "INVSLOT_MAINHAND", "INVSLOT_OFFHAND",

    -- Auras / spells
    "AuraUtil", "C_UnitAuras", "C_Spell", "GetSpellInfo", "C_SpellBook", "C_ClassTalents",

    -- Quests
    "C_QuestLog", "C_SuperTrack", "GetQuestLink", "GetSuperTrackedQuestID",
    "C_TaskQuest", "C_QuestInfoSystem",

    -- Achievements / stats
    "GetAchievementInfo", "GetCategoryInfo", "GetStatistic", "GetComparisonStatistic",
    "C_AchievementInfo", "GetAchievementNumCriteria", "GetAchievementCriteriaInfo",
    "GetCategoryList", "GetCategoryNumAchievements", "C_DateAndTime",

    -- Map / location
    "C_Map", "GetRealZoneText", "GetSubZoneText", "GetMinimapZoneText", "IsResting",
    "GetZoneText",

    -- Mythic+ / vault
    "C_MythicPlus", "C_ChallengeMode", "C_WeeklyRewards", "C_PlayerInfo",

    -- Housing (Midnight 12.0+)
    "C_Housing", "C_HousingCatalog", "C_HousingDecor", "C_HousingLayout",
    "C_HousingNeighborhood",

    -- Modern list views / panel chrome (ScrollBox, tabs, portrait frames)
    "ScrollUtil", "CreateScrollBoxListLinearView", "CreateDataProvider",
    "ScrollBoxConstants", "PanelTemplates_SetNumTabs", "PanelTemplates_SetTab",
    "PanelTemplates_TabResize", "PanelTemplates_UpdateTabs",
    "PlaySound", "SOUNDKIT", "SetPortraitToTexture",
    "WorldMapFrame", "ToggleWorldMap", "UiMapPoint", "Mixin", "SmoothStatusBarMixin",
    "TooltipDataProcessor", "ItemRefTooltip", "StaticPopupDialogs", "StaticPopup_Show",

    -- Comm / addon
    "C_ChatInfo", "C_AddOns", "C_CVar", "GetAddOnMetadata", "RegisterAddonMessagePrefix",
    "SendAddonMessage", "Ambiguate", "ChatFrame_AddMessageEventFilter",
    "ERR_CHAT_PLAYER_NOT_FOUND_S",

    -- Misc globals occasionally referenced
    "_G", "date", "GetBuildInfo", "GetServerTime",
    "BackdropTemplateMixin", "CombatLogGetCurrentEventInfo", "StaticPopup_Show",
    "StaticPopupDialogs", "SlashCmdList",   -- writable for luacheck (base.globals); listed
                                            -- here too so the LuaLS stub gen declares it.

    -- Common localized UI strings exposed as globals
    "ACCEPT", "DECLINE", "OKAY", "CANCEL", "CLOSE", "YES", "NO",
  },
}

-- Merge the curated list UNDER the generated dump as a floor: the dump (version-accurate,
-- with strict C_* field-tables) wins on every name it defines, and curated only adds names
-- the dump missed. Crucial for load-on-demand globals (C_Stats, ClassTalentFrame, ...) that
-- aren't in _G at dump time, so /papidump can't see them but they're real APIs.
local function mergeFloor(generated, floor)
  -- Names the dump already defines: array part = plain "Name", hash part = Name = {fields}.
  local have = {}
  for k, v in pairs(generated.read_globals) do
    if type(k) == "number" then have[v] = true else have[k] = true end
  end
  local rg = generated.read_globals
  for k, v in pairs(floor.read_globals) do
    if type(k) == "number" then
      if not have[v] then rg[#rg + 1] = v; have[v] = true end   -- plain name
    else
      if not have[k] then rg[k] = v; have[k] = true end          -- Name = { fields = ... }
    end
  end
  return generated
end

-- Prefer the generated, version-accurate std (merged with the curated floor); else curated.
-- Guarded so a missing file / sandboxed loadfile silently keeps the fallback working.
local function loadWowStd()
  if not BUILD then return curated end
  local path = apiDir .. "/build/" .. FLAVOR .. "/" .. BUILD .. "/wow-globals.lua"
  local f = loadfile and loadfile(path)
  if f then
    local ok, res = pcall(f)
    if ok and type(res) == "table" and res.read_globals then
      return mergeFloor(res, curated)
    end
  end
  return curated
end

local wow = loadWowStd()

-- Dumper blind-spots: real APIs that /papidump can't enumerate, force-added on top of
-- whichever std won. Either absent from _G at dump time (CombatLogGetCurrentEventInfo),
-- or exposed through a metatable so pairs() sees no fields (TooltipUtil's mixin methods
-- -> make it lenient instead of a strict field set).
do
  local rg = wow.read_globals
  rg[#rg + 1] = "CombatLogGetCurrentEventInfo"
  rg.TooltipUtil = nil          -- drop any field-less strict entry from the dump
  rg[#rg + 1] = "TooltipUtil"   -- re-add as a plain global: any field allowed

  -- Peavers ecosystem globals shared across all addons (not WoW API, so not in the dump;
  -- added here so every addon can read the framework, embedded Ace3 locator, the shared
  -- SavedVariables, and the data-addon tables consumed cross-addon.
  for _, name in ipairs({
    "LibStub", "PeaversCommons", "PeaversCommonsDB",
    "PeaversTalentsData", "PeaversCurrencyData", "PeaversBestInSlotData",
    "PeaversConsumablesData",
  }) do rg[#rg + 1] = name end
end

return {
  std     = "lua51+wow",
  wow     = wow,
  -- Globals an addon defines at the top level of any of its files are auto-allowed, so
  -- each addon's public table / SLASH_* commands need no per-addon declaration. This only
  -- loosens *assignment*-side checks; *access* to undefined WoW API (113) stays strict —
  -- which is the whole point. Keeps per-addon .luacheckrc tiny across all 16 addons.
  allow_defined_top = true,
  -- Writable globals every addon shares. The cross-addon changelog registry is appended
  -- to by each addon's Changelog.lua; SlashCmdList gets per-addon command fields assigned;
  -- StaticPopupDialogs gets per-addon dialog tables registered into it (the /papidump
  -- captures it as a strict read-only table, so writes need it declared writable here).
  -- Per-addon .luacheckrc merges its own globals on top of these.
  globals = { "PeaversChangelogs", "SlashCmdList", "StaticPopupDialogs" },
  -- Warnings accepted project-wide. We deliberately KEEP 113 (undefined global) and
  -- 143 (undefined field) ON — those catch API typos, which is the whole point.
  ignore  = {
    "212",            -- unused argument (WoW event/callback signatures often ignore args)
    "213",            -- unused loop variable
    "542",            -- empty if branch (intentional no-op placeholders)
    "211/addonName",  -- `local addonName, ns = ...` header idiom
    "131/SLASH_.*",   -- SLASH_<CMD><N> globals are read by the WoW engine, not Lua, so
                      -- 131 (unused global) is always a false positive on them
    "111/SLASH_.*",   -- ...and when SLASH_* are assigned inside a callback (not at top
                      -- level) allow_defined_top doesn't cover them, so 111 fires instead
    "611", "612",     -- whitespace-only / trailing-whitespace lines (style, not bugs)
    "613", "614",     -- trailing whitespace in string/comment
    -- KEEP ON: 11x (undefined/setting globals — WoW API typos), 211/231 (unused),
    -- 4xx (shadowing/redefining locals) — those are the findings worth a PR comment.
  },
  exclude = {
    "tools/",
    ".release/",
    "**/Libs/**",
    "**/libs/**",
    "**/Templates/**",   -- scaffolding with YourAddon/YourAddonName placeholders, not real code
  },
}
