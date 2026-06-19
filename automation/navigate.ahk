; navigate.ahk — drive a freshly-launched WoW client past login -> character select -> in-world
; so the apidump-auto addon can dump and quit. AutoHotkey v2.
;
; Assumes Battle.net is running and logged in with credentials saved ("Remember Me"), and a
; character has been selected once on this client so "Enter World" targets the last character.
;
; Args (passed by dumpbot.py from each client's "navigate" config):
;   1 login_wait   seconds to wait after the window appears before the first Enter (login/realm)
;   2 char_wait    seconds to wait at character select before pressing Enter (Enter World)
;   3 enters       how many Enter presses to send at each step (default 2, for extra prompts)
;   4 window_title window title to wait for (default "World of Warcraft")
;
; These are deliberately generous, dumb waits + key presses — the most robust approach against
; queues/patch-day prompts is long timeouts and a couple of extra Enters, not tight UI scraping.
; Tune the per-client values in clients.json for your machine.

login_wait := A_Args.Length >= 1 ? Integer(A_Args[1]) : 25
char_wait  := A_Args.Length >= 2 ? Integer(A_Args[2]) : 15
enters     := A_Args.Length >= 3 ? Integer(A_Args[3]) : 2
title      := A_Args.Length >= 4 ? A_Args[4] : "World of Warcraft"

if !WinWait(title, , 120) {
    ExitApp 1   ; window never appeared
}
WinActivate title

Sleep login_wait * 1000
Loop enters {
    WinActivate title
    Send "{Enter}"
    Sleep 1500
}

Sleep char_wait * 1000
Loop enters {
    WinActivate title
    Send "{Enter}"
    Sleep 1500
}

ExitApp 0
