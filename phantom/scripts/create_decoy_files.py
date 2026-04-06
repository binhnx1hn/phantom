#!/usr/bin/env python3
"""
PHANTOM R3 - Decoy File Generator
Generates convincing personal-notes decoy files for the outer (plausible deniability)
volume of a TrueCrypt hidden container.

All generated content is entirely fictional and harmless.
Files are saved to /tmp/phantom/decoy/ (or a custom --output-dir).

Usage:
    python3 create_decoy_files.py
    python3 create_decoy_files.py --output-dir /tmp/phantom/decoy --dry-run
"""

from __future__ import annotations

import argparse
import logging
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List

# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────
DEFAULT_OUTPUT_DIR = Path("/tmp/phantom/decoy")

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
LOG_DATEFMT = "%Y-%m-%dT%H:%M:%S%z"

# ─────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, datefmt=LOG_DATEFMT,
                    handlers=[logging.StreamHandler(sys.stdout)])
log = logging.getLogger("phantom.decoy")


# ─────────────────────────────────────────────
# Random content helpers
# ─────────────────────────────────────────────
def _random_date(days_back: int = 180) -> str:
    """Return a random past date as a human-readable string (YYYY-MM-DD)."""
    delta = random.randint(0, days_back)
    d = datetime.now(tz=timezone.utc) - timedelta(days=delta)
    return d.strftime("%Y-%m-%d")


def _random_time() -> str:
    """Return a random time string HH:MM."""
    return f"{random.randint(7, 23):02d}:{random.randint(0, 59):02d}"


def _pick(*items: str) -> str:
    """Pick a random item from the provided arguments."""
    return random.choice(items)


# ─────────────────────────────────────────────
# Individual decoy file generators
# ─────────────────────────────────────────────

def _generate_personal_diary() -> str:
    """Generate a short personal diary entry."""
    moods = ["tired", "energetic", "a bit stressed", "content", "bored", "focused"]
    activities = [
        "went for a jog around the park",
        "cooked pasta for dinner",
        "watched a documentary about oceans",
        "read 30 pages of that novel I started last month",
        "met up with Minh for coffee",
        "spent the afternoon organising my bookshelf",
        "did laundry and cleaned the apartment",
        "video-called my parents",
    ]
    thoughts = [
        "I should start waking up earlier.",
        "Need to drink more water — I keep forgetting.",
        "Maybe it is time to start learning a new language.",
        "Work deadlines are piling up but I will manage.",
        "The weather has been unusually warm lately.",
        "Thinking about taking a short trip next month.",
        "I want to cook more at home and eat out less.",
    ]
    date = _random_date(60)
    mood = _pick(*moods)
    activity = _pick(*activities)
    thought = _pick(*thoughts)
    return (
        f"Personal Diary\n"
        f"==============\n\n"
        f"Date: {date}\n\n"
        f"Feeling {mood} today. {activity.capitalize()}.\n\n"
        f"{thought}\n\n"
        f"Also need to:\n"
        f"  - Call the dentist for an appointment\n"
        f"  - Return borrowed book to Lan\n"
        f"  - Renew gym membership before end of month\n\n"
        f"--- end of entry ---\n"
    )


def _generate_todo_list() -> str:
    """Generate a personal to-do list."""
    date = _random_date(14)
    items = [
        "Buy groceries (eggs, bread, vegetables, yogurt)",
        "Pay electricity bill online",
        "Reply to email from university alumni group",
        "Finish reading chapter 7 of 'Atomic Habits'",
        "Schedule annual health check-up",
        "Clean out old clothes and donate",
        "Fix leaky kitchen tap — call landlord",
        "Update CV / LinkedIn profile",
        "Sort out tax documents for this quarter",
        "Back up photos from phone to laptop",
        "Get a haircut",
        "Return library books (overdue!)",
    ]
    random.shuffle(items)
    selected = items[:random.randint(5, 9)]
    lines = "\n".join(f"  [ ] {item}" for item in selected)
    return (
        f"TODO — {date}\n"
        f"{'=' * (7 + len(date))}\n\n"
        f"{lines}\n\n"
        f"Reminder: budget review on the last Friday of the month.\n"
    )


def _generate_shopping_list() -> str:
    """Generate a grocery / shopping list."""
    categories = {
        "Produce": ["apples", "bananas", "spinach", "tomatoes", "carrots", "garlic", "ginger"],
        "Dairy": ["milk (1L)", "yogurt", "cheddar cheese", "butter"],
        "Pantry": ["instant noodles", "rice (2 kg)", "olive oil", "soy sauce", "fish sauce"],
        "Snacks": ["dark chocolate", "almonds", "crackers"],
        "Household": ["dish soap", "toilet paper", "laundry detergent", "trash bags"],
    }
    lines = [f"Shopping List — {_random_date(7)}\n{'=' * 28}\n"]
    for cat, options in categories.items():
        random.shuffle(options)
        selected = options[:random.randint(2, 4)]
        lines.append(f"\n{cat}:")
        lines.extend(f"  - {item}" for item in selected)
    lines.append(f"\n\nEstimated budget: {random.randint(200, 600):,} VND × 1000\n")
    return "\n".join(lines)


def _generate_meeting_notes() -> str:
    """Generate fake work meeting notes."""
    projects = ["Project Alpha", "Q3 Budget Review", "Team Sync", "Product Roadmap",
                 "Infrastructure Planning", "Marketing Campaign Brief"]
    attendees = ["Linh", "Duc", "Mai", "Tuan", "Nam", "Hoa", "Khoa", "An"]
    project = _pick(*projects)
    random.shuffle(attendees)
    present = attendees[:random.randint(3, 5)]
    date = _random_date(30)
    time_str = _random_time()
    action_items = [
        "Prepare slides for next Friday presentation",
        "Send updated report to stakeholders by EOD Thursday",
        "Review pull requests before end of sprint",
        "Schedule follow-up meeting for next week",
        "Update project timeline in shared spreadsheet",
        "Collect feedback from client survey",
    ]
    random.shuffle(action_items)
    actions = action_items[:3]
    return (
        f"Meeting Notes — {project}\n"
        f"{'=' * (17 + len(project))}\n\n"
        f"Date:      {date}\n"
        f"Time:      {time_str}\n"
        f"Attendees: {', '.join(present)}\n\n"
        f"Discussion:\n"
        f"  - Reviewed progress from last sprint.\n"
        f"  - Identified blockers: dependencies on external API, delayed vendor response.\n"
        f"  - Agreed to adjust timeline by 1 week.\n"
        f"  - Brief update on budget: within limits for now.\n\n"
        f"Action Items:\n"
        + "\n".join(f"  [{_pick('Linh', 'Duc', 'Mai')}] {action}" for action in actions)
        + "\n\nNext meeting: TBD\n"
    )


def _generate_book_notes() -> str:
    """Generate reading notes / book summary."""
    books = [
        ("Atomic Habits", "James Clear"),
        ("Deep Work", "Cal Newport"),
        ("The Pragmatic Programmer", "David Thomas & Andrew Hunt"),
        ("Clean Code", "Robert C. Martin"),
        ("Sapiens", "Yuval Noah Harari"),
        ("The Psychology of Money", "Morgan Housel"),
    ]
    title, author = _pick(*books)
    quotes = [
        "Small habits compound over time into remarkable results.",
        "Focus is a skill that must be deliberately practised.",
        "Every line of code is a communication to the next reader.",
        "Systems beat goals — design your environment for success.",
        "Understanding history helps us understand ourselves.",
        "Wealth is what you don't spend — financial freedom requires patience.",
    ]
    quote = _pick(*quotes)
    return (
        f"Reading Notes\n"
        f"=============\n\n"
        f"Book:   {title}\n"
        f"Author: {author}\n"
        f"Date:   {_random_date(90)}\n\n"
        f"Key Takeaways:\n"
        f"  1. {quote}\n"
        f"  2. Consistency over intensity — show up daily.\n"
        f"  3. Track progress to stay motivated.\n\n"
        f"Favourite quote:\n"
        f"  \"{quote}\"\n\n"
        f"Rating: {random.randint(3, 5)}/5 stars\n"
        f"Would recommend: {'Yes' if random.random() > 0.3 else 'Maybe'}\n"
    )


def _generate_budget_notes() -> str:
    """Generate a simple personal monthly budget note."""
    month_names = ["January", "February", "March", "April", "May", "June",
                   "July", "August", "September", "October", "November", "December"]
    now = datetime.now(tz=timezone.utc)
    month = month_names[now.month - 1]
    year = now.year
    income = random.randint(12, 25) * 1_000_000
    rent = random.randint(3, 6) * 1_000_000
    food = random.randint(2, 4) * 1_000_000
    transport = random.randint(500, 1500) * 1000
    entertainment = random.randint(300, 900) * 1000
    total_expenses = rent + food + transport + entertainment
    savings = income - total_expenses
    return (
        f"Monthly Budget — {month} {year}\n"
        f"{'=' * (17 + len(month) + len(str(year)))}\n\n"
        f"Income:\n"
        f"  Salary:              {income:>12,} VND\n\n"
        f"Expenses:\n"
        f"  Rent:                {rent:>12,} VND\n"
        f"  Food & groceries:    {food:>12,} VND\n"
        f"  Transport:           {transport:>12,} VND\n"
        f"  Entertainment:       {entertainment:>12,} VND\n"
        f"  ─────────────────────────────────\n"
        f"  Total expenses:      {total_expenses:>12,} VND\n\n"
        f"Savings this month:  {savings:>12,} VND\n\n"
        f"Notes:\n"
        f"  - Should reduce eating out.\n"
        f"  - Save at least 20% of income next month.\n"
    )


# ─────────────────────────────────────────────
# Master generator list
# ─────────────────────────────────────────────
# Each entry: (filename, generator_function)
DECOY_FILE_SPECS: List[tuple] = [
    ("diary.txt",         _generate_personal_diary),
    ("todo.txt",          _generate_todo_list),
    ("shopping.txt",      _generate_shopping_list),
    ("meeting_notes.txt", _generate_meeting_notes),
    ("book_notes.txt",    _generate_book_notes),
    ("budget.txt",        _generate_budget_notes),
]


# ─────────────────────────────────────────────
# Main: generate all decoy files
# ─────────────────────────────────────────────
def generate_decoy_files(output_dir: Path, dry_run: bool = False) -> List[Path]:
    """Generate all decoy files and write them to output_dir.

    Each call regenerates files with fresh random content (idempotent — safe
    to call multiple times; existing files are overwritten).

    Args:
        output_dir: Destination directory for the generated files.
        dry_run:    If True, log what would be written but do not touch disk.

    Returns:
        List of Path objects for all successfully written files.
    """
    ts = datetime.now(tz=timezone.utc).isoformat()
    log.info("═══ Decoy File Generator started at %s ═══", ts)
    log.info("Output dir: %s | Dry-run: %s", output_dir, dry_run)

    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)
        log.info("Output directory ready: %s", output_dir)

    written: List[Path] = []
    for filename, generator in DECOY_FILE_SPECS:
        dest = output_dir / filename
        content = generator()
        if dry_run:
            log.info(
                "[DRY-RUN] Would write %s (%d bytes).",
                dest,
                len(content.encode("utf-8")),
            )
            written.append(dest)
        else:
            try:
                dest.write_text(content, encoding="utf-8")
                log.info(
                    "Written: %s (%d bytes).",
                    dest,
                    dest.stat().st_size,
                )
                written.append(dest)
            except OSError as exc:
                log.error("Failed to write %s: %s", dest, exc)

    log.info(
        "═══ Decoy generation complete — %d/%d file(s) written ═══",
        len(written),
        len(DECOY_FILE_SPECS),
    )
    return written


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="PHANTOM R3 — Generate decoy files for outer TrueCrypt volume",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate to default directory (/tmp/phantom/decoy)
  python3 create_decoy_files.py

  # Custom output directory
  python3 create_decoy_files.py --output-dir /data/decoy

  # Dry-run (no files written)
  python3 create_decoy_files.py --dry-run
        """,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory to write decoy files into (default: {DEFAULT_OUTPUT_DIR}).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be written without creating any files.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    written = generate_decoy_files(args.output_dir, dry_run=args.dry_run)
    return 0 if written else 1


if __name__ == "__main__":
    sys.exit(main())
