"""Prompt templates for LLM-powered analysis."""

from __future__ import annotations

from datetime import datetime, timezone

SYSTEM_PROMPT = """You are Academic Weapon — an AI academic assistant for an NUS student.
You have access to course data synced from NUS Canvas including:
- Assignment details, deadlines, and descriptions
- Course announcements
- Calendar events
- Lecture slides, notes, and other uploaded files
- Module/week structures

When answering:
- Be concise and structured. Use bullet points and bold for key info.
- Always mention specific dates and deadlines in SGT (UTC+8).
- Prioritise actionable information (what's due, what to study, etc.).
- If you don't have enough info, say so clearly.
- Format output for Telegram (use Markdown: *bold*, _italic_, `code`).
- Use ⚠️ for urgent deadlines (within 3 days) and 📌 for important items."""


DAILY_DIGEST_PROMPT = """Generate a daily academic digest for today ({today}).

Here is the student's current data across all courses:

{context}

Create a structured digest with these sections:

1. **⚡ Urgent (Due within 3 days)** — assignments/tasks due very soon
2. **📅 This Week** — what's due this week
3. **📢 Recent Announcements** — key announcements from the last 3 days
4. **🔮 Coming Up** — important dates in the next 2 weeks
5. **💡 Quick Tip** — one actionable study tip based on the workload

If a section has nothing, skip it. Keep it brief and scannable.
Format for Telegram Markdown."""


DEADLINE_TRACKER_PROMPT = """List ALL upcoming deadlines from the following course data.

{context}

Output a clean sorted list:
- Group by timeframe: OVERDUE, THIS WEEK, NEXT WEEK, LATER
- Format each: **Course** — Assignment Name — 📅 Due: date (SGT)
- Add ⚠️ for items due within 48 hours
- Skip past deadlines unless they are within the last 2 days (mark as OVERDUE)

Today is {today}. Format for Telegram Markdown."""


COURSE_SUMMARY_PROMPT = """Summarise the following course based on its Canvas data.

Course: {course_code}

{context}

Provide:
1. **📚 Overview** — What the course covers (topics, themes)
2. **📋 Assessment** — Grading breakdown if available
3. **📅 Key Dates** — Important deadlines and milestones
4. **📂 Materials** — Summary of available files/resources
5. **📊 Workload** — Your assessment of current workload intensity

Format for Telegram Markdown. Be concise."""


QUERY_PROMPT = """Answer the following question about the student's courses at NUS.

Question: {question}

Here is the relevant course data:

{context}

Answer concisely and accurately. If you reference specific files or dates, be precise.
If the data doesn't contain enough info to fully answer, say what you can and note the gaps.
Today is {today}. Format for Telegram Markdown."""


def get_today() -> str:
    """Get today's date formatted nicely in SGT."""
    from datetime import timedelta
    sgt = timezone(timedelta(hours=8))
    now = datetime.now(sgt)
    return now.strftime("%A, %d %B %Y (%H:%M SGT)")
