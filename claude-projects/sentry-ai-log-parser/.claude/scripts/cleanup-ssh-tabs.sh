#!/bin/bash
# cleanup-ssh-tabs.sh — Remove SSH tab flag files when a Claude session ends
# Triggered by Stop hook

# Read hook input to get this session's ID
input=$(cat)
session_id=$(echo "$input" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(d.get('session_id', ''))
" 2>/dev/null)

if [ -n "$session_id" ]; then
    rm -f /tmp/.claude-ssh-${session_id}-* 2>/dev/null
fi

exit 0
