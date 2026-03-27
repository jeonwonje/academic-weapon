"""Generate a beautiful HTML page to view Canvas announcements and open it in the browser."""
import json
import re
import sys
import io
import webbrowser
from html import escape
from pathlib import Path
from datetime import datetime, timezone

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.config import settings


# ── Helpers ──────────────────────────────────────────────────────────

def time_ago(posted_str: str) -> str:
    try:
        posted = datetime.fromisoformat(posted_str)
        now = datetime.now(timezone.utc)
        diff = now - posted
        seconds = int(diff.total_seconds())
        if seconds < 60:
            return "just now"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes}m ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h ago"
        days = hours // 24
        if days < 30:
            return f"{days}d ago"
        months = days // 30
        return f"{months}mo ago"
    except Exception:
        return ""


def format_date(posted_str: str) -> str:
    try:
        posted = datetime.fromisoformat(posted_str)
        return posted.strftime("%a %d %b %Y, %I:%M %p")
    except Exception:
        return posted_str or "Unknown"


def clean_message(html: str) -> str:
    """Clean Canvas message HTML (remove injected scripts, etc.)."""
    if not html:
        return "<em>No content</em>"
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
    return html


# ── Data loading ─────────────────────────────────────────────────────

def load_courses(data_dir: Path):
    f = data_dir / "courses.json"
    if not f.exists():
        return []
    with open(f, "r", encoding="utf-8") as fh:
        return json.load(fh)


def load_announcements(data_dir: Path, course_code: str):
    safe = course_code.replace("/", "-").replace("\\", "-")
    f = data_dir / safe / "announcements.json"
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

    all_anns = []
    course_color_map = {}
    color_idx = 0

    for c in sorted(courses, key=lambda c: c["course_code"]):
        code = c["course_code"]
        anns = load_announcements(data_dir, code)
        if anns:
            course_color_map[code] = COLORS[color_idx % len(COLORS)]
            color_idx += 1
            for a in anns:
                a["_course_code"] = code
                a["_course_name"] = c["name"]
                all_anns.append(a)

    all_anns.sort(key=lambda a: a.get("posted_at", ""), reverse=True)

    if not all_anns:
        return "<html><body><h1>No announcements found.</h1></body></html>"

    course_codes = sorted(course_color_map.keys())

    # Filter buttons
    filter_buttons = []
    for code in course_codes:
        bg, fg = course_color_map[code]
        count = sum(1 for a in all_anns if a["_course_code"] == code)
        filter_buttons.append(
            f'<button class="filter-btn active" data-course="{escape(code)}" '
            f'style="--badge-bg:{bg}; --badge-fg:{fg}">'
            f'{escape(code)} <span class="count">{count}</span></button>'
        )

    # Announcement cards
    cards = []
    for ann in all_anns:
        code = ann["_course_code"]
        bg, fg = course_color_map.get(code, ("#666", "#fff"))
        title = escape(ann.get("title", "Untitled"))
        author = escape(ann.get("author", {}).get("display_name", "Unknown"))
        posted = ann.get("posted_at", "")
        date_str = escape(format_date(posted))
        ago = escape(time_ago(posted))
        message = clean_message(ann.get("message", ""))

        cards.append(f"""
        <article class="card" data-course="{escape(code)}">
            <div class="card-header">
                <span class="badge" style="background:{bg}; color:{fg}">{escape(code)}</span>
                <span class="ago">{ago}</span>
            </div>
            <h2 class="card-title">{title}</h2>
            <div class="card-meta">
                <span class="author">{author}</span>
                <span class="sep">&middot;</span>
                <span class="date">{date_str}</span>
            </div>
            <details class="card-details">
                <summary>Show message</summary>
                <div class="card-body">{message}</div>
            </details>
        </article>
        """)

    generated = datetime.now().strftime("%d %b %Y, %I:%M %p")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Canvas Announcements</title>
<style>
:root {{
    --bg: #0d1117;
    --surface: #161b22;
    --surface-hover: #1c2333;
    --text: #e6edf3;
    --text-muted: #7d8590;
    --border: #30363d;
    --accent: #58a6ff;
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
    max-width: 780px;
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
    min-width: 160px;
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
}}
.badge {{
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.4px;
    text-transform: uppercase;
}}
.ago {{
    color: var(--text-muted);
    font-size: 0.78rem;
}}
.card-title {{
    font-size: 1.08rem;
    font-weight: 600;
    color: #fff;
    margin-bottom: 4px;
}}
.card-meta {{
    font-size: 0.78rem;
    color: var(--text-muted);
    display: flex;
    gap: 8px;
    align-items: center;
    margin-bottom: 8px;
}}
.card-meta .sep {{ opacity: 0.4; }}

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
    <h1>Canvas Announcements</h1>
    <p class="subtitle">{len(all_anns)} announcements across {len(course_codes)} courses &middot; {generated}</p>
</header>

<div class="container">
    <div class="toolbar">
        <div class="filters">
            {''.join(filter_buttons)}
            <input type="text" id="search" placeholder="Search announcements...">
        </div>
    </div>
    <div id="cards">
        {''.join(cards)}
    </div>
    <div id="empty" class="empty-state" style="display:none">
        No announcements match your filters.
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
    output = data_dir / "announcements.html"

    print("Generating announcements page...")
    html = generate_html(data_dir)

    with open(output, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Saved to {output}")
    print("Opening in browser...")
    webbrowser.open(str(output.resolve()))


if __name__ == "__main__":
    main()
