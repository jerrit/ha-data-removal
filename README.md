# Data Removal — Home Assistant Add-on

A Home Assistant add-on that monitors 35+ data broker websites for your personal
information and automates opt-out removal requests — all from a web dashboard
running inside your Home Assistant instance.

**Your data never leaves your home.** No cloud accounts, no external services, no
subscriptions. The add-on runs a headless Chromium browser locally and talks
directly to each data broker site.

---

## Features

- **35 sites monitored out of the box** — Whitepages, Spokeo, BeenVerified, Radaris,
  MyLife, Intelius, PeopleFinders, and more
- **Automated opt-out requests** — the bot fills out removal forms for you
- **Email template generator** — one-click copy for sites that require an email
- **Multi-user support** — monitor your whole family from a single add-on
- **Auto-rescans** — sites are rechecked 30 days after a removal request
- **Live scan progress** — real-time progress bar as each site is checked
- **Add custom sites** — register any data broker not already in the list
- **Optional UI password** — lock the dashboard behind a password
- **Persistent storage** — all data survives add-on restarts and HA reboots

---

## Installation

This add-on is not in the official Home Assistant add-on store. You add it as a
custom repository.

1. In Home Assistant, go to **Settings → Add-ons → Add-on Store**
2. Click the menu (⋮) in the top-right corner and select **Repositories**
3. Paste the repository URL and click **Add**:
   ```
   https://github.com/jerrit/ha-data-removal
   ```
4. Close the dialog — the **Data Removal** add-on will appear in the store
5. Click **Install**, wait for the image to build, then click **Start**
6. Open the **Web UI** to set up your first user profile

> **Note:** The first build takes several minutes because it compiles Chromium.
> Subsequent starts are fast.

---

## Configuration

Open **Settings → Add-ons → Data Removal → Configuration** in Home Assistant.

| Option | Required | Description |
|--------|----------|-------------|
| `secret_key` | No | Flask session secret key. Leave blank to auto-generate a persistent key stored in `/data`. |
| `web_password` | No | Password to lock the web UI. Leave blank for open access. |

Personal information (name, city, state, email, phone) is entered through the
**web UI** after first start — not through the add-on configuration.

---

## First Run

1. Start the add-on and open the **Web UI**
2. You'll see a prompt: *"No user profile yet"* — click **Add a profile**
3. Fill in your first name, last name, and location details
4. Click **Scan All Sites** in the top navbar to run your first scan
5. For any site showing **Found**, click **Submit Opt-Out Request**

---

## Dashboard

The dashboard shows every monitored site and its current status for the active user:

| Status | Meaning |
|--------|---------|
| 🔴 Found | Your data is visible — submit an opt-out |
| 🟡 Removal Requested | Opt-out submitted — waiting for the site to process |
| ✅ Removed | Confirmed removed — will be rescanned automatically in 30 days |
| ⚪ Not Found | Clean — rescanned on schedule |
| 🚫 Blocked | The site blocked the scanner (rate limiting) |

---

## Multi-User

Each person in your household gets their own profile and separate scan history.
Use **Manage Users** in the navbar to add profiles. Switch between them with
the person icon in the top-right of every page.

---

## Adding Custom Sites

Click **Add Site** in the navbar. The key field is the **Search URL Template** —
replace your name and state in the site's search URL with placeholders:

```
https://example.com/people/john-smith/illinois
→ https://example.com/people/{first_last}/{state_full}
```

Available placeholders: `{first}` `{last}` `{city}` `{state}` `{state_full}`
`{first_last}` `{name}`

---

## Privacy

- All personal data is stored only in the add-on's `/data/` directory on your
  Home Assistant machine
- The add-on makes no outbound connections except to the data broker sites
  themselves during a scan
- Chromium requests mimic normal browser traffic (realistic user-agent, pacing)
- No telemetry, no analytics, no external APIs

---

## Changelog

See [CHANGELOG.md](data-removal/CHANGELOG.md).
