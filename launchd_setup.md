# Running the job alert automatically on your Mac (via launchd)

`launchd` is macOS's native background task scheduler -- more reliable than
`cron` on modern macOS, since cron jobs can silently get blocked by macOS's
background-permission restrictions.

## Step 1: Find your Python path

In Terminal:
```
which python3
```
Copy the output (e.g. `/usr/bin/python3` or `/opt/homebrew/bin/python3`).

## Step 2: Decide where the project lives

```
mkdir -p ~/Projects/job-alert
mv ~/Downloads/job_alert.py ~/Downloads/ADDING_COMPANIES.md ~/Projects/job-alert/
```

## Step 3: Allow Terminal/osascript to send notifications

The first time the script runs, macOS will ask for permission to show
notifications -- click Allow. If you don't see the prompt, go to
System Settings > Notifications and make sure Script Editor / Terminal
is allowed to send notifications.

## Step 4: Create the launchd config file

Create a file at:
```
~/Library/LaunchAgents/com.raunaq.jobalert.plist
```

With this content (replace the paths and python3 path with your actual
ones from Step 1):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.raunaq.jobalert</string>

    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Users/yourname/Projects/job-alert/job_alert.py</string>
    </array>

    <!-- Runs every 300 seconds = 5 minutes -->
    <key>StartInterval</key>
    <integer>300</integer>

    <key>RunAtLoad</key>
    <true/>

    <key>StandardOutPath</key>
    <string>/Users/yourname/Projects/job-alert/output.log</string>

    <key>StandardErrorPath</key>
    <string>/Users/yourname/Projects/job-alert/error.log</string>
</dict>
</plist>
```

## Step 5: Load it

```
launchctl load ~/Library/LaunchAgents/com.raunaq.jobalert.plist
```

It runs immediately, then every 5 minutes, across every company in your
COMPANIES list, even across reboots (as long as you're logged in).

## Useful commands

Check it's running:
```
launchctl list | grep jobalert
```

Stop it:
```
launchctl unload ~/Library/LaunchAgents/com.raunaq.jobalert.plist
```

Watch live output:
```
tail -f ~/Projects/job-alert/output.log
```

Browse your full permanent archive of every job ever found, across every
company, relevant or not:
```
cat ~/Projects/job-alert/all_new_jobs.log
```
