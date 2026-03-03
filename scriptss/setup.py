#!/usr/bin/env python3
"""
Quick setup script — run this first before using the bot.
"""
import subprocess
import sys
import json
from pathlib import Path


def install_deps():
    repo_root = Path(__file__).resolve().parent.parent
    reqs_file = repo_root / "requirements.txt"
    print("📦 Installing dependencies...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(reqs_file)])
    print("🌐 Installing Playwright browsers (Chromium)...")
    subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
    print("✅ Dependencies installed.\n")


def setup_config():
    repo_root = Path(__file__).resolve().parent.parent
    config_path = repo_root / "config" / "settings.json"
    env_path = repo_root / ".env"
    with open(config_path) as f:
        config = json.load(f)

    # Load existing .env for prompt defaults
    env_vars = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env_vars[k.strip()] = v.strip().strip('"').strip("'")

    cred = config.get("credentials", {})
    prof = config.get("profile", {})

    print("=" * 50)
    print("  LinkedIn Bot — Initial Setup")
    print("=" * 50)
    print("\nLet's configure your settings.\n")

    email = input(f"LinkedIn Email [{env_vars.get('LINKEDIN_EMAIL', cred.get('email', ''))}]: ").strip()
    password = input("LinkedIn Password: ").strip()
    name = input(f"Your full name [{env_vars.get('PROFILE_FIRST_NAME', prof.get('first_name', ''))} {env_vars.get('PROFILE_LAST_NAME', prof.get('last_name', ''))}]: ").strip()
    phone = input(f"Phone [{env_vars.get('PROFILE_PHONE', prof.get('phone', ''))}]: ").strip()
    role = input(f"Target job role [{env_vars.get('PROFILE_TARGET_ROLE', prof.get('target_role', ''))}]: ").strip()
    years_exp = input(f"Years experience [{env_vars.get('PROFILE_YEARS_EXPERIENCE', prof.get('years_experience', ''))}]: ").strip()

    # Write .env (credentials and profile only)
    first = (name.split()[0] if name and " " in name else name or env_vars.get("PROFILE_FIRST_NAME", "John"))
    last = (name.split()[-1] if name and " " in name else env_vars.get("PROFILE_LAST_NAME", ""))
    env_lines = [
        "# Credentials and profile — do not commit .env",
        f"LINKEDIN_EMAIL={email or env_vars.get('LINKEDIN_EMAIL', 'your_email@gmail.com')}",
        f"LINKEDIN_PASSWORD={password or env_vars.get('LINKEDIN_PASSWORD', '')}",
        f"PROFILE_FIRST_NAME={first}",
        f"PROFILE_LAST_NAME={last}",
        f"PROFILE_PHONE={phone or env_vars.get('PROFILE_PHONE', '')}",
        f"PROFILE_TARGET_ROLE={role or env_vars.get('PROFILE_TARGET_ROLE', 'Software Engineer')}",
        f"PROFILE_YEARS_EXPERIENCE={years_exp or env_vars.get('PROFILE_YEARS_EXPERIENCE', '3')}",
    ]
    env_path.write_text("\n".join(env_lines) + "\n")
    print("  → Credentials and profile saved to .env")

    print("\n── Job Search ──")
    location = input(f"Job location [{config['job_search']['location']}]: ").strip()
    if location:
        config["job_search"]["location"] = location

    keywords_input = input(
        f"Job keywords (comma-separated) [{', '.join(config['job_search']['keywords'])}]: "
    ).strip()
    if keywords_input:
        config["job_search"]["keywords"] = [k.strip() for k in keywords_input.split(",")]

    max_apps = input(f"Max applications per run [{config['job_search']['max_applications_per_run']}]: ").strip()
    if max_apps.isdigit():
        config["job_search"]["max_applications_per_run"] = int(max_apps)

    print("\n── Networking ──")
    net_location = input(f"Location for recruiter search [{config['networking'].get('location', '')}]: ").strip()
    if net_location:
        config["networking"]["location"] = net_location

    hr_input = input(
        f"HR role keywords (comma-separated) [{', '.join(config['networking'].get('hr_keywords', [])[:3])}...]: "
    ).strip()
    if hr_input:
        config["networking"]["hr_keywords"] = [k.strip() for k in hr_input.split(",")]

    max_conn = input(f"Max connection requests per run [{config['networking']['max_connections_per_run']}]: ").strip()
    if max_conn.isdigit():
        config["networking"]["max_connections_per_run"] = int(max_conn)

    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    print("\n✅ Configuration saved to config/settings.json and .env\n")


def create_dirs():
    repo_root = Path(__file__).resolve().parent.parent
    for d in ["config", "data", "logs", "screenshots"]:
        (repo_root / d).mkdir(exist_ok=True)


if __name__ == "__main__":
    create_dirs()
    install_deps()
    setup_config()

    print("=" * 50)
    print("  Setup Complete! 🎉")
    print("=" * 50)
    print("""
Next steps:
  1. Run the bot:
       python3 linkedin_bot.py --mode all       # Apply + Connect
       python3 linkedin_bot.py --mode apply     # Jobs only
       python3 linkedin_bot.py --mode connect   # Networking only
       python3 linkedin_bot.py --headless       # No browser window

  2. View your dashboard:
       python3 dashboard.py                     # Interactive menu
       python3 dashboard.py --stats             # Quick stats
       python3 dashboard.py --export csv        # Export to CSV

  Tips:
    • Keep max_applications_per_run ≤ 20/day
    • Keep max_connections_per_run ≤ 25/day
    • First login may show CAPTCHA — bot will pause for you

⚠️  Playwright downloads its own Chromium — no Chrome install needed!
""")