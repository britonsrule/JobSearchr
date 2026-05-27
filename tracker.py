"""
Application Tracker for Jeremiah Marett
---------------------------------------
Tracks job applications for both personal search management
and Washington State weekly unemployment claims.

Usage:
  python tracker.py add       — log a new application (interactive)
  python tracker.py list      — show all applications
  python tracker.py week      — show this week's applications (for UI claim)
  python tracker.py summary   — show counts by status
"""

import csv
import os
import sys
from datetime import datetime, date, timedelta

TRACKER_FILE = "applications.csv"

COLUMNS = [
    "date_applied",       # YYYY-MM-DD
    "employer_name",      # Company name
    "job_title",          # Title of the role
    "job_url",            # Posting URL
    "resume_used",        # Which resume version was submitted
    "source",             # Where you found it (LinkedIn, Indeed, Referral, etc.)
    "status",             # Applied / Phone Screen / Interview / Offer / Rejected / Withdrawn
    "notes",              # Any freeform notes
]

VALID_STATUSES = ["Applied", "Phone Screen", "Interview", "Offer", "Rejected", "Withdrawn"]

# ─────────────────────────────────────────────
# FILE HELPERS
# ─────────────────────────────────────────────

def init_tracker():
    """Create the CSV with headers if it doesn't exist."""
    if not os.path.exists(TRACKER_FILE):
        with open(TRACKER_FILE, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=COLUMNS)
            writer.writeheader()
        print(f"  Created {TRACKER_FILE}")

def load_applications() -> list[dict]:
    init_tracker()
    with open(TRACKER_FILE, "r", newline="") as f:
        return list(csv.DictReader(f))

def save_application(entry: dict):
    init_tracker()
    with open(TRACKER_FILE, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writerow(entry)

def update_applications(apps: list[dict]):
    with open(TRACKER_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(apps)

# ─────────────────────────────────────────────
# DISPLAY HELPERS
# ─────────────────────────────────────────────

def print_divider():
    print("─" * 70)

def print_app(app: dict, index: int = None):
    prefix = f"  [{index}] " if index is not None else "  "
    print(f"{prefix}{app['date_applied']}  {app['employer_name']}  —  {app['job_title']}")
    print(f"       Status: {app['status']}  |  Resume: {app['resume_used']}  |  Source: {app['source']}")
    if app.get("job_url"):
        print(f"       URL: {app['job_url']}")
    if app.get("notes"):
        print(f"       Notes: {app['notes']}")

# ─────────────────────────────────────────────
# COMMANDS
# ─────────────────────────────────────────────

def cmd_add():
    """Interactively log a new application."""
    print(f"\n{'='*70}")
    print("  LOG NEW APPLICATION")
    print(f"{'='*70}\n")

    def prompt(label, default=None, options=None):
        if options:
            print(f"  Options: {', '.join(options)}")
        hint = f" [{default}]" if default else ""
        val = input(f"  {label}{hint}: ").strip()
        if not val and default:
            return default
        if options and val not in options:
            print(f"  Invalid — choosing 'Applied' as default.")
            return "Applied"
        return val

    today = date.today().isoformat()

    entry = {
        "date_applied": prompt("Date applied (YYYY-MM-DD)", default=today),
        "employer_name": prompt("Employer name"),
        "job_title":     prompt("Job title"),
        "job_url":       prompt("Job posting URL (or leave blank)", default=""),
        "resume_used":   prompt("Resume used", default="JeremiahMarett_GoogleTPgM.docx"),
        "source":        prompt("Source (LinkedIn / Indeed / Referral / Company Site / Other)", default="LinkedIn"),
        "status":        prompt("Status", default="Applied", options=VALID_STATUSES),
        "notes":         prompt("Notes (optional)", default=""),
    }

    save_application(entry)
    print(f"\n  ✓ Logged: {entry['employer_name']} — {entry['job_title']} ({entry['date_applied']})\n")


def cmd_list():
    """Show all applications sorted by date descending."""
    apps = load_applications()
    if not apps:
        print("\n  No applications logged yet. Run: python tracker.py add\n")
        return

    apps_sorted = sorted(apps, key=lambda x: x["date_applied"], reverse=True)

    print(f"\n{'='*70}")
    print(f"  ALL APPLICATIONS ({len(apps)} total)")
    print(f"{'='*70}\n")

    for i, app in enumerate(apps_sorted, 1):
        print_app(app, index=i)
        print()


def cmd_week():
    """
    Show applications for the current WA unemployment claim week.
    WA claim weeks run Sunday–Saturday.
    """
    today = date.today()
    # Find most recent Sunday
    days_since_sunday = (today.weekday() + 1) % 7
    week_start = today - timedelta(days=days_since_sunday)
    week_end = week_start + timedelta(days=6)

    apps = load_applications()
    week_apps = [
        a for a in apps
        if week_start.isoformat() <= a["date_applied"] <= week_end.isoformat()
    ]

    print(f"\n{'='*70}")
    print(f"  WEEKLY UNEMPLOYMENT CLAIM — {week_start.strftime('%b %d')} to {week_end.strftime('%b %d, %Y')}")
    print(f"  {len(week_apps)} application(s) this week")
    print(f"{'='*70}\n")

    if not week_apps:
        print("  No applications logged this week.\n")
        return

    # WA requires: employer name, job title, date, how applied
    print(f"  {'#':<4} {'Date':<12} {'Employer':<28} {'Job Title':<28}")
    print_divider()
    for i, app in enumerate(week_apps, 1):
        employer = app["employer_name"][:27]
        title = app["job_title"][:27]
        print(f"  {i:<4} {app['date_applied']:<12} {employer:<28} {title:<28}")
        print(f"       URL: {app['job_url'] or 'N/A'}")
        print(f"       Resume: {app['resume_used']}  |  Source: {app['source']}")
        print()

    print(f"  Claim week: {week_start.isoformat()} to {week_end.isoformat()}\n")


def cmd_update():
    """Update the status of an existing application."""
    apps = load_applications()
    if not apps:
        print("\n  No applications to update.\n")
        return

    apps_sorted = sorted(apps, key=lambda x: x["date_applied"], reverse=True)

    print(f"\n{'='*70}")
    print("  UPDATE APPLICATION STATUS")
    print(f"{'='*70}\n")

    for i, app in enumerate(apps_sorted, 1):
        print(f"  [{i}] {app['date_applied']}  {app['employer_name']} — {app['job_title']}  ({app['status']})")

    try:
        choice = int(input("\n  Enter number to update (0 to cancel): ").strip())
        if choice == 0 or choice > len(apps_sorted):
            return
    except ValueError:
        print("  Invalid input.")
        return

    target = apps_sorted[choice - 1]
    print(f"\n  Updating: {target['employer_name']} — {target['job_title']}")
    print(f"  Options: {', '.join(VALID_STATUSES)}")
    new_status = input(f"  New status [{target['status']}]: ").strip()
    if new_status not in VALID_STATUSES:
        print("  Invalid status — no changes made.")
        return

    new_notes = input(f"  Notes [{target['notes']}]: ").strip()

    # Update in original list (match by all fields since no unique ID)
    for app in apps:
        if (app["date_applied"] == target["date_applied"] and
            app["employer_name"] == target["employer_name"] and
            app["job_title"] == target["job_title"]):
            app["status"] = new_status
            if new_notes:
                app["notes"] = new_notes
            break

    update_applications(apps)
    print(f"\n  ✓ Updated to: {new_status}\n")


def cmd_summary():
    """Show application counts by status."""
    apps = load_applications()
    if not apps:
        print("\n  No applications logged yet.\n")
        return

    counts = {s: 0 for s in VALID_STATUSES}
    for app in apps:
        status = app.get("status", "Applied")
        if status in counts:
            counts[status] += 1

    print(f"\n{'='*70}")
    print(f"  APPLICATION SUMMARY  ({len(apps)} total)")
    print(f"{'='*70}\n")
    for status, count in counts.items():
        bar = "█" * count
        print(f"  {status:<15} {count:>3}  {bar}")

    # Active pipeline
    active = sum(1 for a in apps if a.get("status") in ["Phone Screen", "Interview", "Offer"])
    print(f"\n  Active in pipeline: {active}")
    print()


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

COMMANDS = {
    "add":     (cmd_add,     "Log a new application"),
    "list":    (cmd_list,    "Show all applications"),
    "week":    (cmd_week,    "This week's apps for unemployment claim"),
    "update":  (cmd_update,  "Update status of an application"),
    "summary": (cmd_summary, "Show counts by status"),
}

def print_usage():
    print("\n  Usage: python tracker.py <command>\n")
    for cmd, (_, desc) in COMMANDS.items():
        print(f"    {cmd:<10} {desc}")
    print()

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print_usage()
    else:
        COMMANDS[sys.argv[1]][0]()
