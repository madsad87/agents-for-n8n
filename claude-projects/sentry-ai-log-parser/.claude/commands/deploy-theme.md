Use when deploying the SEntry Portal WordPress theme to sentrysync.wpenginepowered.com. Run after making changes to the theme source code.

Run this rsync command to deploy the theme files:

```bash
rsync -avz wordpress-theme/sentry-portal/ hluna_@pod-400999.wpengine.com:/nas/content/live/sentrysync/wp-content/themes/sentry-portal/
```

After deployment, if this is the first deploy, activate the theme and create required pages:

```bash
ssh hluna_@pod-400999.wpengine.com "cd /nas/content/live/sentrysync && wp theme activate sentry-portal"
ssh hluna_@pod-400999.wpengine.com "cd /nas/content/live/sentrysync && wp post create --post_type=page --post_title=Dashboard --post_name=dashboard --post_status=publish"
ssh hluna_@pod-400999.wpengine.com "cd /nas/content/live/sentrysync && wp post create --post_type=page --post_title=Reports --post_name=reports --post_status=publish"
ssh hluna_@pod-400999.wpengine.com "cd /nas/content/live/sentrysync && wp post create --post_type=page --post_title='Request Analysis' --post_name=request --post_status=publish"
```

Then set the Dashboard page as the static front page:

```bash
ssh hluna_@pod-400999.wpengine.com "cd /nas/content/live/sentrysync && wp option update show_on_front page && wp option update page_on_front \$(wp post list --post_type=page --name=dashboard --field=ID)"
```
