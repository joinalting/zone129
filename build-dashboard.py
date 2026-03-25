#!/usr/bin/env python3
"""
Build a dashboard HTML page for the Zone 129 Ting.
Reads all effort configs and entry counts to generate a snapshot view.

Usage: python3 build-dashboard.py [--output dashboard.html]
"""

import re
import yaml
import argparse
from datetime import date
from pathlib import Path

VAULT_DIR = Path(__file__).parent
CONTACTS_DIR = VAULT_DIR.parent / "contacts"
OUTPUT_DEFAULT = VAULT_DIR / "dashboard.html"

PHASES = ["define", "propose", "discuss", "decide", "record"]
PHASE_LABELS = {"define": "Define", "propose": "Propose", "discuss": "Discuss", "decide": "Vote", "record": "Record"}

STATUS_COLORS = {
    "active": "#E5905A",
    "exploring": "#7A8A6E",
    "planned": "#6b7563",
}

STATUS_LABELS = {
    "active": "Active",
    "exploring": "Exploring",
    "planned": "Planned",
}


def parse_frontmatter(filepath):
    text = filepath.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)", text, re.DOTALL)
    if not match:
        return None, text
    try:
        meta = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return None, text
    return meta, match.group(2).strip()


def load_efforts():
    efforts = []
    for d in sorted(VAULT_DIR.iterdir()):
        if d.is_dir() and (d / "_effort.md").exists():
            meta, _ = parse_frontmatter(d / "_effort.md")
            if meta:
                # Count entries
                entry_count = len(list(d.glob("2*.md")))
                # Count decisions
                decisions = 0
                for f in d.glob("2*.md"):
                    m, _ = parse_frontmatter(f)
                    if m and m.get("type") == "decision":
                        decisions += 1
                meta["_entry_count"] = entry_count
                meta["_decision_count"] = decisions
                meta["_dir"] = d.name
                efforts.append(meta)
    return efforts


def count_contacts():
    if not CONTACTS_DIR.exists():
        return 0
    count = 0
    for f in CONTACTS_DIR.glob("*.md"):
        meta, _ = parse_frontmatter(f)
        if meta and meta.get("address"):
            count += 1
    return count


def render_effort_card(e):
    eid = e.get("effort_id", "")
    name = e.get("effort_name", "")
    desc = e.get("description", "")
    status = e.get("status", "planned")
    status_color = STATUS_COLORS.get(status, "#6b7563")
    status_label = STATUS_LABELS.get(status, status)
    topics = e.get("topics", [])
    entry_count = e.get("_entry_count", 0)
    decision_count = e.get("_decision_count", 0)
    committee = e.get("committee", [])

    # Phase summary - what's the furthest along topic?
    max_phase = 0
    for t in topics:
        phase = t.get("phase", "define")
        if phase in PHASES:
            idx = PHASES.index(phase)
            if idx > max_phase:
                max_phase = idx

    # Mini progress bar
    pct = ((max_phase + 1) / len(PHASES)) * 100 if topics else 0

    # Topics summary
    topic_pills = ""
    for t in topics:
        phase = t.get("phase", "define")
        tname = t.get("name", "")
        phase_label = PHASE_LABELS.get(phase, phase)
        pill_class = "topic-pill--vote" if phase == "decide" else ""
        topic_pills += f'<span class="topic-pill {pill_class}" title="{phase_label}">{tname}</span>'

    stats_html = f"""
      <div class="card__stats">
        <div class="card__stat"><span class="card__stat-num">{entry_count}</span> entries</div>
        <div class="card__stat"><span class="card__stat-num">{decision_count}</span> decisions</div>
        <div class="card__stat"><span class="card__stat-num">{len(committee)}</span> members</div>
        <div class="card__stat"><span class="card__stat-num">{len(topics)}</span> topics</div>
      </div>"""

    return f"""
    <a class="card" href="timeline.html" data-effort="{eid}">
      <div class="card__header">
        <h3 class="card__name">{name}</h3>
        <span class="card__status" style="color: {status_color}; border-color: {status_color}">{status_label}</span>
      </div>
      <p class="card__desc">{desc}</p>
      <div class="card__progress">
        <div class="card__progress-bg">
          <div class="card__progress-fill" style="width: {pct}%"></div>
        </div>
      </div>
      {stats_html}
      <div class="card__topics">{topic_pills}</div>
    </a>"""


def build_dashboard(efforts, member_count):
    today = date.today()
    today_str = today.strftime("%B %d, %Y")

    total_entries = sum(e.get("_entry_count", 0) for e in efforts)
    total_decisions = sum(e.get("_decision_count", 0) for e in efforts)
    active_efforts = sum(1 for e in efforts if e.get("status") == "active")

    effort_cards = "\n".join(render_effort_card(e) for e in efforts)

    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Zone 129 &mdash; Dashboard</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=DM+Serif+Display&display=swap" rel="stylesheet">
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}

    :root[data-theme="dark"] {{
      --bg: #1A2316; --bg-header: #1A2316; --bg-card: #222d1c; --bg-footer: #151d11;
      --text: #FAF6F0; --text-secondary: #a8b0a0; --text-muted: #6b7563;
      --border: rgba(122,138,110,0.25); --sage: #7A8A6E; --amber: #E5905A;
      --toggle-bg: rgba(122,138,110,0.2); --toggle-active: #7A8A6E;
    }}
    :root[data-theme="light"] {{
      --bg: #FAF6F0; --bg-header: #FAF6F0; --bg-card: #ffffff; --bg-footer: #f0ebe4;
      --text: #1A2316; --text-secondary: #4a5542; --text-muted: #7a8a6e;
      --border: rgba(46,61,38,0.15); --sage: #5a6a4e; --amber: #c47040;
      --toggle-bg: rgba(46,61,38,0.1); --toggle-active: #2E3D26;
    }}

    body {{ font-family: 'DM Sans', sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; transition: background 0.3s, color 0.3s; }}

    .header {{ background: var(--bg-header); border-bottom: 1px solid var(--border); padding: 16px 40px; display: flex; justify-content: space-between; align-items: center; }}
    .header__left {{ display: flex; flex-direction: column; }}
    .header__brand {{ display: flex; align-items: baseline; gap: 8px; }}
    .header__alting {{ font-family: 'DM Serif Display', serif; font-size: 18px; color: var(--sage); text-decoration: none; }}
    .header__alting:hover {{ opacity: 0.8; }}
    .header__sep {{ color: var(--border); font-size: 18px; font-weight: 300; }}
    .header__title {{ font-family: 'DM Serif Display', serif; font-size: 24px; text-decoration: none; color: var(--text); }}
    .header__title:hover {{ opacity: 0.8; }}
    .header__sub {{ font-size: 13px; color: var(--text-muted); }}
    .header__right {{ display: flex; gap: 12px; align-items: center; }}

    .toggle {{ display: flex; background: var(--toggle-bg); border-radius: 20px; padding: 2px; }}
    .toggle__btn {{ background: none; border: none; color: var(--text-muted); padding: 4px 10px; border-radius: 18px; font-size: 12px; font-family: inherit; font-weight: 500; cursor: pointer; transition: all 0.2s; }}
    .toggle__btn.active {{ background: var(--toggle-active); color: #FAF6F0; }}

    .main {{ max-width: 1100px; margin: 0 auto; padding: 40px; }}

    /* --- Stats bar --- */
    .stats {{ display: flex; gap: 32px; margin-bottom: 40px; padding-bottom: 32px; border-bottom: 1px solid var(--border); }}
    .stat {{ display: flex; flex-direction: column; }}
    .stat__num {{ font-family: 'DM Serif Display', serif; font-size: 36px; color: var(--text); line-height: 1; }}
    .stat__label {{ font-size: 12px; color: var(--text-muted); margin-top: 4px; text-transform: uppercase; letter-spacing: 0.08em; font-weight: 600; }}

    /* --- Section --- */
    .section-label {{ font-size: 13px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--text-secondary); font-weight: 700; margin-bottom: 20px; }}

    /* --- Effort cards --- */
    .cards {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 20px; margin-bottom: 48px; }}

    .card {{ background: var(--bg-card); border: 1px solid var(--border); border-radius: 10px; padding: 24px; text-decoration: none; color: var(--text); transition: all 0.2s; display: flex; flex-direction: column; }}
    .card:hover {{ border-color: var(--sage); transform: translateY(-2px); box-shadow: 0 4px 20px rgba(0,0,0,0.15); }}
    .card__header {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px; }}
    .card__name {{ font-family: 'DM Serif Display', serif; font-size: 20px; }}
    .card__status {{ font-size: 10px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; padding: 3px 10px; border: 1px solid; border-radius: 12px; white-space: nowrap; }}
    .card__desc {{ font-size: 13px; color: var(--text-secondary); line-height: 1.6; margin-bottom: 16px; flex: 1; }}

    .card__progress {{ margin-bottom: 16px; }}
    .card__progress-bg {{ height: 3px; background: var(--toggle-bg); border-radius: 2px; }}
    .card__progress-fill {{ height: 3px; background: var(--sage); border-radius: 2px; transition: width 0.3s; }}

    .card__stats {{ display: flex; gap: 16px; margin-bottom: 12px; flex-wrap: wrap; }}
    .card__stat {{ font-size: 12px; color: var(--text-muted); }}
    .card__stat-num {{ font-weight: 700; color: var(--text-secondary); }}

    .card__topics {{ display: flex; flex-wrap: wrap; gap: 5px; }}
    .topic-pill {{ font-size: 11px; padding: 2px 8px; border-radius: 10px; background: var(--toggle-bg); color: var(--sage); font-weight: 500; }}
    .topic-pill--vote {{ background: rgba(229,144,90,0.15); color: var(--amber); }}

    /* --- Footer --- */
    .footer {{ text-align: center; padding: 48px 40px; margin-top: 32px; font-size: 12px; color: var(--text-muted); background: var(--bg-footer); }}
    .footer a {{ color: var(--sage); text-decoration: none; }}
    .footer__brand {{ margin-bottom: 8px; }}
    .footer__alting {{ font-family: 'DM Serif Display', serif; font-size: 20px; color: var(--text-secondary); }}
    .footer__tagline {{ display: block; font-size: 11px; letter-spacing: 0.12em; text-transform: uppercase; color: var(--text-muted); margin-top: 4px; }}

    @media (max-width: 600px) {{
      .header {{ padding: 12px 16px; }}
      .main {{ padding: 20px 16px; }}
      .stats {{ gap: 20px; flex-wrap: wrap; }}
      .stat__num {{ font-size: 28px; }}
      .cards {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>

  <header class="header">
    <div class="header__left">
      <div class="header__brand">
        <a href="dashboard.html" class="header__alting">Alting</a>
        <span class="header__sep">/</span>
        <a href="dashboard.html" class="header__title">Zone 129</a>
      </div>
      <div class="header__sub">{today_str}</div>
    </div>
    <div class="header__right">
      <div class="toggle" id="theme-toggle">
        <button class="toggle__btn active" data-theme-val="dark">&#9789;</button>
        <button class="toggle__btn" data-theme-val="light">&#9788;</button>
      </div>
    </div>
  </header>

  <div class="main">

    <div class="stats">
      <div class="stat">
        <div class="stat__num">{member_count}</div>
        <div class="stat__label">People</div>
      </div>
      <div class="stat">
        <div class="stat__num">3</div>
        <div class="stat__label">Streets</div>
      </div>
      <div class="stat">
        <div class="stat__num">{len(efforts)}</div>
        <div class="stat__label">Efforts</div>
      </div>
      <div class="stat">
        <div class="stat__num">{active_efforts}</div>
        <div class="stat__label">Active</div>
      </div>
      <div class="stat">
        <div class="stat__num">{total_entries}</div>
        <div class="stat__label">Entries</div>
      </div>
      <div class="stat">
        <div class="stat__num">{total_decisions}</div>
        <div class="stat__label">Decisions</div>
      </div>
    </div>

    <div class="section-label">Efforts</div>
    <div class="cards">
      {effort_cards}
    </div>

  </div>

  <footer class="footer">
    <div class="footer__brand">
      <span class="footer__alting">Alting</span>
      <span class="footer__tagline">Govern From Within</span>
    </div>
    <div>Zone 129 &middot; <a href="https://joinalting.org">joinalting.org</a></div>
  </footer>

  <script>
    function setTheme(theme) {{
      document.documentElement.dataset.theme = theme;
      document.querySelectorAll("#theme-toggle .toggle__btn").forEach(function(btn) {{
        btn.classList.toggle("active", btn.dataset.themeVal === theme);
      }});
      localStorage.setItem("ting-theme", theme);
    }}

    document.addEventListener("DOMContentLoaded", function() {{
      setTheme(localStorage.getItem("ting-theme") || "dark");
      document.querySelectorAll("#theme-toggle .toggle__btn").forEach(function(btn) {{
        btn.addEventListener("click", function() {{ setTheme(this.dataset.themeVal); }});
      }});
      // Link cards to timeline with effort tab
      document.querySelectorAll(".card").forEach(function(card) {{
        card.addEventListener("click", function(e) {{
          e.preventDefault();
          var eid = this.dataset.effort;
          localStorage.setItem("ting-effort", eid);
          window.location.href = "timeline.html";
        }});
      }});
    }});
  </script>

</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description="Build Ting dashboard")
    parser.add_argument("--output", "-o", default=str(OUTPUT_DEFAULT))
    args = parser.parse_args()

    efforts = load_efforts()
    member_count = count_contacts()

    print(f"Found {len(efforts)} efforts, {member_count} members")
    for e in efforts:
        print(f"  {e['effort_name']}: {e['_entry_count']} entries, {e['_decision_count']} decisions")

    html = build_dashboard(efforts, member_count)
    output_path = Path(args.output)
    output_path.write_text(html, encoding="utf-8")
    print(f"Dashboard saved to {output_path}")


if __name__ == "__main__":
    main()
