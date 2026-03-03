"""
LinkedIn Bot — Dashboard & Tracker
====================================
View, update, and export your application and connection data.

USAGE:
  python dashboard.py                   # Interactive menu
  python dashboard.py --export csv      # Export all data to CSV
  python dashboard.py --update-status   # Update application statuses
"""

import argparse
import csv
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = "data/tracker.db"


def get_conn():
    return sqlite3.connect(DB_PATH)


# ─── Display ──────────────────────────────────────────────────────────────────
def show_applications(status_filter=None):
    conn = get_conn()
    c = conn.cursor()
    if status_filter:
        c.execute("SELECT * FROM applications WHERE status=? ORDER BY applied_at ASC", (status_filter,))
    else:
        c.execute("SELECT * FROM applications ORDER BY applied_at ASC")
    rows = c.fetchall()
    conn.close()

    if not rows:
        print("  No applications found.")
        return

    print(f"\n{'ID':<5} {'Status':<15} {'Job Title':<35} {'Company':<60} {'Date':<12}")
    print("-" * 95)
    for r in rows:
        print(f"{r[0]:<5} {r[5]:<15} {r[1][:33]:<35} {r[2][:23]:<25} {r[6][:10]:<12}")
    print(f"\nTotal: {len(rows)} applications\n")


def show_connections(status_filter=None):
    conn = get_conn()
    c = conn.cursor()
    if status_filter:
        c.execute("SELECT * FROM connections WHERE status=? ORDER BY connected_at ASC", (status_filter,))
    else:
        c.execute("SELECT * FROM connections ORDER BY connected_at ASC")
    rows = c.fetchall()
    conn.close()

    if not rows:
        print("  No connections found.")
        return

    print(f"\n{'ID':<5} {'Status':<15} {'Name':<25} {'Company':<60} {'Date':<12}")
    print("-" * 90)
    for r in rows:
        print(f"{r[0]:<5} {r[6]:<15} {r[1][:23]:<25} {r[3][:28]:<30} {r[7][:10]:<12}")
    print(f"\nTotal: {len(rows)} connections\n")


def show_stats():
    conn = get_conn()
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM applications")
    total_apps = c.fetchone()[0]

    c.execute("SELECT status, COUNT(*) FROM applications GROUP BY status")
    app_statuses = c.fetchall()

    c.execute("SELECT COUNT(*) FROM connections")
    total_conn = c.fetchone()[0]

    c.execute("SELECT status, COUNT(*) FROM connections GROUP BY status")
    conn_statuses = c.fetchall()

    conn.close()

    print("\n" + "=" * 55)
    print("  📊  LINKEDIN BOT — STATISTICS DASHBOARD")
    print("=" * 55)
    print(f"\n  📋 Job Applications: {total_apps} total")
    for status, count in app_statuses:
        bar = "█" * min(count, 30)
        print(f"     {status:<20} {count:>4}  {bar}")

    print(f"\n  🤝 Connection Requests: {total_conn} total")
    for status, count in conn_statuses:
        bar = "█" * min(count, 30)
        print(f"     {status:<20} {count:>4}  {bar}")

    print("\n" + "=" * 55 + "\n")


# ─── Update ───────────────────────────────────────────────────────────────────
VALID_APP_STATUSES = ["Applied", "Interviewing", "Offer", "Rejected", "Withdrawn", "Ghosted"]
VALID_CONN_STATUSES = ["Pending", "Accepted", "Declined", "No Response"]


def update_application_status():
    show_applications()
    try:
        app_id = int(input("Enter Application ID to update: "))
        print(f"Valid statuses: {', '.join(VALID_APP_STATUSES)}")
        new_status = input("New status: ").strip()
        if new_status not in VALID_APP_STATUSES:
            print(f"Invalid status. Choose from: {VALID_APP_STATUSES}")
            return
        notes = input("Notes (optional, press Enter to skip): ").strip()

        conn = get_conn()
        c = conn.cursor()
        c.execute("UPDATE applications SET status=?, notes=? WHERE id=?", (new_status, notes, app_id))
        conn.commit()
        conn.close()
        print(f"✅ Updated application #{app_id} → {new_status}")
    except ValueError:
        print("Invalid ID.")


def update_connection_status():
    show_connections()
    try:
        conn_id = int(input("Enter Connection ID to update: "))
        print(f"Valid statuses: {', '.join(VALID_CONN_STATUSES)}")
        new_status = input("New status: ").strip()
        if new_status not in VALID_CONN_STATUSES:
            print(f"Invalid status.")
            return

        conn = get_conn()
        c = conn.cursor()
        c.execute("UPDATE connections SET status=? WHERE id=?", (new_status, conn_id))
        conn.commit()
        conn.close()
        print(f"✅ Updated connection #{conn_id} → {new_status}")
    except ValueError:
        print("Invalid ID.")


# ─── Export ───────────────────────────────────────────────────────────────────
def export_csv():
    Path("data").mkdir(exist_ok=True)
    conn = get_conn()
    c = conn.cursor()

    # Applications
    app_file = f"data/applications_{datetime.now().strftime('%Y%m%d')}.csv"
    c.execute("SELECT * FROM applications")
    rows = c.fetchall()
    with open(app_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "job_title", "company", "job_url", "status", "applied_at", "notes"])
        writer.writerows(rows)
    print(f"✅ Exported {len(rows)} applications → {app_file}")

    # Connections
    conn_file = f"data/connections_{datetime.now().strftime('%Y%m%d')}.csv"
    c.execute("SELECT * FROM connections")
    rows = c.fetchall()
    with open(conn_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "name", "company", "profile_url", "message_sent", "status", "connected_at"])
        writer.writerows(rows)
    print(f"✅ Exported {len(rows)} connections → {conn_file}")

    conn.close()


# ─── Menu ─────────────────────────────────────────────────────────────────────
def interactive_menu():
    while True:
        print("\n" + "─" * 40)
        print("  LinkedIn Bot Dashboard")
        print("─" * 40)
        print("  1. View Statistics")
        print("  2. View All Applications")
        print("  3. View All Connections")
        print("  4. Update Application Status")
        print("  5. Update Connection Status")
        print("  6. Export to CSV")
        print("  0. Exit")
        print("─" * 40)

        choice = input("  Choose: ").strip()

        if choice == "1":
            show_stats()
        elif choice == "2":
            show_applications()
        elif choice == "3":
            show_connections()
        elif choice == "4":
            update_application_status()
        elif choice == "5":
            update_connection_status()
        elif choice == "6":
            export_csv()
        elif choice == "0":
            print("Goodbye!")
            break
        else:
            print("Invalid choice.")


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--export", choices=["csv"], help="Export data")
    parser.add_argument("--stats", action="store_true", help="Show stats")
    args = parser.parse_args()

    if not Path(DB_PATH).exists():
        print("❌ No database found. Run linkedin_bot.py first.")
        return

    if args.export == "csv":
        export_csv()
    elif args.stats:
        show_stats()
    else:
        interactive_menu()


if __name__ == "__main__":
    main()