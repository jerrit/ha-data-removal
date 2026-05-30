# Data Removal — Documentation

## Overview

This addon monitors 35 data broker websites (Whitepages, Spokeo, Radaris, etc.) for
your personal information and helps you submit opt-out removal requests. All data is
stored locally in the addon — nothing is sent to external services.

## Initial Setup

1. Install the addon and open **Configuration**
2. Fill in your personal details (first name, last name, city, state, email)
3. Click **Save** and **Start** the addon
4. Open the Web UI — a default user profile is created automatically from your config

## Configuration Options

| Option | Required | Description |
|--------|----------|-------------|
| `first_name` | Yes | Your first name (used in search queries) |
| `last_name` | Yes | Your last name (used in search queries) |
| `city` | No | Your city (improves search accuracy) |
| `state` | No | Two-letter state abbreviation (e.g. `IL`) |
| `state_full` | No | Full state name (e.g. `Illinois`) |
| `email` | No | Email address (used in opt-out form submissions) |
| `phone` | No | Phone number (required for some sites like Whitepages) |
| `secret_key` | No | Flask session secret — leave blank to auto-generate |

Changing personal info in Configuration takes effect after the next scan.
Existing user profiles in the web UI are not automatically updated — edit them
via **Manage Users** in the dashboard navbar.

## How It Works

### Scanning
Click **Scan All Sites** in the navbar to start a scan. The addon opens a headless
Chromium browser, visits each data broker site, and checks whether your name and
location appear in their database.

### Opt-Out Requests
For sites where your data was found, click **Submit Opt-Out Request**. The bot
navigates to the site's removal form, fills it in with your details, and logs
the result. Most sites then send an email verification — you click that link yourself.

Sites that use email-based removal (MyLife, Radaris) generate a pre-written email
you can copy with one click and send yourself.

### Monitoring
The dashboard shows the current status of every site:
- **Found** — your data is visible; submit an opt-out
- **Pending** — opt-out submitted; waiting for removal
- **Removed** — confirmed removed; scheduled for rescan in 30 days
- **Not Found** — clean; rescanned monthly
- **Blocked** — site is rate-limiting the bot

### Automatic Rescans
Sites marked *Pending* are automatically rescanned 30 days after the opt-out
request was submitted. You don't need to do anything — the scheduler runs in
the background.

## Multi-User

You can monitor multiple people from the same addon. Use **Manage Users** in the
navbar to add additional profiles. Each person's scan history is tracked separately.
Switch between users with the person icon in the top-right navbar.

## Adding Custom Sites

Click **Add Site** in the navbar to register a new data broker. The most important
field is the **Search URL Template** — replace your name/state in the site's
people-search URL with `{first}`, `{last}`, `{state}` placeholders.

Example: `https://site.com/people/john-smith/il`
becomes: `https://site.com/people/{first_last}/{state}`

## Privacy Notes

- All personal information is stored only in the addon's `/data/` directory
- No data is transmitted to external servers by the addon itself
- The headless browser makes requests directly to data broker sites
- Chromium requests look like normal browser traffic (realistic user-agent, delays)
