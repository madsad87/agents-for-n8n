#!/bin/bash
# open-ssh-tab.sh — Auto-open iTerm2 SSH tab on first pod connection
# Triggered by PostToolUse hook on Bash tool calls containing SSH commands

# Read hook input from stdin
input=$(cat)

# Extract command and session_id from the JSON input
eval "$(echo "$input" | python3 -c "
import sys, json
d = json.load(sys.stdin)
cmd = d.get('tool_input', {}).get('command', '')
sid = d.get('session_id', '')
print(f'command={repr(cmd)}')
print(f'session_id={repr(sid)}')
" 2>/dev/null)"

# Check if this is an SSH command to a WPE pod
pod_host=$(echo "$command" | grep -oE 'pod-[0-9]+\.wpengine\.com' | head -1)

if [ -z "$pod_host" ]; then
    exit 0
fi

pod_id=$(echo "$pod_host" | grep -oE 'pod-[0-9]+')
flag_file="/tmp/.claude-ssh-${session_id}-${pod_id}"

# Only open once per pod per session
if [ -f "$flag_file" ]; then
    exit 0
fi

touch "$flag_file"

# Open new iTerm2 tab, SSH in, then run factfind after connection establishes
osascript -e "
tell application \"iTerm2\"
    tell current window
        create tab with default profile
        tell current session
            write text \"gogo ${pod_host}\"
            delay 5
            write text \"factfind\"
        end tell
    end tell
end tell
" 2>/dev/null

exit 0
