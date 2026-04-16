# Deploy Sentry Sync WordPress Plugin

Use when deploying the `sentry-sync` WordPress plugin to `sentrysync.wpenginepowered.com` (pod-400999) via bastion SSH. Run after making changes to the plugin source code.

## Prerequisites

- VPN connected
- SSH config with `*.wpengine.com` bastion proxy pattern
- LDAP SSH key loaded

## Deployment Steps

### Step 1: Detect SSH Username

Read `~/.ssh/config` and extract the `User` line from the `*.wpengine.com` host block. This is the WP Engine SSH username (e.g., `hluna_`).

If no matching host block is found, ask the user for their WP Engine SSH username.

### Step 2: Verify Local Plugin Files

Confirm the local plugin directory exists and contains the expected files:

```bash
ls wordpress-plugin/sentry-sync/
```

If the directory is missing or empty, stop and inform the user.

### Step 3: Deploy via rsync

Deploy the plugin files to the remote server using rsync. The `*.wpengine.com` SSH config pattern auto-routes through bastion — no special proxy flags needed.

```bash
rsync -avz wordpress-plugin/sentry-sync/ {username}@pod-400999.wpengine.com:sites/sentrysync/wp-content/plugins/sentry-sync/
```

Replace `{username}` with the SSH username detected in Step 1.

### Step 4: Verify Deployment

Confirm the plugin files were deployed correctly by listing the remote directory:

```bash
ssh {username}@pod-400999.wpengine.com "ls -la sites/sentrysync/wp-content/plugins/sentry-sync/ && echo '---' && ls sites/sentrysync/wp-content/plugins/sentry-sync/includes/"
```

### Step 5: Report Results

After deployment, report:
- SSH username used
- Number of files transferred
- Verification listing of remote plugin files
- Any errors encountered

If rsync or SSH fails, check:
1. VPN connection is active
2. SSH key is loaded (`ssh-add -l`)
3. SSH config has the `*.wpengine.com` host block with bastion proxy
