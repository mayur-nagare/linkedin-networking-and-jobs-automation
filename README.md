# 🤖 LinkedIn Job Application & Networking Bot

A semi-automated Python tool to speed up your job search on LinkedIn.

## ✨ Features

| Feature | Description |
|---|---|
| 🚀 **Easy Apply** | Auto-applies to LinkedIn Easy Apply jobs matching your keywords |
| 🤝 **HR Networking** | Finds HR managers & recruiters at target companies, sends personalized connection requests |
| 💬 **Smart Messages** | Rotates personalized message templates so each note feels unique |
| 📊 **Activity Tracker** | SQLite database logs every application and connection |
| 📋 **Dashboard** | Interactive CLI dashboard to update statuses, view stats, export CSV |

---

## 📁 Project Structure

```
linkedin_bot/
├── linkedin_bot.py      ← Main bot (apply + connect)
├── dashboard.py         ← Tracker & dashboard CLI
├── setup.py             ← First-time setup wizard
├── requirements.txt
├── config/
│   └── settings.json    ← Job search, networking, messages (not credentials)
├── .env                 ← Credentials & profile (copy from .env.example; do not commit)
├── .env.example         ← Template for .env
├── data/
│   └── tracker.db       ← SQLite database (auto-created)
├── logs/
│   └── bot.log          ← Activity log
└── screenshots/         ← Error screenshots for debugging
```

---

## 🚀 Quick Start

### 1. Install & Configure
```bash
cd linkedin_bot
python setup.py
```
This installs dependencies and walks you through configuration.

### 2. Run the Bot
```bash
# Apply to jobs + connect with HR (recommended)
python linkedin_bot.py --mode all

# Just apply to jobs
python linkedin_bot.py --mode apply

# Just send connection requests
python linkedin_bot.py --mode connect

# View activity report
python linkedin_bot.py --mode report
```

### 3. Use the Dashboard
```bash
python dashboard.py              # Interactive menu
python dashboard.py --stats      # Quick stats overview
python dashboard.py --export csv # Export to CSV files
```

---

## ⚙️ Configuration

### Credentials & profile (`.env`)

Copy `.env.example` to `.env` and set your LinkedIn credentials and profile. **Do not commit `.env`.**

```bash
cp .env.example .env
# Edit .env: LINKEDIN_EMAIL, LINKEDIN_PASSWORD, PROFILE_* fields
```

| Variable | Description |
|----------|-------------|
| `LINKEDIN_EMAIL` | LinkedIn login email |
| `LINKEDIN_PASSWORD` | LinkedIn password |
| `PROFILE_FIRST_NAME` / `PROFILE_LAST_NAME` | Your name |
| `PROFILE_PHONE` | Phone (e.g. for applications) |
| `PROFILE_TARGET_ROLE` | Target job role |
| `PROFILE_YEARS_EXPERIENCE` | Years of experience |

### Job search & networking (`config/settings.json`)

This file controls search preferences, networking behavior, and connection message templates. Credentials and profile are read from `.env`.

```json
{
  "job_search": {
    "keywords": [
      "Software Engineer",
      "Python Developer",
      "Backend Engineer",
      "Full Stack Developer"
    ],
    "location": "San Francisco Bay Area",
    "date_posted": "r604800",
    "max_applications_per_run": 15
  },

  "networking": {
    "max_connections_per_run": 20,
    "location": "San Francisco Bay Area",
    "hr_keywords": [
      "Technical Recruiter",
      "HR Manager",
      "Talent Acquisition",
      "Recruiter",
      "People Operations",
      "HR Business Partner"
    ]
  },

  "connection_messages": [
    "Hi {first_name}, I'm a {your_role} actively exploring new opportunities and would love to connect with you. Looking forward to staying in touch!"
  ]
}
```

### Message Template Placeholders

You can customize the `connection_messages` array with your own templates. Common placeholders:

| Placeholder | Meaning |
|---|---|
| `{first_name}` | Contact's first name (this is the only placeholder auto-filled by default) |
| `{your_role}` | Your target role from `profile.target_role` (requires extending the code if you want automatic substitution) |
| `{company}` | The person's company (requires extending the code if you want automatic substitution) |

> **Note:** By default, the bot only replaces `{first_name}` when sending messages. The other placeholders are included as suggestions if you decide to extend `generate_connection_note` in `linkedin_bot.py`.

---

## 📊 Dashboard — Application Statuses

Update statuses as your job search progresses:

**Applications:** `Applied` → `Interviewing` → `Offer` / `Rejected` / `Withdrawn` / `Ghosted`

**Connections:** `Pending` → `Accepted` / `Declined` / `No Response`

---

## ⚠️ Safety Guidelines

| Rule | Why |
|---|---|
| Max **15-20 applications/day** | Avoid triggering LinkedIn's bot detection |
| Max **20-25 connections/day** | LinkedIn limits invites; exceeding risks account restriction |
| Run at **varied times** | Don't run at the exact same time every day |
| **Don't run 24/7** | LinkedIn monitors unusual activity patterns |
| Expect **manual CAPTCHA** on first login | The bot will pause and ask you to solve it |

---

## 🛠️ Troubleshooting

**Bot can't find apply button:**
LinkedIn frequently updates their CSS selectors. Check `logs/bot.log` and update selectors in `linkedin_bot.py` if needed.

**Login fails / CAPTCHA loop:**
- Run without `--headless` so you can see the browser
- Complete the CAPTCHA manually when prompted

**"Element not found" errors:**
LinkedIn's UI changes often. The bot is designed to skip problematic listings gracefully.

---

## 📦 Requirements

- **Python**: 3.8+ (tested with 3.12)
- **Dependencies**: install with:

  ```bash
  pip install -r requirements.txt
  # or simply run the setup wizard, which also installs Playwright:
  python setup.py
  ```

- **Browser**: No separate Chrome install is required — Playwright downloads its own Chromium binary.

---

*Use responsibly. This tool is for personal job searching only.*