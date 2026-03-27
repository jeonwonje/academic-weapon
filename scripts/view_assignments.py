"""Generate a beautiful HTML page to view Canvas assignments and open it in the browser."""
import io
import json
import re
import sys
import webbrowser
from datetime import datetime, timezone
from html import escape
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.config import settings


# ── Helpers ──────────────────────────────────────────────────────────

def parse_dt(dt_str: str):
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str)
    except Exception:
        return None


def format_date(dt_str: str) -> str:
    dt = parse_dt(dt_str)
    if not dt:
        return "No due date"
    return dt.strftime("%a %d %b %Y, %I:%M %p")


def due_in(dt_str: str) -> str:
    dt = parse_dt(dt_str)
    if not dt:
        return "No due date"

    now = datetime.now(timezone.utc)
    diff = dt - now
    seconds = int(diff.total_seconds())

    if abs(seconds) < 60:
        return "due now"

    past = seconds < 0
    seconds = abs(seconds)

    minutes = seconds // 60
    if minutes < 60:
        text = f"{minutes}m"
    else:
        hours = minutes // 60
        if hours < 24:
            text = f"{hours}h"
        else:
            days = hours // 24
            if days < 30:
                text = f"{days}d"
            else:
                months = days // 30
                text = f"{months}mo"

    return f"{text} ago" if past else f"in {text}"


def clean_html(html: str) -> str:
    """Clean Canvas HTML description (remove injected scripts, etc.)."""
    if not html:
        return "<em>No description</em>"
    return re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)


# ── Data loading ─────────────────────────────────────────────────────

def load_courses(data_dir: Path):
    f = data_dir / "courses.json"
    if not f.exists():
        return []
    with open(f, "r", encoding="utf-8") as fh:
        return json.load(fh)


def load_assignments(data_dir: Path, course_code: str):
    safe = course_code.replace("/", "-").replace("\\", "-")
    f = data_dir / safe / "assignments.json"
    if not f.exists():
        return []
    with open(f, "r", encoding="utf-8") as fh:
        return json.load(fh)


# ── Color palette for course badges ─────────────────────────────────

COLORS = [
    ("#e74c3c", "#fff"),
    ("#3498db", "#fff"),
    ("#2ecc71", "#fff"),
    ("#9b59b6", "#fff"),
    ("#e67e22", "#fff"),
    ("#1abc9c", "#fff"),
    ("#e84393", "#fff"),
    ("#0984e3", "#fff"),
]


# ── HTML generation ─────────────────────────────────────────────────

def generate_html(data_dir: Path) -> str:
    courses = load_courses(data_dir)
    if not courses:
        return "<html><body><h1>No courses found. Run a sync first.</h1></body></html>"

    all_items = []
    course_color_map = {}
    color_idx = 0

    for course in sorted(courses, key=lambda c: c["course_code"]):
        code = course["course_code"]
        items = load_assignments(data_dir, code)
        if items:
            course_color_map[code] = COLORS[color_idx % len(COLORS)]
            color_idx += 1
            for item in items:
                item["_course_code"] = code
                item["_course_name"] = course["name"]
                all_items.append(item)

    if not all_items:
        return "<html><body><h1>No assignments found.</h1></body></html>"

    def sort_key(item):
        due = parse_dt(item.get("due_at"))
        if due is None:
            return (1, 0)
        return (0, -due.timestamp())

    all_items.sort(key=sort_key)
    course_codes = sorted(course_color_map.keys())

    # Filter buttons
    filter_buttons = []
    for code in course_codes:
        bg, fg = course_color_map[code]
        count = sum(1 for item in all_items if item["_course_code"] == code)
        filter_buttons.append(
            f'<button class="filter-btn active" data-course="{escape(code)}" '
            f'style="--badge-bg:{bg}; --badge-fg:{fg}">'
            f'{escape(code)} <span class="count">{count}</span></button>'
        )

    # Assignment cards
    cards = []
    now = datetime.now(timezone.utc)
    for item in all_items:
        code = item["_course_code"]
        bg, fg = course_color_map.get(code, ("#666", "#fff"))

        title = escape(item.get("name", "Untitled"))
        due_at = item.get("due_at")
        due_text = escape(format_date(due_at))
        due_relative = escape(due_in(due_at))
        description = clean_html(item.get("description") or "")

        points = item.get("points_possible")
        points_text = "Ungraded" if points is None else f"{points:g} pts"

        submission_types = item.get("submission_types") or []
        sub_text = ", ".join(submission_types) if submission_types else "Unknown"
        sub_text = escape(sub_text.replace("_", " "))

        submitted = bool(item.get("has_submitted_submissions", False))
        published = bool(item.get("published", False))

        due_dt = parse_dt(due_at)
        is_overdue = bool(due_dt and due_dt < now)
        due_class = "overdue" if is_overdue else "upcoming"

        cards.append(f"""
        <article class="card" data-course="{escape(code)}">
            <div class="card-header">
                <span class="badge" style="background:{bg}; color:{fg}">{escape(code)}</span>
                <span class="due-chip {due_class}">{due_relative}</span>
            </div>
            <h2 class="card-title">{title}</h2>
            <div class="card-meta">
                <span class="label">Due:</span>
                <span class="date">{due_text}</span>
                <span class="sep">&middot;</span>
                <span>{escape(points_text)}</span>
            </div>
            <div class="pill-row">
                <span class="pill {('ok' if submitted else 'todo')}">{'Submitted' if submitted else 'Not submitted'}</span>
                <span class="pill {('ok' if published else 'todo')}">{'Published' if published else 'Unpublished'}</span>
                <span class="pill">{sub_text}</span>
            </div>
            <details class="card-details">
                <summary>Show details</summary>
                <div class="card-body">{description}</div>
            </details>
        </article>
        """)

    generated = datetime.now().strftime("%d %b %Y, %I:%M %p")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Canvas Assignments</title>
<style>
:root {{
    --bg: #0d1117;
    --surface: #161b22;
    --surface-hover: #1c2333;
    --text: #e6edf3;
    --text-muted: #7d8590;
    --border: #30363d;
    --accent: #58a6ff;
    --danger: #f85149;
    --ok: #2ea043;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
}}

/* ── Header ── */
header {{
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    padding: 32px 20px 24px;
    text-align: center;
}}
header h1 {{
    font-size: 1.6rem;
    font-weight: 700;
    letter-spacing: -0.3px;
}}
header .subtitle {{
    color: var(--text-muted);
    font-size: 0.82rem;
    margin-top: 4px;
}}

/* ── Container ── */
.container {{
    max-width: 900px;
    margin: 0 auto;
    padding: 0 16px 40px;
}}

/* ── Sticky toolbar ── */
.toolbar {{
    position: sticky;
    top: 0;
    z-index: 100;
    background: var(--bg);
    padding: 16px 0 12px;
    border-bottom: 1px solid var(--border);
    margin-bottom: 16px;
}}
.filters {{
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    align-items: center;
}}
.filter-btn {{
    border: 2px solid var(--badge-bg, #555);
    background: var(--badge-bg);
    color: var(--badge-fg, #fff);
    padding: 5px 13px;
    border-radius: 20px;
    cursor: pointer;
    font-size: 0.78rem;
    font-weight: 600;
    transition: all 0.2s;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    user-select: none;
}}
.filter-btn .count {{
    background: rgba(255,255,255,0.2);
    border-radius: 10px;
    padding: 0 6px;
    font-size: 0.7rem;
}}
.filter-btn:not(.active) {{
    background: transparent;
    color: var(--text-muted);
    opacity: 0.5;
}}
.filter-btn:not(.active) .count {{
    background: rgba(255,255,255,0.08);
}}
.filter-btn:hover {{
    opacity: 1;
    transform: translateY(-1px);
}}
#search {{
    flex: 1;
    min-width: 180px;
    padding: 7px 14px;
    border-radius: 20px;
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--text);
    font-size: 0.82rem;
    outline: none;
    transition: border-color 0.2s;
}}
#search:focus {{
    border-color: var(--accent);
}}

/* ── Cards ── */
.card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 20px 22px;
    margin-bottom: 12px;
    transition: border-color 0.15s, transform 0.15s;
}}
.card:hover {{
    border-color: var(--accent);
    transform: translateY(-1px);
}}
.card.hidden {{ display: none; }}

.card-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
    gap: 8px;
}}
.badge {{
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.4px;
    text-transform: uppercase;
}}
.due-chip {{
    font-size: 0.75rem;
    border-radius: 12px;
    padding: 2px 8px;
    border: 1px solid var(--border);
    color: var(--text-muted);
}}
.due-chip.overdue {{
    color: var(--danger);
    border-color: rgba(248, 81, 73, 0.4);
}}
.due-chip.upcoming {{
    color: var(--ok);
    border-color: rgba(46, 160, 67, 0.4);
}}

.card-title {{
    font-size: 1.05rem;
    font-weight: 600;
    color: #fff;
    margin-bottom: 4px;
}}
.card-meta {{
    font-size: 0.8rem;
    color: var(--text-muted);
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
    margin-bottom: 8px;
}}
.card-meta .label {{
    color: #fff;
    font-weight: 500;
}}
.card-meta .sep {{ opacity: 0.4; }}

.pill-row {{
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-bottom: 6px;
}}
.pill {{
    border: 1px solid var(--border);
    color: var(--text-muted);
    font-size: 0.72rem;
    border-radius: 12px;
    padding: 2px 8px;
}}
.pill.ok {{
    color: #8bffa8;
    border-color: rgba(46, 160, 67, 0.4);
}}
.pill.todo {{
    color: #ffb4b0;
    border-color: rgba(248, 81, 73, 0.35);
}}

/* Collapsible body */
.card-details summary {{
    cursor: pointer;
    color: var(--accent);
    font-size: 0.82rem;
    font-weight: 500;
    padding: 4px 0;
    user-select: none;
    list-style: none;
}}
.card-details summary::before {{
    content: '\\25B6  ';
    font-size: 0.65rem;
    transition: transform 0.2s;
    display: inline-block;
}}
.card-details[open] summary::before {{
    transform: rotate(90deg);
}}
.card-details summary::-webkit-details-marker {{ display: none; }}

.card-body {{
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px solid var(--border);
    font-size: 0.88rem;
    line-height: 1.75;
    color: var(--text);
}}
.card-body img {{
    max-width: 100%;
    border-radius: 8px;
    margin: 8px 0;
}}
.card-body a {{
    color: var(--accent);
    text-decoration: none;
}}
.card-body a:hover {{ text-decoration: underline; }}
.card-body p {{ margin-bottom: 8px; }}

/* ── Empty state ── */
.empty-state {{
    text-align: center;
    padding: 60px 20px;
    color: var(--text-muted);
    font-size: 0.95rem;
}}

/* ── Footer ── */
footer {{
    text-align: center;
    padding: 24px;
    color: var(--text-muted);
    font-size: 0.72rem;
    border-top: 1px solid var(--border);
}}
</style>
</head>
<body>

<header>
    <h1>Canvas Assignments</h1>
    <p class="subtitle">{len(all_items)} assignments across {len(course_codes)} courses &middot; {generated}</p>
</header>

<div class="container">
    <div class="toolbar">
        <div class="filters">
            {''.join(filter_buttons)}
            <input type="text" id="search" placeholder="Search assignments...">
        </div>
    </div>
    <div id="cards">
        {''.join(cards)}
    </div>
    <div id="empty" class="empty-state" style="display:none">
        No assignments match your filters.
    </div>
</div>

<footer>Canvas Academic Weapon</footer>

<script>
const buttons = document.querySelectorAll('.filter-btn');
const cards = document.querySelectorAll('.card');
const searchBox = document.getElementById('search');
const empty = document.getElementById('empty');
const activeCourses = new Set({json.dumps(course_codes)});

buttons.forEach(btn => {{
    btn.addEventListener('click', () => {{
        const c = btn.dataset.course;
        btn.classList.toggle('active');
        activeCourses.has(c) ? activeCourses.delete(c) : activeCourses.add(c);
        applyFilters();
    }});
}});
searchBox.addEventListener('input', applyFilters);

function applyFilters() {{
    const q = searchBox.value.toLowerCase();
    let visible = 0;
    cards.forEach(card => {{
        const show = activeCourses.has(card.dataset.course)
                     && (!q || card.textContent.toLowerCase().includes(q));
        card.classList.toggle('hidden', !show);
        if (show) visible++;
    }});
    empty.style.display = visible ? 'none' : 'block';
}}
</script>
</body>
</html>"""


def main():
    data_dir = settings.data_dir
    output = data_dir / "assignments.html"

    print("Generating assignments page...")
    html = generate_html(data_dir)

    with open(output, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Saved to {output}")
    print("Opening in browser...")
    webbrowser.open(str(output.resolve()))


if __name__ == "__main__":
    main()
