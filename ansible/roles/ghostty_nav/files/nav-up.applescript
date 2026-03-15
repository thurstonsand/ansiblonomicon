tell application "Ghostty"
	set t to focused terminal of selected tab of front window
	if name of t starts with (character id 8203) then
		tell application "System Events" to keystroke "k" using control down
	else
		perform action "goto_split:up" on t
	end if
end tell
