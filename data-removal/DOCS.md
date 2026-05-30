# Data Removal — Documentation

## Overview

This add-on monitors 35+ data broker websites (Whitepages, Spokeo, Radaris, etc.)
for your personal information and helps you submit opt-out removal requests.
All data is stored locally in the add-on — nothing is sent to external services.

## Initial Setup

1. Install and start the add-on, then open the **Web UI**
2. You'll see a prompt: *"No user profile yet"* — click **Add a profile**
3. Enter your first name, last name, and any optional details (city, state, email, phone)
4. Click **Scan All Sites** in the navbar to run your first scan

## Configuration Options

| Option | Required | Description |
|--------|----------|-------------|
| `secret_key` | No | Flask session secret key. Leave blank to auto-generate a persistent key stored in `/data/`. |
| `web_password` | No | Password to lock the web UI. Leave blank for open access (default). |

Personal information is not stored in the add-on configuration — use the
**Manage Users** section of the web UI instead.

## How It Works

### Scanning

Click **Scan All Sites** in the navbar to start a scan. The add-on opens a
headless Chromium browser, visits each data broker site, and checks whether
your name and location appear in their database.

### Opt-Out Requests

For sites where your data was found, click **Submit Opt-Out Request**. The bot
navigates to the site's removal form, fills it in with your details, and logs
the result. Most sites then send an email verification — you click that link
yourself to complete the removal.

Sites that use email-based removal (MyLife, Radaris) generate a pre-written email
you can copy with one click and send yourself.

### Monitoring

The dashboard shows the current status of every site:

| Status | Meaning |
|--------|---------|
| 🔴 Found | Your data is visible — submit an opt-out |
| 🟡 Removal Requested | Opt-out submitted — waiting for removal |
| ✅ Removed | Confirmed removed — rescanned automatically in 30 days |
| ⚪ Not Found | Clean — rescanned on schedule |
| 🚫 Blocked | Site is rate-limiting the scanner |

### Automatic Rescans

Sites marked *Removal Requested* are automatically rescanned 30 days after the
opt-out was submitted. The scheduler runs in the background — you don't need to
do anything.

## Multi-User

You can monitor multiple people from the same add-on. Use **Manage Users** in
the navbar to add additional profiles. Each person's scan history is tracked
separately. Switch between users with the person icon in the top-right navbar.

## Adding Custom Sites

Click **Add Site** in the navbar to register a new data broker. The most
important field is the **Search URL Template** — replace your name and state
in the site's people-search URL with placeholders:

```
https://example.com/people/john-smith/il
→ https://example.com/people/{first_last}/{state}
```

Available placeholders: `{first}` `{last}` `{city}` `{state}` `{state_full}`
`{first_last}` `{name}`

## Password Protection

Set `web_password` in the add-on configuration to require a password before
anyone can access the web UI. Leave it blank to keep the UI open (default).

When a password is set, a **Lock** button appears in the navbar so you can
manually lock the session.

## Privacy

- All personal information is stored only in the add-on's `/data/` directory
- No data is transmitted to external servers by the add-on itself
- The headless browser makes requests directly to data broker sites
- Chromium requests look like normal browser traffic
