---
name: modify
description: Start an interactive modification session for a WordPress directory — iterate on changes conversationally with git commits per step and a single versioned zip on completion
usage: /modify {path} ["modification text"] [--visual ./path/]
modes:
  - nl (default): Natural language modification
  - visual: Updated design export for theme re-generation
---

# Modify Command

Start an interactive modification session for a WordPress directory. Users iterate on changes one at a time — each modification is git-committed immediately for rollback granularity. No zip is produced until the user confirms they are done, at which point a versioned output folder and zip are created.

## Section 0: Command Overview

**Usage patterns:**

```
/modify ./my-wp-site                                                        — start session, prompt for first modification
/modify ./my-wp-site "change the primary color to forest green"             — execute as first step, then continue session
/modify ./my-wp-site "change the color to green and add a blog page"        — compound NL (auto-decomposed), then continue
/modify ./my-wp-site --visual ./updated-export/                             — visual re-export as first step, then continue
```

**Prerequisites:**
- A local directory containing a WordPress installation (any source — /build output, Local WP, manual install, etc.)
- Docker available (started lazily — only when a content or plugin step is detected)
- WP-CLI available (local or Docker fallback — checked lazily)

**How it works:**
1. Parse arguments to determine WordPress directory path and optional first step
2. Validate the WordPress directory (wp-content/ must exist)
3. Initialize session — load state, print session banner
4. Execute first step if inline text or --visual was provided
5. Enter prompt loop — ask what to change next after each step
6. When user says "done", produce versioned output folder + zip and end session

## Section 1: Argument Parsing

Parse all arguments to extract the WordPress directory path, detect an optional first step, and validate inputs.

```bash
INPUT="$@"

# ── Extract WP_DIR (first positional argument — required) ────────────────────

WP_DIR=""
NL_REQUEST=""
VISUAL_PATH=""
MODIFY_MODE=""
FIRST_STEP_REQUEST=""
FIRST_STEP_VISUAL=""

# First word is the WordPress directory path, rest is the request or flags
WP_DIR=$(echo "$INPUT" | awk '{print $1}')
REMAINING=$(echo "$INPUT" | cut -d' ' -f2-)

# ── Validate WP_DIR ─────────────────────────────────────────────────────────

if [ -z "$WP_DIR" ]; then
  echo ""
  echo "ERROR: WordPress directory path is required."
  echo ""
  echo "Usage:"
  echo "  /modify ./my-wp-site                                    — start session"
  echo "  /modify ./my-wp-site \"change the primary color\"         — with first step"
  echo "  /modify ./my-wp-site --visual ./updated-export/          — visual first step"
  echo ""
  echo "The path can be any local WordPress directory — /build output, Local WP site, manual install, etc."
  echo ""
  exit 1
fi

if [ ! -d "$WP_DIR" ]; then
  echo ""
  echo "ERROR: Directory does not exist: $WP_DIR"
  echo ""
  echo "Please provide a valid path to a WordPress directory."
  echo ""
  exit 1
fi

if [ ! -d "$WP_DIR/wp-content" ]; then
  echo ""
  echo "ERROR: The directory at $WP_DIR does not appear to be a WordPress installation — wp-content/ was not found."
  echo ""
  echo "Please provide a path to a directory containing wp-content/."
  echo ""
  exit 1
fi

# ── Detect optional first step ───────────────────────────────────────────────

if echo "$REMAINING" | grep -qE "\-\-visual[[:space:]]"; then
  FIRST_STEP_VISUAL=$(echo "$REMAINING" | sed 's/.*--visual[[:space:]]*\([^ ]*\).*/\1/')
  if [ ! -d "$FIRST_STEP_VISUAL" ]; then
    echo ""
    echo "ERROR: Visual path does not exist or is not a directory: $FIRST_STEP_VISUAL"
    echo ""
    echo "Usage: /modify ./my-wp-site --visual ./updated-export/"
    echo ""
    exit 1
  fi
elif echo "$REMAINING" | grep -qE "^\-\-visual$"; then
  echo ""
  echo "ERROR: --visual requires a path to the updated design export directory."
  echo ""
  echo "Usage: /modify ./my-wp-site --visual ./updated-export/"
  echo ""
  exit 1
elif [ -n "$REMAINING" ] && [ "$REMAINING" != "$WP_DIR" ]; then
  # Inline text provided — treat as first step NL request
  FIRST_STEP_REQUEST="$REMAINING"
fi

# ── Print parsed inputs ─────────────────────────────────────────────────────

echo "[Modify] WordPress directory: $WP_DIR"
if [ -n "$FIRST_STEP_REQUEST" ]; then
  echo "[Modify] First step: $FIRST_STEP_REQUEST"
elif [ -n "$FIRST_STEP_VISUAL" ]; then
  echo "[Modify] First step: visual re-export from $FIRST_STEP_VISUAL"
else
  echo "[Modify] No first step — will prompt for first modification"
fi
echo ""
```

## Section 2: Session Loop

Initialize the session, execute the optional first step, then enter the interactive prompt loop. COMMAND.md owns the conversation; the build-modify skill (SKILL.md) owns per-step execution.

```
Session initialization:

1. Invoke build-modify SKILL.md Section 0 (prerequisites — lazy Docker, git helper, EXIT trap)
   and Section 1 (WordPress directory validation, build.json load/create, git init if needed)
   once at session start.

2. Print session banner:

   ════════════════════════════════════════════════════════════════════════════

   Modification session started for: {WP_DIR}

   Theme: {THEME_SLUG}  |  Existing modifications: {EXISTING_MODS}

   Describe what you'd like to change. Each modification is applied and
   git-committed immediately. Say "done" when you're finished and a
   versioned output folder + zip will be produced.

   ════════════════════════════════════════════════════════════════════════════

3. If FIRST_STEP_REQUEST is set:
   - Set NL_REQUEST=FIRST_STEP_REQUEST, MODIFY_MODE="nl"
   - Execute via SKILL.md Sections 2 → 3 → 4 (decompose, execute, finalize per step)

4. If FIRST_STEP_VISUAL is set:
   - Set VISUAL_PATH=FIRST_STEP_VISUAL, MODIFY_MODE="visual"
   - Execute via SKILL.md Section 5 → Section 4 (visual re-export + finalize)

5. Enter prompt loop (or go directly to prompt loop if no first step):

PROMPT LOOP:

  After each completed step, SKILL.md Section 4c prints a per-step summary
  (files changed, step type, git commit hash, description).

  Claude prompts: "What would you like to change next? (or say 'done' to finish)"

  User responds with one of:

  a) DONE INTENT — user says "done", "that's it", "finished", "I'm done",
     "all good", "that's all", "nothing else", or equivalent.
     → Exit loop, proceed to Section 3 (Completion).
     NOTE: Use judgment to distinguish done intent from modification requests
     that mention the word "done" (e.g., "change the Done button color" is
     a modification, NOT a done signal).

  b) VISUAL STEP — user input contains "--visual ./path/" flag, or natural
     language like "apply the design from ./export/", "use the updated
     mockup at ./path/", "re-export the visual from ./designs/".
     → Extract the visual path from user input
     → Set VISUAL_PATH, MODIFY_MODE="visual"
     → Execute via SKILL.md Section 5 → Section 4
     → Loop back to prompt

  c) NL MODIFICATION — any other text input.
     → Set NL_REQUEST to the user's input, MODIFY_MODE="nl"
     → Execute via SKILL.md Sections 2 → 3 → 4
     → Compound requests are auto-decomposed into atomic steps (each
       gets its own git commit) within a single turn
     → Loop back to prompt

Variable contract per step:
  - WP_DIR: set once at session start, never changes
  - BUILD_DIR: derived from WP_DIR in SKILL.md Section 1, set once
  - MODIFY_MODE: set per step ("nl" or "visual")
  - NL_REQUEST: set per NL step by the session loop
  - VISUAL_PATH: set per visual step by the session loop
```

## Section 3: Completion

When the user signals done, produce the versioned output and end the session.

```
Completion flow:

1. Invoke SKILL.md Section 7 (Session Completion):
   - Regenerate SETUP.md (once, reflecting final state)
   - Copy BUILD_DIR to versioned sibling directory ({wp-dir}-v{N}/)
   - Zip the versioned copy
   - Print full session summary (all steps, git log, output paths)

2. The session is over. No further prompts.
```

## Section 4: Implementation Notes

- **COMMAND.md owns the conversation, SKILL.md owns execution** — the session loop lives here, per-step execution logic lives in the skill
- Both modification modes work on ANY WordPress directory — /build output, Local WP site, manual install, or any other source
- External directories may not have build.json; the skill handles this gracefully (creates one)
- Compound NL requests within a single turn are still auto-decomposed into atomic steps by the skill — each gets its own git commit
- Docker/MySQL uses lazy startup — only checked and started when a content or plugin step is detected. Theme-only sessions work without Docker entirely.
- No zip is produced between steps — git commits provide rollback granularity. A single versioned zip is produced at completion.
- SETUP.md is regenerated once at completion, not per-step
- The original WordPress directory is preserved (copied to versioned output, not moved) so the user can re-run /modify on it later

## Success Criteria

- `/modify ./my-wp-site` starts a session and prompts for the first modification
- `/modify ./my-wp-site "change the primary color"` executes as first step, then prompts for next
- `/modify ./my-wp-site --visual ./updated-export/` executes visual as first step, then continues session
- After each step, user is asked what to change next
- User saying "done" produces versioned output folder + zip and ends the session
- `--visual` works mid-session alongside NL modifications
- Missing path produces a clear usage error
- Non-existent path produces a clear error
- Missing wp-content/ produces a clear halt with explanation
