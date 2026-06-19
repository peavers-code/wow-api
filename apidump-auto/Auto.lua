--[[ Peavers API Dump — Auto (dev-only, dump-server companion)
  Unattended counterpart to the manual /papidump addon. When BOTH PeaversAPIDump and this
  addon are enabled, on entering the world it runs the dump and quits the client. Quitting
  flushes SavedVariables to disk, so no /reload is needed — the dumpbot orchestrator then
  reads PeaversAPIDump.lua and regenerates build/<flavor>/<build>/.

  Enable this ONLY on the dedicated dump server (it quits the game on login). The shared
  PeaversAPIDump addon stays manual on normal machines.

  Depends on PeaversAPIDump for PeaversAPIDump_Run() (## Dependencies guarantees load order).
]]

local DUMP_DELAY = 8   -- seconds after entering world: let load-on-demand docs + world settle
local QUIT_DELAY = 3   -- seconds after dumping before Quit(), so the print/serialize finishes

local f = CreateFrame("Frame")
f:RegisterEvent("PLAYER_ENTERING_WORLD")
f:SetScript("OnEvent", function(self)
  self:UnregisterAllEvents()  -- once per session; PLAYER_ENTERING_WORLD can fire repeatedly
  C_Timer.After(DUMP_DELAY, function()
    if type(PeaversAPIDump_Run) == "function" then
      PeaversAPIDump_Run()
    else
      print("|cffff0000PAPIDump Auto|r PeaversAPIDump_Run missing — is PeaversAPIDump enabled?")
    end
    C_Timer.After(QUIT_DELAY, function() Quit() end)
  end)
end)
