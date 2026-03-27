"""Interactive CLI for selecting which Canvas courses to sync."""
import json
from pathlib import Path
from typing import List, Dict, Optional, Set


PREFS_FILENAME = ".sync_preferences.json"


def load_preferences(data_dir: Path) -> Dict:
    """Load saved preferences from disk."""
    prefs_file = data_dir / PREFS_FILENAME
    if prefs_file.exists():
        try:
            with open(prefs_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_preferences(data_dir: Path, prefs: Dict):
    """Save preferences to disk."""
    prefs_file = data_dir / PREFS_FILENAME
    with open(prefs_file, "w", encoding="utf-8") as f:
        json.dump(prefs, f, indent=2)


def prompt_course_selection(
    courses: List[Dict],
    data_dir: Path,
) -> List[int]:
    """
    Show an interactive menu to pick which courses to sync.
    
    Remembers previous choices and pre-selects them next time.
    Returns a list of selected course IDs.
    """
    prefs = load_preferences(data_dir)
    saved_ids: Set[int] = set(prefs.get("selected_course_ids", []))
    has_saved = len(saved_ids) > 0

    # Sort courses by code for readability
    courses_sorted = sorted(courses, key=lambda c: c["course_code"])

    print("\n" + "=" * 60)
    print("  Canvas Course Selector")
    print("=" * 60)

    if has_saved:
        print("\n  Previously selected courses are marked with [*].")
        print("  Press ENTER to keep your previous selection,")
        print("  or type new numbers to change it.\n")
    else:
        print("\n  Select which courses to sync.\n")

    # Display numbered list
    for i, course in enumerate(courses_sorted, 1):
        marker = "*" if course["id"] in saved_ids else " "
        print(f"  [{marker}] {i:>2}. {course['course_code']:<20s} {course['name']}")

    print()
    print(f"  {'a':>4}. Select ALL courses")
    print(f"  {'n':>4}. Select NONE (skip sync)")
    print()

    # Prompt
    while True:
        if has_saved:
            raw = input("Enter course numbers (e.g. 1,3,5) or ENTER to keep previous: ").strip()
        else:
            raw = input("Enter course numbers (e.g. 1,3,5): ").strip()

        # ENTER with saved prefs -> reuse
        if raw == "" and has_saved:
            selected_ids = list(saved_ids)
            print(f"\n  -> Keeping previous selection ({len(selected_ids)} courses)")
            break

        # Select all
        if raw.lower() == "a":
            selected_ids = [c["id"] for c in courses_sorted]
            print(f"\n  -> Selected ALL {len(selected_ids)} courses")
            break

        # Select none
        if raw.lower() == "n":
            selected_ids = []
            print("\n  -> No courses selected. Nothing to sync.")
            break

        # Parse numbers
        try:
            nums = [int(x.strip()) for x in raw.replace(" ", ",").split(",") if x.strip()]
            invalid = [n for n in nums if n < 1 or n > len(courses_sorted)]
            if invalid:
                print(f"  Invalid numbers: {invalid}. Enter 1-{len(courses_sorted)}.")
                continue
            selected_ids = [courses_sorted[n - 1]["id"] for n in nums]
            # Show confirmation
            print()
            for n in sorted(set(nums)):
                c = courses_sorted[n - 1]
                print(f"  [*] {c['course_code']:<20s} {c['name']}")
            print(f"\n  -> Selected {len(selected_ids)} course(s)")
            break
        except ValueError:
            print("  Please enter numbers separated by commas (e.g. 1,3,5), 'a' for all, or 'n' for none.")

    # Save for next time
    prefs["selected_course_ids"] = selected_ids
    save_preferences(data_dir, prefs)

    return selected_ids
