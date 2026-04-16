---
name: build
description: Build a WordPress site from scratch — blank install, natural language, visual design, or URL clone
usage: /build [--blank] [--visual ./path/] [--from-url https://...] ["description text"]
modes:
  - blank: Empty WordPress installation with default theme
  - nl (default): Natural language site description
  - visual: Structured design export or screenshot image
  - url: URL clone from scraped site
---

# Build Command

Generate a complete WordPress site packaged as a Local WP importable zip. Supports four creation modes: blank install (fully functional), natural language (default), visual design, and URL clone (Playwright scrape of a live site). The command validates prerequisites, detects the requested mode from input, and routes to the appropriate build pipeline.

## Section 0: Prerequisite Validation

Check Docker and WP-CLI are available before attempting any build work.

```bash
# Check Docker is running
if ! docker info > /dev/null 2>&1; then
  echo ""
  echo "ERROR: Docker is required for /build."
  echo ""
  echo "Start Docker Desktop and try again."
  echo ""
  exit 1
fi

# Check WP-CLI — local first, Docker fallback
if which wp > /dev/null 2>&1; then
  WP_CLI_AVAILABLE=true
  WP_CLI_SOURCE="local"
elif docker run --rm wordpress:cli wp --version > /dev/null 2>&1; then
  WP_CLI_AVAILABLE=true
  WP_CLI_SOURCE="docker"
else
  echo ""
  echo "ERROR: WP-CLI is required for /build but was not found."
  echo ""
  echo "Install WP-CLI:"
  echo "  curl -O https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar"
  echo "  chmod +x wp-cli.phar"
  echo "  sudo mv wp-cli.phar /usr/local/bin/wp"
  echo ""
  echo "Full instructions: https://wp-cli.org"
  echo ""
  exit 1
fi

echo "[Build] Prerequisites OK — Docker ✓, WP-CLI ✓ ($WP_CLI_SOURCE)"
```

## Section 1: Argument Parsing and Mode Detection

Parse all arguments and determine the build mode. Flag-based modes take priority over natural language (default) mode.

```bash
INPUT="$@"

# Mode detection — check flags in priority order
if echo "$INPUT" | grep -q "\-\-blank"; then
  MODE="blank"
  SLUG="blank-site"
  SITE_TITLE="Blank WordPress Site"

elif echo "$INPUT" | grep -qE "\-\-visual[[:space:]]"; then
  MODE="visual"
  VISUAL_PATH=$(echo "$INPUT" | sed 's/.*--visual[[:space:]]*\([^ ]*\).*/\1/')
  # Slug from folder basename
  SLUG=$(basename "$VISUAL_PATH" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | sed 's/[^a-z0-9-]//g')
  SITE_TITLE="$SLUG"

elif echo "$INPUT" | grep -qE "\-\-from-url[[:space:]]"; then
  MODE="url"
  SOURCE_URL=$(echo "$INPUT" | sed 's/.*--from-url[[:space:]]*\([^ ]*\).*/\1/')
  # Slug from domain name
  SLUG=$(echo "$SOURCE_URL" | sed 's|https\?://||' | sed 's|/.*||' | tr '.' '-' | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9-]//g')
  SITE_TITLE="$SLUG"

else
  # Natural language mode (default — plain text with no flags)
  MODE="nl"
  NL_PROMPT="$INPUT"
  # Derive slug: lowercase, spaces→hyphens, strip special chars, truncate to 40 chars
  SLUG=$(echo "$NL_PROMPT" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | sed 's/[^a-z0-9-]//g' | sed 's/--*/-/g' | cut -c1-40)
  SITE_TITLE="$NL_PROMPT"
fi

# WP Version override — applies to any mode
if echo "$INPUT" | grep -qE "\-\-wp-version[[:space:]]"; then
  WP_VERSION=$(echo "$INPUT" | sed 's/.*--wp-version[[:space:]]*\([^ ]*\).*/\1/')
else
  WP_VERSION="latest"
fi

echo "[Build] Mode: $MODE | Slug: $SLUG | WP Version: $WP_VERSION"
```

## Section 2: Mode Routing

Route to the appropriate build pipeline based on the detected mode.

```bash
case "$MODE" in

  "blank")
    echo "[Build] Mode: Blank WordPress installation"
    echo ""
    # Route to build-scaffold skill
    # The skill expects: MODE, SLUG, WP_VERSION, SITE_TITLE
    # (Skill execution follows — see skills/build-scaffold/SKILL.md)
    ;;

  "nl")
    echo "[Build] Mode: Natural language site creation"
    echo "[Build] Prompt: $NL_PROMPT"
    echo ""
    # Route to NL pipeline (Section 3a)
    ;;

  "visual")
    echo "[Build] Mode: Visual design import"
    echo "[Build] Input: $VISUAL_PATH"
    echo ""
    # Route to visual pipeline (Section 3b)
    ;;

  "url")
    echo "[Build] Mode: URL clone"
    echo "[Build] Source: $SOURCE_URL"
    echo ""
    # Route to URL clone pipeline (Section 3c)
    ;;

esac
```

## Section 3: Build Execution (blank mode)

For `--blank` mode, execute the complete build pipeline: build-scaffold followed by build-mcp, then zip packaging. The steps are carried out in order, invoking sections from `skills/build-scaffold/SKILL.md`, `skills/build-mcp/SKILL.md`, and `skills/build-git/SKILL.md`.

```bash
# ── Pre-step: Resolve PLUGIN_DIR ───────────────────────────────────────────
# PLUGIN_DIR is the absolute path to the CoWork plugin directory — the directory
# containing CLAUDE.md, skills/, commands/, and vendor/.
# Claude resolves this from the known location of the COMMAND.md being executed.
# Example: PLUGIN_DIR="/Users/yourname/cowork-wp-plugin"
PLUGIN_DIR="<resolved by Claude to the absolute path of this plugin's root directory>"

# ── Step 1: Set up build directory ─────────────────────────────────────────
# Variables: MODE, SLUG, WP_VERSION, SITE_TITLE (set in Section 1)
# Sets: BUILD_DIR, BUILD_DIR_NAME
# (Execute skills/build-scaffold/SKILL.md Section 2: Build Directory Setup)

# ── Step 1a: Initialize git and write .gitignore Phase 1 ───────────────────
# Requires: BUILD_DIR (set in Step 1)
# Sets: GIT_INITIALIZED, defines git_commit_stage() function
# Produces: $BUILD_DIR/.git/, $BUILD_DIR/.gitignore (static exclusions)
# (Execute skills/build-git/SKILL.md Section 1: Git Initialization and User Config)
# (Execute skills/build-git/SKILL.md Section 2: .gitignore Phase 1)
# (Execute skills/build-git/SKILL.md Section 4: Stage Commit Helper — define function)

# ── Step 2: Start ephemeral MySQL ──────────────────────────────────────────
# Sets: MYSQL_CONTAINER, EXIT trap (cleanup_mysql), database credentials
# IMPORTANT: The EXIT trap remains active through Steps 3–6 below.
# The Docker container must be alive for WP-CLI plugin activation in Step 4.
# (Execute skills/build-scaffold/SKILL.md Section 3: Ephemeral Docker MySQL)

# ── Step 3: Run WP-CLI pipeline ────────────────────────────────────────────
# Steps: wp core download → wp config create → wp core install → wp db export
# Sets: WP (WP-CLI command), WP_CLI_MODE, ADMIN_PASS
# Produces: database.sql (initial export — will be overwritten by Step 4)
# (Execute skills/build-scaffold/SKILL.md Section 4: WP-CLI Build Pipeline)

# ── Step 3a: Commit scaffold ────────────────────────────────────────────────
# Commit the blank WP installation state (before MCP adapter is added)
# (Execute skills/build-git/SKILL.md Section 4 — call git_commit_stage)
# git_commit_stage "build(scaffold): blank WordPress installation"

# ── Step 4: Install and activate MCP adapter (build-mcp) ───────────────────
# Requires: BUILD_DIR, WP, PLUGIN_DIR (set above)
# Runs while Docker MySQL container is still alive (EXIT trap is active)
# Steps: copy vendor/mcp-adapter/ → activate → re-export DB → write README.md
# Produces: wp-content/plugins/mcp-adapter/, updated database.sql, README.md
# Sets: MCP_ADAPTER_INCLUDED, MCP_ADAPTER_ACTIVE, MCP_ADAPTER_VERSION
# Warn-and-continue: adapter failures produce warnings, never abort the build
# (Execute skills/build-mcp/SKILL.md Section 1: MCP Adapter Copy)
# (Execute skills/build-mcp/SKILL.md Section 2: Plugin Activation and Database Re-export)
# (Execute skills/build-mcp/SKILL.md Section 3: README.md Generation)

# ── Step 4a: Commit MCP adapter ─────────────────────────────────────────────
# Commit the MCP adapter installation (README.md + mcp-adapter excluded by .gitignore)
# (Execute skills/build-git/SKILL.md Section 4 — call git_commit_stage)
# git_commit_stage "build(mcp): install MCP adapter v${MCP_ADAPTER_VERSION}"

# ── Step 5: Package for Local WP ───────────────────────────────────────────
# zip wp-content/ + database.sql + README.md + .git/ + .gitignore with cd-before-zip pattern
# .git/ and .gitignore are included so the imported build has git history
# (Execute skills/build-scaffold/SKILL.md Section 5: Zip Packaging)
# NOTE: The zip command must include .git/ and .gitignore:
#   (cd "$BUILD_DIR" && zip -r "$ZIP_PATH" wp-content/ database.sql README.md .git/ .gitignore)

# ── Step 6: Write build manifest ───────────────────────────────────────────
# build.json at $BUILD_DIR/build.json — no admin password stored
# (Execute skills/build-scaffold/SKILL.md Section 6: Build Manifest)

# ── Step 7: Update build manifest with MCP fields ──────────────────────────
# Adds mcp_adapter object {included, activated, version} to build.json
# (Execute skills/build-mcp/SKILL.md Section 4: Build Manifest Update)

# ── Step 7a: Update build manifest with git metadata ───────────────────────
# Adds git object {initialized, branch, commits} to build.json (2 commits for blank build)
# (Execute skills/build-git/SKILL.md Section 7: Build Manifest Update)

# ── Step 8: Display build summary ──────────────────────────────────────────
# Shows build ID, WP version, build dir, zip path, admin credentials
# Admin password displayed here ONLY — not stored anywhere
# (Execute skills/build-scaffold/SKILL.md Section 7: Build Summary Output)
# (Execute skills/build-mcp/SKILL.md Section 5: Build Summary Extension)

# ── Cleanup ────────────────────────────────────────────────────────────────
# Docker container cleanup is automatic via EXIT trap set in Step 2 (Section 3 of build-scaffold)
# The trap fires when the entire build session ends — covering both build-scaffold and build-mcp steps
# (No explicit action needed here)
```

## Section 3a: NL Build Execution

For natural language mode, execute the complete NL pipeline: scaffold → MCP → theme → content → setup → zip. This runs when MODE="nl" is detected in Section 2.

```bash
# ── Pre-step: Resolve PLUGIN_DIR ───────────────────────────────────────────
PLUGIN_DIR="<resolved by Claude to the absolute path of this plugin's root directory>"

# ── Step 1: Set up build directory ─────────────────────────────────────────
# Variables: MODE="nl", SLUG, WP_VERSION, SITE_TITLE (set in Section 1)
# Sets: BUILD_DIR, BUILD_DIR_NAME
# (Execute skills/build-scaffold/SKILL.md Section 2: Build Directory Setup)

# ── Step 1a: Initialize git and write .gitignore Phase 1 ───────────────────
# Requires: BUILD_DIR (set in Step 1)
# Sets: GIT_INITIALIZED, defines git_commit_stage() function
# Produces: $BUILD_DIR/.git/, $BUILD_DIR/.gitignore (static exclusions)
# (Execute skills/build-git/SKILL.md Section 1: Git Initialization and User Config)
# (Execute skills/build-git/SKILL.md Section 2: .gitignore Phase 1)
# (Execute skills/build-git/SKILL.md Section 4: Stage Commit Helper — define function)

# ── Step 2: Start ephemeral MySQL ──────────────────────────────────────────
# Sets: MYSQL_CONTAINER, EXIT trap, database credentials
# EXIT trap remains active through all remaining steps
# (Execute skills/build-scaffold/SKILL.md Section 3: Ephemeral Docker MySQL)

# ── Step 3: Run WP-CLI pipeline ────────────────────────────────────────────
# Steps: wp core download → wp config create → wp core install → wp db export
# Sets: WP, ADMIN_PASS
# Produces: initial database.sql (will be overwritten by content + MCP steps)
# (Execute skills/build-scaffold/SKILL.md Section 4: WP-CLI Build Pipeline)

# ── Step 3a: Commit scaffold ────────────────────────────────────────────────
# Commit the blank WP installation state (before MCP adapter is added)
# (Execute skills/build-git/SKILL.md Section 4 — call git_commit_stage)
# git_commit_stage "build(scaffold): blank WordPress installation"

# ── Step 4: Install and activate MCP adapter ──────────────────────────────
# Requires: BUILD_DIR, WP, PLUGIN_DIR
# Copies pre-compiled vendor/mcp-adapter/, activates via WP-CLI, re-exports DB, writes README.md
# Sets: MCP_ADAPTER_INCLUDED, MCP_ADAPTER_ACTIVE, MCP_ADAPTER_VERSION
# Warn-and-continue: adapter failures produce warnings, never abort the build
# (Execute skills/build-mcp/SKILL.md Sections 1-3)

# ── Step 4a: Commit MCP adapter ─────────────────────────────────────────────
# Commit the MCP adapter installation (README.md tracked; mcp-adapter/ excluded by .gitignore)
# (Execute skills/build-git/SKILL.md Section 4 — call git_commit_stage)
# git_commit_stage "build(mcp): install MCP adapter v${MCP_ADAPTER_VERSION}"

# ── Step 5: Select and install FSE theme ──────────────────────────────────
# Requires: BUILD_DIR, WP, NL_PROMPT, SITE_TITLE
# Searches WP.org Themes API for FSE themes matching the NL description
# Falls back to curated category list if API returns poor results
# Sets: THEME_SLUG, THEME_NAME, THEME_VERSION, THEME_INSTALLED
# Warn-and-continue: uses twentytwentyfour fallback if all else fails
# (Execute skills/build-theme/SKILL.md Sections 1-4)

# ── Step 5a: Commit theme ───────────────────────────────────────────────────
# Commit theme installation — WP.org themes excluded by .gitignore Phase 2 (appended in Step 6a)
# At this point the theme IS tracked — Phase 2 exclusion happens AFTER content is installed
# NOTE: This commit captures theme-related config changes (e.g., active theme in DB export)
# (Execute skills/build-git/SKILL.md Section 4 — call git_commit_stage)
# git_commit_stage "build(theme): install ${THEME_NAME}"

# ── Step 6: Install plugins + seed content + generate images ──────────────
# Requires: BUILD_DIR, WP, NL_PROMPT, THEME_SLUG, PLUGIN_DIR
# Installs relevant WP.org plugins (max 10, curated baseline + Claude selection)
# Generates Python placeholder images matched to theme colors
# Creates 3-5 pages + 3-5 blog posts with Gutenberg block markup
# Creates and assigns navigation menu (or attempts assignment for FSE themes)
# Re-exports database to capture all content and activation states
# Sets: INSTALLED_PLUGINS, FAILED_PLUGINS, PAGES_CREATED, POSTS_CREATED, MENU_ASSIGNED, MENU_LOCATION
# (Execute skills/build-content/SKILL.md Sections 1-5)

# ── Step 6a: Update .gitignore with dynamic exclusions ──────────────────────
# Append WP.org plugin and theme slug exclusions based on what was actually installed
# Requires: THEME_SLUG, INSTALLED_PLUGINS (both set in Steps 5 and 6)
# (Execute skills/build-git/SKILL.md Section 3: .gitignore Phase 2)

# ── Step 6b: Commit initial content ─────────────────────────────────────────
# Commit content, plugins, and menus with structured build(init) commit body
# This commit comes AFTER .gitignore Phase 2 so installed plugins/themes are excluded
# Body format: "Theme: {THEME_NAME}\nPlugins: {comma-separated names}\nPages: N, Posts: N"
# (Execute skills/build-git/SKILL.md Section 5 — build the PLUGINS_SUMMARY, then call:)
# git_commit_stage "build(init): ${SLUG}" "$INIT_BODY"

# ── Step 7: Generate SETUP.md and update build.json ───────────────────────
# Requires: BUILD_DIR, NL_PROMPT, THEME_SLUG, THEME_NAME, THEME_VERSION, THEME_INSTALLED
#           INSTALLED_PLUGINS, FAILED_PLUGINS, PAGES_CREATED, POSTS_CREATED, MENU_ASSIGNED, MENU_LOCATION
# Produces: SETUP.md at $BUILD_DIR/SETUP.md
# Updates: build.json with NL-specific metadata (mode, nl_prompt, theme, plugins, content)
# (Execute skills/build-setup/SKILL.md Sections 1-2)

# ── Step 7a: Commit setup ───────────────────────────────────────────────────
# Commit SETUP.md and build manifest files
# (Execute skills/build-git/SKILL.md Section 4 — call git_commit_stage)
# git_commit_stage "build(setup): generate SETUP.md and build manifest"

# ── Step 8: Package for Local WP ─────────────────────────────────────────
# zip wp-content/ + database.sql + README.md + SETUP.md + .git/ + .gitignore
# .git/ and .gitignore are included so the imported build has git history
# (Execute skills/build-scaffold/SKILL.md Section 5: Zip Packaging)
# The zip command MUST include .git/ and .gitignore:
#   (cd "$BUILD_DIR" && zip -r "$ZIP_PATH" wp-content/ database.sql README.md SETUP.md .git/ .gitignore)

# ── Step 9: Write build manifest ─────────────────────────────────────────
# build.json at $BUILD_DIR/build.json — no admin password stored
# (Execute skills/build-scaffold/SKILL.md Section 6: Build Manifest)

# ── Step 10: Update manifest with MCP + NL fields ─────────────────────────
# Adds mcp_adapter object {included, activated, version} to build.json
# (Execute skills/build-mcp/SKILL.md Section 4: Build Manifest Update)
# build-setup Section 2 updates NL fields (mode, nl_prompt, theme, plugins, content) — already run in Step 7
# If Step 7 is run before Step 9 (manifest doesn't exist yet), defer NL metadata to this step instead

# ── Step 10a: Update build manifest with git metadata ──────────────────────
# Adds git object {initialized, branch, commits} to build.json (5 commits for NL build)
# (Execute skills/build-git/SKILL.md Section 7: Build Manifest Update)

# ── Step 11: Display build summary ────────────────────────────────────────
# Base summary: build ID, WP version, build dir, zip path, admin credentials
# (Execute skills/build-scaffold/SKILL.md Section 7: Build Summary Output)
# MCP extension: MCP adapter status and README.md note
# (Execute skills/build-mcp/SKILL.md Section 5: Build Summary Extension)
# NL extension: prompt, theme, plugins, content counts, menu status, SETUP.md note
# (Execute skills/build-setup/SKILL.md Section 3: NL Build Summary Extension)

# ── Cleanup ───────────────────────────────────────────────────────────────
# Docker container cleanup automatic via EXIT trap
```

**Step 7 / Step 10 ordering note:** build-setup Section 2 (build.json NL metadata) reads and updates the build.json file. If the build.json doesn't exist yet when Step 7 runs (i.e., build-scaffold Section 6 hasn't run), defer the build.json update to Step 10 after Section 6 creates the file. In practice, Claude should run Steps 7 (SETUP.md only) and 9 (build.json creation) before running the NL metadata update in Step 10.

## Section 3b: Visual Build Execution

For visual mode, execute the complete visual pipeline: scaffold → MCP → design parsing → token extraction → theme scaffolding → font downloading → theme activation → setup → zip. This runs when MODE="visual" is detected in Section 2.

```bash
# ── Pre-step: Resolve PLUGIN_DIR ───────────────────────────────────────────
PLUGIN_DIR="<resolved by Claude to the absolute path of this plugin's root directory>"

# ── Step 1: Set up build directory ─────────────────────────────────────────
# Variables: MODE="visual", SLUG, WP_VERSION, SITE_TITLE (set in Section 1)
# Sets: BUILD_DIR, BUILD_DIR_NAME
# (Execute skills/build-scaffold/SKILL.md Section 2: Build Directory Setup)

# ── Step 1a: Initialize git and write .gitignore Phase 1 ───────────────────
# Requires: BUILD_DIR (set in Step 1)
# Sets: GIT_INITIALIZED, defines git_commit_stage() function
# Produces: $BUILD_DIR/.git/, $BUILD_DIR/.gitignore (static exclusions)
# (Execute skills/build-git/SKILL.md Section 1: Git Initialization and User Config)
# (Execute skills/build-git/SKILL.md Section 2: .gitignore Phase 1)
# (Execute skills/build-git/SKILL.md Section 4: Stage Commit Helper — define function)

# ── Step 2: Start ephemeral MySQL ──────────────────────────────────────────
# Sets: MYSQL_CONTAINER, EXIT trap, database credentials
# EXIT trap remains active through all remaining steps
# (Execute skills/build-scaffold/SKILL.md Section 3: Ephemeral Docker MySQL)

# ── Step 3: Run WP-CLI pipeline ────────────────────────────────────────────
# Steps: wp core download → wp config create → wp core install → wp db export
# Sets: WP, ADMIN_PASS
# Produces: initial database.sql
# (Execute skills/build-scaffold/SKILL.md Section 4: WP-CLI Build Pipeline)

# ── Step 3a: Commit scaffold ────────────────────────────────────────────────
# git_commit_stage "build(scaffold): blank WordPress installation"

# ── Step 4: Install and activate MCP adapter ──────────────────────────────
# Requires: BUILD_DIR, WP, PLUGIN_DIR
# Sets: MCP_ADAPTER_INCLUDED, MCP_ADAPTER_ACTIVE, MCP_ADAPTER_VERSION
# (Execute skills/build-mcp/SKILL.md Sections 1-3)

# ── Step 4a: Commit MCP adapter ─────────────────────────────────────────────
# git_commit_stage "build(mcp): install MCP adapter v${MCP_ADAPTER_VERSION}"

# ── Step 5: Detect input type and parse design ────────────────────────────
# Requires: VISUAL_PATH (set in Section 1)
# Sets: VISUAL_MODE (html-css or screenshot)
# (Execute skills/build-visual/SKILL.md Section 1: Input Detection and Design Parsing)

# ── Step 6: Extract design tokens ─────────────────────────────────────────
# Requires: VISUAL_MODE, design files or screenshot analysis
# Sets: EXTRACTED_COLORS, EXTRACTED_FONTS, FONT_MAP, FONT_SUBSTITUTIONS
# (Execute skills/build-visual/SKILL.md Section 2: Design Token Extraction)

# ── Step 7: Scaffold custom FSE theme ──────────────────────────────────────
# Requires: BUILD_DIR, SLUG, EXTRACTED_COLORS, EXTRACTED_FONTS
# Produces: custom-{slug}/ theme directory with style.css, theme.json, templates/, parts/, assets/
# CRITICAL: Validates theme.json as valid JSON after writing
# (Execute skills/build-visual/SKILL.md Section 3: Theme Scaffolding)

# ── Step 8: Download and bundle Google Fonts ──────────────────────────────
# Requires: FONT_MAP, THEME_DIR ($BUILD_DIR/wp-content/themes/custom-${SLUG})
# Downloads woff2 files via gwfh.mranftl.com API to assets/fonts/
# Updates theme.json fontFace src entries with actual downloaded filenames
# Fallback: system font stack in theme.json + SETUP.md Critical warning (no CDN requests per locked decision)
# (Execute skills/build-visual/SKILL.md Section 4: Font Downloading)

# ── Step 9: Activate theme and re-export database ──────────────────────────
# Requires: BUILD_DIR, WP, custom-${SLUG} theme written to disk
# Activates theme via WP-CLI, sets static front page, re-exports database
# Sets: THEME_SLUG, THEME_NAME, THEME_VERSION, THEME_INSTALLED
# (Execute skills/build-visual/SKILL.md Section 5: WP-CLI Theme Activation and DB Export)

# ── Step 9a: Update .gitignore with dynamic exclusions ────────────────────
# Custom-{slug} theme is NOT excluded (custom- prefix = tracked)
# No WP.org plugins installed in visual mode — Phase 2 is minimal
# (Execute skills/build-git/SKILL.md Section 3: .gitignore Phase 2)
# Note: INSTALLED_PLUGINS is empty for visual builds — Phase 2 only processes theme

# ── Step 9b: Commit theme and content ──────────────────────────────────────
# Commit the custom theme, activation state, and all theme files
# git_commit_stage "build(init): custom-${SLUG}" "Theme: Custom ${SLUG}\nMode: visual (${VISUAL_MODE})"

# ── Step 10: Generate SETUP.md for visual build ──────────────────────────
# Requires: THEME_SLUG, FONT_SUBSTITUTIONS, VISUAL_MODE
# Produces: SETUP.md with visual-specific guidance (font substitutions, image replacement, etc.)
# (Execute skills/build-visual/SKILL.md Section 6: SETUP.md for Visual Builds)

# ── Step 10a: Commit setup ─────────────────────────────────────────────────
# git_commit_stage "build(setup): generate SETUP.md and build manifest"

# ── Step 11: Package for Local WP ────────────────────────────────────────
# zip wp-content/ + database.sql + README.md + SETUP.md + .git/ + .gitignore
# (Execute skills/build-scaffold/SKILL.md Section 5: Zip Packaging)
# ZIP MUST include .git/ and .gitignore:
#   (cd "$BUILD_DIR" && zip -r "$ZIP_PATH" wp-content/ database.sql README.md SETUP.md .git/ .gitignore)

# ── Step 12: Write build manifest ────────────────────────────────────────
# build.json at $BUILD_DIR/build.json
# (Execute skills/build-scaffold/SKILL.md Section 6: Build Manifest)

# ── Step 13: Update manifest with MCP + visual fields ──────────────────
# Adds mcp_adapter object to build.json
# (Execute skills/build-mcp/SKILL.md Section 4: Build Manifest Update)
# Adds visual-specific fields to build.json:
#   "mode": "visual"
#   "visual_input": { "type": VISUAL_MODE, "path": VISUAL_PATH, "colors_extracted": N, "fonts_extracted": N, "fonts_bundled": true/false }
#   "theme": { "slug": "custom-{slug}", "name": "Custom {Slug}", "version": "1.0.0", "installed": true/false }
# Use Python3 JSON update pattern from build-setup Section 2

# ── Step 13a: Update build manifest with git metadata ─────────────────────
# Adds git object {initialized, branch, commits} to build.json (4 commits for visual build)
# (Execute skills/build-git/SKILL.md Section 7: Build Manifest Update)

# ── Step 14: Display build summary ───────────────────────────────────────
# Base summary: build ID, WP version, build dir, zip path, admin credentials
# (Execute skills/build-scaffold/SKILL.md Section 7: Build Summary Output)
# MCP extension:
# (Execute skills/build-mcp/SKILL.md Section 5: Build Summary Extension)
# Visual extension:
echo ""
echo "[Build] ── Visual Build Details ──────────────────"
echo "[Build] Input:   ${VISUAL_MODE} (${VISUAL_PATH})"
echo "[Build] Theme:   Custom ${SLUG} (custom-${SLUG} v1.0.0)"
echo "[Build] Colors:  ${#EXTRACTED_COLORS[@]} extracted"
echo "[Build] Fonts:   ${#EXTRACTED_FONTS[@]} extracted (${FONTS_BUNDLED_COUNT} bundled)"
echo "[Build] Guide:   SETUP.md included in zip"
echo ""

# ── Cleanup ───────────────────────────────────────────────────────────────
# Docker container cleanup automatic via EXIT trap
```

## Section 3c: URL Build Execution

For URL clone mode, execute the complete URL pipeline: scaffold → MCP → scrape → sanitise → visual FSE → setup → zip. This runs when MODE="url" is detected in Section 2. The URL pipeline reuses build-visual Sections 2–6 with no separate theme generation code — `VISUAL_PATH` is set to `SCRAPE_DIR` and `VISUAL_MODE` to `"html-css"` as the integration seam.

```bash
# ── Pre-step: Resolve PLUGIN_DIR ───────────────────────────────────────────
# PLUGIN_DIR is the absolute path to the CoWork plugin directory — the directory
# containing CLAUDE.md, skills/, commands/, and vendor/.
# Claude resolves this from the known location of the COMMAND.md being executed.
# Example: PLUGIN_DIR="/Users/yourname/cowork-wp-plugin"
PLUGIN_DIR="<resolved by Claude to the absolute path of this plugin's root directory>"

# ── Step 1: Set up build directory and temp directories ─────────────────────
# Variables: MODE="url", SLUG, WP_VERSION, SITE_TITLE, SOURCE_URL (set in Section 1)
# Sets: BUILD_DIR, BUILD_DIR_NAME
# Also sets: SCRAPE_DIR="/tmp/scrape_${SLUG}_$$"
# EXIT trap cleans up BOTH directories: trap "rm -rf '$BUILD_DIR' '$SCRAPE_DIR'" EXIT
# (Execute skills/build-scaffold/SKILL.md Section 2: Build Directory Setup)
# Then set:
# SCRAPE_DIR="/tmp/scrape_${SLUG}_$$"
# mkdir -p "$SCRAPE_DIR"
# trap "rm -rf '$BUILD_DIR' '$SCRAPE_DIR'" EXIT
# NOTE: build-scrape Section 0 also registers its own trap for SCRAPE_DIR — the COMMAND.md
# trap here is belt-and-suspenders, covering the case where build-scrape Section 0 hasn't
# run yet if an early error fires.

# ── Step 1a: Initialize git and write .gitignore Phase 1 ───────────────────
# Requires: BUILD_DIR (set in Step 1)
# Sets: GIT_INITIALIZED, defines git_commit_stage() function
# Produces: $BUILD_DIR/.git/, $BUILD_DIR/.gitignore (static exclusions)
# (Execute skills/build-git/SKILL.md Section 1: Git Initialization and User Config)
# (Execute skills/build-git/SKILL.md Section 2: .gitignore Phase 1)
# (Execute skills/build-git/SKILL.md Section 4: Stage Commit Helper — define function)

# ── Step 2: Start ephemeral MySQL ──────────────────────────────────────────
# Sets: MYSQL_CONTAINER, database credentials
# EXIT trap from Step 1 covers Docker cleanup as well — update it to include container removal
# (Execute skills/build-scaffold/SKILL.md Section 3: Ephemeral Docker MySQL)

# ── Step 3: Run WP-CLI pipeline ────────────────────────────────────────────
# Steps: wp core download → wp config create → wp core install → wp db export
# Sets: WP (WP-CLI command), WP_CLI_MODE, ADMIN_PASS
# Produces: initial database.sql
# (Execute skills/build-scaffold/SKILL.md Section 4: WP-CLI Build Pipeline)

# ── Step 3a: Commit scaffold ────────────────────────────────────────────────
# Commit the blank WP installation state (before MCP adapter is added)
# (Execute skills/build-git/SKILL.md Section 4 — call git_commit_stage)
# git_commit_stage "build(scaffold): blank WordPress installation"

# ── Step 4: Install and activate MCP adapter (build-mcp) ───────────────────
# Requires: BUILD_DIR, WP, PLUGIN_DIR
# Runs while Docker MySQL container is still alive
# Steps: copy vendor/mcp-adapter/ → activate → re-export DB → write README.md
# Produces: wp-content/plugins/mcp-adapter/, updated database.sql, README.md
# Sets: MCP_ADAPTER_INCLUDED, MCP_ADAPTER_ACTIVE, MCP_ADAPTER_VERSION
# Warn-and-continue: adapter failures produce warnings, never abort the build
# (Execute skills/build-mcp/SKILL.md Sections 1-3)

# ── Step 4a: Commit MCP adapter ─────────────────────────────────────────────
# Commit the MCP adapter installation (README.md + mcp-adapter excluded by .gitignore)
# (Execute skills/build-git/SKILL.md Section 4 — call git_commit_stage)
# git_commit_stage "build(mcp): install MCP adapter v${MCP_ADAPTER_VERSION}"

# ── Step 5: build-scrape Sections 0–1 — Prerequisites and pre-scrape guard ─
# Requires: SOURCE_URL, SLUG, PLUGIN_DIR (all set above)
# Checks: Playwright npm package, robots-parser npm package
# Creates: SCRAPE_DIR (if not already created in Step 1)
# Registers: EXIT trap for SCRAPE_DIR cleanup
# Displays: robots.txt check result + copyright disclaimer + confirmation banner
# Prompts: interactive y/N confirmation — exits 0 on user cancel (clean exit, no error)
# Sets: ROBOTS_STATUS="allowed" or "disallowed-override"
# (Execute skills/build-scrape/SKILL.md Section 0: Prerequisite Check)
# (Execute skills/build-scrape/SKILL.md Section 1: Pre-Scrape Guard)

# ── Step 6: build-scrape Section 2 — Playwright scraping ───────────────────
# Requires: SOURCE_URL, SCRAPE_DIR, PLUGIN_DIR (set above)
# Invokes: node "$PLUGIN_DIR/skills/build-scrape/scraper.js" "$SOURCE_URL" "$SCRAPE_DIR"
# If homepage scrape fails: exit 1 (build aborted — error message shown)
# Inner page failures: logged to failed_pages in scrape.json, build continues
# Sets: SCRAPE_MANIFEST="$SCRAPE_DIR/scrape.json"
# Logs: pages scraped, CSS size, dynamic features detected, images noted
# (Execute skills/build-scrape/SKILL.md Section 2: Playwright Scraping)

# ── Step 7: build-scrape Section 3 — Content sanitisation ──────────────────
# Requires: SCRAPE_DIR (HTML files and styles/main.css written by scraper.js)
# Claude in-context step: reads each .html file, rewrites with fictional placeholders
# 8 explicit replacement rules: text, brand name, logo, nav, scripts, external CSS, meta, feature placeholders
# Python script: strips CSS content: "..." declarations (prevents brand text in pseudo-elements)
# Python script: updates scrape.json with robots_status field
# (Execute skills/build-scrape/SKILL.md Section 3: Content Sanitisation)

# ── Step 8: Set VISUAL_PATH and VISUAL_MODE ─────────────────────────────────
# This is the critical integration seam: from here, build-visual runs identically
# to a design export build. VISUAL_MODE is pre-set — Section 1 of build-visual is SKIPPED.
VISUAL_PATH="$SCRAPE_DIR"
VISUAL_MODE="html-css"
echo "[Build] Integration seam: VISUAL_PATH=$VISUAL_PATH, VISUAL_MODE=$VISUAL_MODE"
echo "[Build] Routing to build-visual pipeline (Sections 2–6)..."

# ── Step 9: build-visual Sections 2–6 — FSE theme generation ───────────────
# Requires: VISUAL_PATH="$SCRAPE_DIR", VISUAL_MODE="html-css", BUILD_DIR, SLUG, SITE_TITLE, PLUGIN_DIR, WP
# NOTE: Section 1 (input detection) is SKIPPED — VISUAL_MODE is already set to "html-css" by Step 8.
#       build-visual Section 1 is only needed when VISUAL_PATH is user-supplied and type is unknown.
#       For URL builds, build-scrape has already produced an html-css directory at SCRAPE_DIR.
#
# Section 2: Design Token Extraction — read main.css + HTML files, extract colors, fonts, font-sizes
#   Sets: EXTRACTED_COLORS, EXTRACTED_FONTS, FONT_MAP, FONT_SUBSTITUTIONS
# Section 3: Theme Scaffolding — create custom-{slug}/ with style.css, theme.json, templates/, parts/, assets/
#   Requires: EXTRACTED_COLORS, EXTRACTED_FONTS; validates theme.json as valid JSON after write
# Section 4: Font Downloading — download woff2 via gwfh API to assets/fonts/, update theme.json fontFace src
#   Fallback: system font stack + SETUP.md Critical warning if download fails
# Section 5: WP-CLI Theme Activation and DB Export — activate custom-{slug}, set static front page, re-export DB
#   Sets: THEME_SLUG="custom-${SLUG}", THEME_NAME, THEME_VERSION, THEME_INSTALLED
# Section 6: SETUP.md for Visual Builds — generate base SETUP.md with visual-specific guidance
# (Execute skills/build-visual/SKILL.md Section 2: Design Token Extraction)
# (Execute skills/build-visual/SKILL.md Section 3: Theme Scaffolding)
# (Execute skills/build-visual/SKILL.md Section 4: Font Downloading)
# (Execute skills/build-visual/SKILL.md Section 5: WP-CLI Theme Activation and DB Export)
# (Execute skills/build-visual/SKILL.md Section 6: SETUP.md for Visual Builds)

# ── Step 9a: Update .gitignore with dynamic exclusions ────────────────────
# Custom-{slug} theme is NOT excluded (custom- prefix = tracked)
# No WP.org plugins installed in URL mode — Phase 2 minimal (same as visual mode)
# (Execute skills/build-git/SKILL.md Section 3: .gitignore Phase 2)
# Note: INSTALLED_PLUGINS is empty for URL builds — Phase 2 only processes theme

# ── Step 9b: Commit theme and content ──────────────────────────────────────
# Commit the custom theme, activation state, and all theme files
# git_commit_stage "build(init): custom-${SLUG}" "Theme: Custom ${SLUG}\nMode: url (html-css)\nSource: ${SOURCE_URL}"

# ── Step 10: build-scrape Section 4 — Append URL clone sections to SETUP.md ─
# Requires: SCRAPE_MANIFEST="$SCRAPE_DIR/scrape.json", BUILD_DIR
# Appends to $BUILD_DIR/SETUP.md (after build-visual Section 6 writes the base SETUP.md):
#   - URL Clone Information (source URL, clone timestamp)
#   - Color Palette Attribution warning (replace before going live)
#   - Dynamic Features Detected table (all detected features mapped to WP.org plugins)
#   - Pages Scraped table (URLs, filenames, status)
#   - SPA fallback notice if spa_fallback_used=true
# (Execute skills/build-scrape/SKILL.md Section 4: SETUP.md URL Clone Appendix)

# ── Step 10a: Commit setup ─────────────────────────────────────────────────
# Commit SETUP.md (with URL clone appendix) and build manifest files
# git_commit_stage "build(setup): generate SETUP.md and build manifest"

# ── Step 11: Copy scrape.json to BUILD_DIR ──────────────────────────────────
# Preserve scrape.json from the temp SCRAPE_DIR to BUILD_DIR before EXIT trap fires
# This must run BEFORE zip packaging so scrape.json is included at the zip root
cp "$SCRAPE_MANIFEST" "$BUILD_DIR/scrape.json"
echo "[Build] scrape.json copied to BUILD_DIR"

# ── Step 12: build-git — Dynamic .gitignore update and git commits ──────────
# URL builds produce 4 git commits matching visual builds:
#   1. build(scaffold): blank WordPress installation
#   2. build(mcp): install MCP adapter v{version}
#   3. build(init): custom-{slug} [committed in Step 9b above]
#   4. build(setup): generate SETUP.md and build manifest [committed in Step 10a above]
# .gitignore Phase 2: adds custom-{SLUG} to tracked themes (not excluded)
# NOTE: Commits 1 and 2 happen inline (Steps 3a, 4a). Commits 3 and 4 happen in Steps 9b, 10a.
# The build-git skill git_commit_stage() function was defined in Step 1a.
# (Verify with: git -C "$BUILD_DIR" log --oneline — should show 4 commits)

# ── Step 13: Zip packaging ─────────────────────────────────────────────────
# Include scrape.json at zip root alongside database.sql, README.md, SETUP.md
# (Execute skills/build-scaffold/SKILL.md Section 5: Zip Packaging)
# ZIP command MUST include scrape.json, .git/, and .gitignore:
#   (cd "$BUILD_DIR" && zip -r "$ZIP_PATH" wp-content/ database.sql README.md SETUP.md scrape.json .git/ .gitignore)

# ── Step 14: build.json manifest update ────────────────────────────────────
# Write base build.json (build-scaffold Section 6), then update with MCP fields (build-mcp Section 4),
# then add URL-specific metadata using Python3 JSON update pattern:
# (Execute skills/build-scaffold/SKILL.md Section 6: Build Manifest)
# (Execute skills/build-mcp/SKILL.md Section 4: Build Manifest Update)
# (Execute skills/build-git/SKILL.md Section 7: Build Manifest Update — 4 commits for URL build)
# Then append URL-specific fields:
python3 - <<PYEOF
import json, os

manifest_path = os.path.join('$BUILD_DIR', 'build.json')
with open(manifest_path, 'r') as f:
    manifest = json.load(f)

import subprocess
pages_count = int(subprocess.run(
    ['python3', '-c', f"import json; d=json.load(open('$SCRAPE_DIR/scrape.json')); print(len(d.get('pages',[])))"],
    capture_output=True, text=True).stdout.strip() or '0')
dynamic_feats = json.load(open('$SCRAPE_DIR/scrape.json')).get('dynamic_features', [])

manifest['creation_mode'] = 'url'
manifest['source_url']    = '$SOURCE_URL'
manifest['robots_status'] = '$ROBOTS_STATUS'
manifest['url_input'] = {
    'source_url':      '$SOURCE_URL',
    'pages_scraped':   pages_count,
    'dynamic_features': dynamic_feats,
    'robots_status':   '$ROBOTS_STATUS'
}
manifest['theme'] = {
    'slug':    'custom-$SLUG',
    'name':    'Custom $SLUG',
    'version': '1.0.0',
    'installed': True
}

with open(manifest_path, 'w') as f:
    json.dump(manifest, f, indent=2)

print('[Build] build.json updated with URL clone metadata')
PYEOF

# ── Step 15: Build summary ──────────────────────────────────────────────────
# Base summary: build ID, WP version, build dir, zip path, admin credentials
# (Execute skills/build-scaffold/SKILL.md Section 7: Build Summary Output)
# MCP extension:
# (Execute skills/build-mcp/SKILL.md Section 5: Build Summary Extension)
# URL clone extension:
echo ""
echo "[Build] ── URL Clone Build Details ───────────────────"
echo "[Build] Source:          $SOURCE_URL"
echo "[Build] robots.txt:      $ROBOTS_STATUS"
echo "[Build] Pages scraped:   $PAGES_COUNT"
echo "[Build] Features found:  $FEATURES"
echo "[Build] Theme:           Custom ${SLUG} (custom-${SLUG} v1.0.0)"
echo "[Build] scrape.json:     included at zip root"
echo "[Build] Guide:           SETUP.md included in zip (with URL clone appendix)"
echo ""

# ── Cleanup ───────────────────────────────────────────────────────────────
# SCRAPE_DIR cleanup is automatic via EXIT trap (registered in Step 1 and build-scrape Section 0)
# Docker container cleanup is automatic via EXIT trap (registered in build-scaffold Section 3)
# scrape.json has already been copied to BUILD_DIR in Step 11 — SCRAPE_DIR deletion is safe
```

## Section 4: Error Handling

Handle prerequisite failures, port conflicts, and WP-CLI/Docker failures gracefully.

### Docker not running

```bash
# Checked in Section 0 — exits immediately with clear message
# "ERROR: Docker is required for /build. Start Docker Desktop and try again."
```

### WP-CLI not found

```bash
# Checked in Section 0 — exits with install instructions
# Points to https://wp-cli.org for full setup guide
```

### Port 3307 already in use

```bash
# Checked in skill Section 3 before docker run
# "ERROR: Port 3307 is already in use."
# "Close the conflicting process (check with: lsof -i :3307) and try again."
```

### WP-CLI step fails

```bash
# Each WP-CLI step in skill Section 4 checks exit code
# On failure: prints specific step that failed, then exits
# Docker cleanup trap fires automatically on exit
```

### Zip creation fails

```bash
# Checked in skill Section 5
# "ERROR: Zip packaging failed (exit code: N)."
# Docker cleanup trap fires automatically on exit
```

### MCP adapter installation fails

```bash
# build-mcp uses warn-and-continue pattern — no exit 1 for adapter failures
# Build completes without MCP adapter active — zip still valid for Local WP import
# Warning messages explain the situation:
#   "[Build] WARNING: MCP adapter not found at $MCP_ADAPTER_SOURCE"
#   "[Build] WARNING: Skipping MCP adapter installation. Install manually after import."
# OR if copy succeeded but activation failed:
#   "[Build] WARNING: MCP adapter activation failed."
#   "[Build] WARNING: The plugin is installed but not active."
#   "[Build] WARNING: Activate it manually in WP Admin after import."
# README.md is always generated (even if adapter not installed) — explains manual setup
```

### MCP adapter activation fails with database connection error

```bash
# Symptom: wp plugin activate mcp-adapter fails with "Error establishing a database connection"
# Cause: Docker MySQL container stopped before build-mcp could run (e.g., EXIT trap fired early)
# The Docker EXIT trap must remain active through all build steps including build-mcp
# Claude executes all steps in one session — trap scope naturally covers both skills
# If this error occurs: the adapter files are installed but not active in the imported DB
```

### Theme installation fails (NL mode)

```bash
# build-theme uses warn-and-continue — falls back to twentytwentyfour if all candidates fail
# "[Build] WARNING: Theme installation failed for {slug}. Trying next candidate..."
# "[Build] WARNING: All theme candidates failed. Falling back to twentytwentyfour."
# Build continues — zip is valid, SETUP.md notes the installed theme
```

### Plugin installation fails (NL mode)

```bash
# build-content uses warn-and-continue per plugin — FAILED_PLUGINS array tracks failures
# "[Build] WARNING: Plugin {slug} failed to activate. Skipping."
# Build continues with remaining plugins — SETUP.md notes failed plugins
# The zip is still valid for Local WP import
```

### Placeholder image generation fails (NL mode)

```bash
# build-content image generator uses warn-and-continue
# "[Build] WARNING: Image generation failed. Content will be created without placeholder images."
# Pages and posts are created without media references
# Build continues — zip is still valid
```

### WP.org API unavailable (NL mode)

```bash
# build-theme: curated fallback lists are used automatically when API is unavailable
# build-content: curated plugin baseline is used when discovery API is unavailable
# "[Build] WARNING: WP.org API unavailable. Using curated fallback list."
# Build continues using offline-capable defaults
```

## Implementation Notes

**Command format:** This is a CoWork plugin COMMAND.md — Claude reads it as a prompt and executes the described steps. It is not a standalone bash script.

**Skill invocation:** For `--blank` mode, Claude follows the instruction sequence in `skills/build-scaffold/SKILL.md` after Section 2 of this command file. All MODE, SLUG, WP_VERSION, and SITE_TITLE variables must be set before invoking the skill.

**Mode detection priority:** Flag detection takes precedence. If `--blank` is present alongside other flags, `--blank` wins (first match in the if/elif chain).

**WP Version override:** `--wp-version X.Y` applies to all modes. For example, `/build --blank --wp-version 6.6` will install WordPress 6.6.

**Slug safety:** Slugs are sanitized (lowercase, hyphens only, no special characters, max 40 chars) before being used as directory names to prevent filesystem issues.

**Admin password:** Generated by the build-scaffold skill using `openssl rand`. Displayed in the build summary output and nowhere else. Never written to build.json, CLAUDE.md, or any file.

**Absolute zip path:** The zip path displayed in build summary output is always an absolute path (computed before `cd` in the skill), so the user can immediately locate and import it into Local WP.

**Build directory retention:** Both the expanded build directory AND the zip file are kept after packaging. Neither is deleted automatically. The user can inspect the expanded directory or import the zip directly.

**PLUGIN_DIR resolution:** Claude must resolve `PLUGIN_DIR` to the absolute path of the CoWork plugin directory when executing this command. This is the directory containing CLAUDE.md, skills/, commands/, and vendor/. Use the known path of this COMMAND.md file as the reference: PLUGIN_DIR is two directories up from this file (`commands/build/COMMAND.md` → `commands/` → plugin root). In practice, Claude knows this path from the file system context of the session.

**Docker container lifetime and build-mcp:** The EXIT trap registered in build-scaffold Section 3 (`cleanup_mysql`) fires at the end of the entire command session — not between individual skill invocations. Since Claude executes all skills within one session, the Docker MySQL container remains available throughout all steps. The `wp plugin activate mcp-adapter` command in build-mcp Step 4 requires MySQL to be running. If the container exits early (e.g., manual interrupt), the adapter activation will fail with a database connection error — this is handled with warn-and-continue.

**build-mcp skill integration:** The build-mcp skill must run AFTER the WP-CLI pipeline (Step 3) and BEFORE zip packaging. This sequencing is critical: the re-exported database from build-mcp overwrites the initial export and captures plugin activation state.

**NL pipeline requires Python 3:** The build-content skill uses Python 3 for placeholder image generation (Pillow preferred, stdlib struct+zlib fallback). The build-setup skill uses Python 3 for build.json updates. Python 3 is expected to be available on the host machine.

**NL builds produce SETUP.md in addition to README.md:** Both files are included in the zip root. README.md covers MCP adapter setup. SETUP.md covers plugin configuration and content replacement. Both serve different purposes — neither replaces the other.

**NL mode is the default:** Any plain text input without `--blank`, `--visual`, or `--from-url` flags triggers NL mode. Users do not need a special flag. `/build "a portfolio site for a photographer"` and `/build a portfolio site for a photographer` (no quotes) both trigger NL mode.

**Zip includes README.md and SETUP.md (NL mode):** The zip command for NL builds includes both files alongside wp-content/ and database.sql:
```bash
(cd "$BUILD_DIR" && zip -r "$ZIP_PATH" wp-content/ database.sql README.md SETUP.md .git/ .gitignore)
```

**Git initialization:** The build-git skill runs throughout the pipeline, not as a single step. Git init happens early (after directory setup, Step 1a), `.gitignore` Phase 1 is written before any commits, `.gitignore` Phase 2 is appended after build-content (Step 6a), and commits happen after each skill stage. The `git_commit_stage()` function is defined in build-git Section 4 and must be in scope for all commit calls.

**Zip includes .git/ directory:** The git history is preserved in the zip so imported builds have version history. The `.gitignore` file is also included at the build root. Both blank and NL builds include `.git/` and `.gitignore` in their zip archives. This allows users to inspect the build's git history after importing into Local WP.

**Blank build produces 2 commits; NL build produces 5:** Blank builds commit after scaffold and MCP. NL builds additionally commit after theme, content (build(init)), and setup. The build.json `git.commits` field records this count.

**Visual build pipeline:** Section 3b mirrors Section 3a (NL build) in structure but replaces build-theme and build-content with build-visual (Sections 1-6). No WP.org plugins are installed in visual mode — the theme is the sole deliverable alongside the MCP adapter. The visual pipeline produces a lighter build (no plugins, no content pages beyond what the theme templates provide).

**Visual builds produce 4 commits:** scaffold, mcp, init (custom theme + activation), and setup (SETUP.md + manifest). One fewer than NL mode because the theme IS the init in visual mode — there is no separate theme commit. The build(init) commit body includes Theme name and visual mode type.

**No INSTALLED_PLUGINS for visual builds:** The build-git .gitignore Phase 2 receives an empty INSTALLED_PLUGINS array. Only the THEME_SLUG is processed — and since it starts with `custom-`, it is NOT excluded (tracked in git).

**build.json visual metadata:** The visual build adds a `visual_input` object with `type` (html-css or screenshot), `path`, `colors_extracted`, `fonts_extracted`, and `fonts_bundled` fields. The `theme` object uses the custom-{slug} pattern.

**URL build pipeline (Section 3c):** URL clone mode scrapes the target site with Playwright (build-scrape Sections 0–3), hands the sanitised HTML/CSS directory to build-visual Sections 2–6, then runs the build-scrape Section 4 SETUP.md appendix. URL builds produce the same 4-commit git pattern as visual builds: scaffold, mcp, init (custom theme), setup.

**URL builds skip build-visual Section 1:** The input detection logic in build-visual Section 1a is not needed for URL builds — `VISUAL_MODE` is pre-set to `"html-css"` and `VISUAL_PATH` is set to `SCRAPE_DIR` by COMMAND.md Section 3c Step 8 before build-visual is invoked. Only Sections 2–6 of build-visual are executed.

**scrape.json preserved in zip:** The raw scrape manifest (`scrape.json`) is copied from `SCRAPE_DIR` to `BUILD_DIR` in Section 3c Step 11 before the EXIT trap fires. It is included at the zip root alongside `database.sql`, `README.md`, and `SETUP.md`. The remaining temporary HTML/CSS in `SCRAPE_DIR` is cleaned up by the EXIT trap.

**SCRAPE_DIR cleanup:** The EXIT trap set in Section 3c Step 1 covers `SCRAPE_DIR` cleanup. build-scrape Section 0 also registers its own trap — both traps are safe to coexist (idempotent `rm -rf`). After `scrape.json` is copied to `BUILD_DIR` in Step 11, SCRAPE_DIR deletion is safe.

**Content sanitisation is Claude's in-context judgment:** URL builds require Claude to read, rewrite, and overwrite each HTML file in `SCRAPE_DIR` (build-scrape Section 3a). There is no automated verification that all verbatim text has been removed. Following the 8 replacement rules explicitly is the correctness mechanism.

**URL clone mode always requires interactive confirmation:** The pre-scrape guard (build-scrape Section 1) displays the robots.txt result and copyright disclaimer and prompts for y/N confirmation. This cannot be bypassed. If the terminal is non-interactive (TTY not detected), the build exits with an error.

## Success Criteria

The /build command is successful when:

- `/build --blank` triggers the complete build-scaffold pipeline and produces a valid zip file
- `/build "a portfolio site for a freelance photographer"` triggers the full NL pipeline (11 steps: scaffold setup, MySQL, WP-CLI, MCP, theme, content, setup, zip, manifest, MCP manifest, summary) and produces a zip with theme, plugins, content, SETUP.md, and README.md
- The NL zip imports into Local WP with theme active, plugins active, and placeholder content visible
- SETUP.md is present in the zip root with priority-ordered setup guidance
- build.json records the NL prompt, selected theme, installed plugins, and content counts
- `/build --visual ./figma-export/` triggers the full visual pipeline (14 steps) and produces a zip with a custom FSE block theme, SETUP.md, and README.md
- The visual zip imports into Local WP with the custom-{slug} theme active and editable in Site Editor
- `/build --visual ./screenshot.png` triggers the screenshot path and produces a custom theme based on visual analysis
- build.json records mode=visual, visual_input type, theme slug, and extracted token counts
- Visual builds produce 4 git commits: scaffold, mcp, init (custom theme + activation), setup — one fewer than NL mode because the theme IS the init in visual mode
- `/build --from-url https://example.com` routes through the complete URL pipeline (scrape → sanitise → visual FSE → zip) and produces a valid Local WP zip with FSE block theme reproducing the source's visual structure
- No scraped text or images appear verbatim in the URL clone output — all content is AI-generated placeholder prose
- scrape.json is included at the zip root alongside database.sql, README.md, and SETUP.md
- SETUP.md contains the URL clone appendix with color attribution warning, dynamic feature inventory table, and pages scraped table
- URL builds produce 4 git commits: scaffold, mcp, init (custom theme + activation), setup — matching the visual build commit pattern
- Prerequisite checks fail fast with clear error messages when Docker or WP-CLI is missing
- `--wp-version X.Y` flag is parsed and passed through to the build-scaffold skill
- Build summary shows absolute zip path, build directory, and admin credentials
- Docker container is always cleaned up, even on build failure
- `git log` in the build directory shows 2 commits (blank) or 5 commits (NL) with conventional `build()` prefixes
- `.gitignore` excludes WP core, mcp-adapter/, uploads/, cache/, database.sql, and WP.org-sourced plugin/theme slugs
- Zip archives include `.git/` and `.gitignore` so imported builds retain git history
