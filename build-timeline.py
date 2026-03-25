#!/usr/bin/env python3
"""
Build a multi-effort timeline HTML page from Ting vault markdown entries.
Each effort lives in a subdirectory with an _effort.md config.
Zone-wide entries in zone-wide/ appear on all efforts.

Usage: python3 build-timeline.py [--output timeline.html] [--private]
"""

import re
import yaml
import argparse
from datetime import date, datetime
from pathlib import Path

VAULT_DIR = Path(__file__).parent
CONTACTS_DIR = VAULT_DIR.parent / "contacts"
OUTPUT_DEFAULT = VAULT_DIR / "timeline.html"

COLORS = {
    "bg": "#1A2316",
    "cream": "#FAF6F0",
    "sage": "#7A8A6E",
    "amber": "#E5905A",
    "text_secondary": "#a8b0a0",
    "text_muted": "#6b7563",
    "border": "rgba(122, 138, 110, 0.25)",
}

TYPE_LABELS = {
    "event": {"icon": "&#9679;", "color": COLORS["sage"], "label": "Event"},
    "discussion": {"icon": "&#9671;", "color": COLORS["amber"], "label": "Discussion"},
    "decision": {"icon": "&#9733;", "color": "#c4956a", "label": "Decision"},
    "document": {"icon": "&#9744;", "color": COLORS["text_muted"], "label": "Document"},
}


def parse_frontmatter(filepath):
    """Parse YAML frontmatter from a markdown file."""
    text = filepath.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)", text, re.DOTALL)
    if not match:
        return None, text
    try:
        meta = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return None, text
    return meta, match.group(2).strip()


def parse_entry(filepath):
    """Parse a timeline entry markdown file."""
    meta, body = parse_frontmatter(filepath)
    if not meta:
        return None

    title_match = re.match(r"^#\s+(.+)", body)
    title = title_match.group(1) if title_match else filepath.stem
    body_after_title = re.sub(r"^#\s+.+\n*", "", body).strip()

    entry_date = meta.get("date")
    if isinstance(entry_date, str):
        entry_date = datetime.strptime(entry_date, "%Y-%m-%d").date()
    elif isinstance(entry_date, datetime):
        entry_date = entry_date.date()

    return {
        "date": entry_date,
        "type": meta.get("type", "event"),
        "tags": meta.get("tags", []),
        "status": meta.get("status", ""),
        "participants": meta.get("participants", []),
        "comments": meta.get("comments", []),
        "votable": meta.get("votable", False),
        "featured": meta.get("featured", False),
        "title": title,
        "body": body_after_title,
        "filename": filepath.name,
        "is_private": meta.get("type") == "discussion",
    }


def load_entries(directory):
    """Load all entry .md files from a directory."""
    entries = []
    for f in directory.glob("2*.md"):
        entry = parse_entry(f)
        if entry and entry["date"]:
            entries.append(entry)
    entries.sort(key=lambda e: e["date"])
    return entries


def load_effort(directory):
    """Load effort config from _effort.md."""
    effort_file = directory / "_effort.md"
    if not effort_file.exists():
        return None
    meta, _ = parse_frontmatter(effort_file)
    return meta


def load_config():
    """Load Ting config from _config.md."""
    config_path = VAULT_DIR / "_config.md"
    if not config_path.exists():
        return {"ting_name": "Ting"}
    meta, _ = parse_frontmatter(config_path)
    return meta or {"ting_name": "Ting"}


def load_members():
    """Load members from contacts directory."""
    if not CONTACTS_DIR.exists():
        return []
    members = []
    for f in sorted(CONTACTS_DIR.glob("*.md")):
        meta, body = parse_frontmatter(f)
        if not meta:
            continue
        address = meta.get("address", "")
        if not address:
            continue
        # Get name from first heading
        h_match = re.search(r"^#\s+(.+)", body, re.MULTILINE)
        name = h_match.group(1) if h_match else f.stem.replace("-", " ").title()
        # Extract street name for grouping
        street = ""
        if "Morada" in address:
            street = "Morada Pl"
        elif "Mar Vista" in address:
            street = "Mar Vista Ave"
        elif "New York" in address:
            street = "New York Dr"
        members.append({"name": name, "address": address, "street": street})
    return members


def md_to_html(text):
    """Minimal markdown to HTML."""
    lines = text.split("\n")
    html_lines = []
    in_list = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append("")
            continue
        # Images: ![alt](src)
        stripped = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r'<img src="\2" alt="\1" class="entry__img" loading="lazy">', stripped)
        # Bold link = CTA button: **[text](url)**
        stripped = re.sub(r"\*\*\[([^\]]+)\]\(([^)]+)\)\*\*", r'<a href="\2" class="entry__cta" target="_blank">\1</a>', stripped)
        stripped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", stripped)
        stripped = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2" class="entry__link" target="_blank">\1</a>', stripped)
        stripped = re.sub(r"\[\[(.+?)\]\]", r"<em>\1</em>", stripped)
        stripped = re.sub(r"`(.+?)`", r"<code>\1</code>", stripped)
        list_match = re.match(r"^[-*]\s+(.+)", stripped)
        num_match = re.match(r"^\d+\.\s+(.+)", stripped)
        if list_match or num_match:
            content = list_match.group(1) if list_match else num_match.group(1)
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            html_lines.append(f"  <li>{content}</li>")
        else:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<p>{stripped}</p>")
    if in_list:
        html_lines.append("</ul>")
    # Wrap consecutive image paragraphs in gallery
    result = "\n".join(html_lines)
    result = re.sub(
        r'(<p><img [^>]+></p>)\n+(<p><img [^>]+></p>)',
        r'<div class="entry__gallery">\1\n\2</div>',
        result
    )
    # Unwrap <p> tags around images inside galleries
    result = result.replace("<p><img ", "<img ").replace("></p>", ">")
    return result


def render_entry(e, public=True):
    """Render a single entry to HTML."""
    t = TYPE_LABELS.get(e["type"], TYPE_LABELS["event"])
    tags_html = "".join(f'<span class="tag">{tag}</span>' for tag in e.get("tags", []))
    status_html = ""
    if e["status"]:
        status_class = f"status--{e['status']}"
        status_html = f'<span class="status {status_class}" data-status="{e["status"]}">{e["status"]}</span>'
    body_html = md_to_html(e["body"])
    votable = e.get("votable", False)
    featured = e.get("featured", False)
    featured_class = " entry--featured" if featured else ""

    # Render comments
    comments_html = ""
    comments = e.get("comments", [])
    if comments:
        comment_items = ""
        for c in comments:
            c_date = c.get("date", "")
            c_author = c.get("author", "")
            c_text = c.get("text", "")
            comment_items += f"""
            <div class="comment">
              <div class="comment__meta"><strong>{c_author}</strong> &middot; {c_date}</div>
              <div class="comment__text">{c_text}</div>
            </div>"""
        comments_html = f'<div class="comments"><div class="comments__label" data-i18n="label_comments">Comments</div>{comment_items}</div>'

    # Vote button
    vote_html = ""
    if votable:
        vote_html = '<button class="entry__vote-btn" data-i18n="btn_vote">&#9745; Vote on this</button>'

    # Action bar
    actions_html = f"""
        <div class="entry__actions">
          <button class="entry__action" title="Add a comment" data-i18n-title="action_comment">
            <span class="entry__action-icon">&#9998;</span>
            <span data-i18n="action_comment">Comment</span>
          </button>
          <button class="entry__action" title="Raise a concern" data-i18n-title="action_concern">
            <span class="entry__action-icon">&#9888;</span>
            <span data-i18n="action_concern">Concern</span>
          </button>
          {vote_html}
        </div>"""

    return f"""
    <div class="entry{featured_class}" data-type="{e['type']}" data-tags="{','.join(e.get('tags', []))}">
      <div class="entry__marker" style="color: {t['color']}">{t['icon']}</div>
      <div class="entry__content">
        <div class="entry__meta">
          <time class="entry__date">{e['date'].strftime('%b %d, %Y')}</time>
          <span class="entry__type" style="color: {t['color']}">{t['label']}</span>
          {status_html}
        </div>
        <h3 class="entry__title">{e['title']}</h3>
        <div class="entry__body">{body_html}</div>
        {comments_html}
        {actions_html}
        <div class="entry__tags">{tags_html}</div>
      </div>
    </div>"""


def render_committee(committee):
    """Render committee cards."""
    if not committee:
        return ""
    rows = ""
    for m in committee:
        name = m.get("name", "")
        role = m.get("role", "")
        address = m.get("address", "")
        email = m.get("email", "")
        phone = m.get("phone", "")
        parts = []
        if email:
            parts.append(f'<a href="mailto:{email}">{email}</a>')
        if phone:
            parts.append(phone)
        contact = " &middot; ".join(parts)
        rows += f"""
        <div class="committee__member">
          <div class="committee__name">{name}</div>
          <div class="committee__role">{role}</div>
          <div class="committee__address">{address}</div>
          <div class="committee__contact">{contact}</div>
        </div>"""
    return rows


def render_effort_timeline(effort_config, entries, public=True):
    """Render a single effort's timeline section."""
    today = date.today()
    today_str = today.strftime("%B %d, %Y")
    eid = effort_config.get("effort_id", "unknown")
    ename = effort_config.get("effort_name", "Effort")
    ename_es = effort_config.get("effort_name_es", ename)
    desc = effort_config.get("description", "")
    desc_es = effort_config.get("description_es", desc)
    status = effort_config.get("status", "")

    if public:
        entries = [e for e in entries if not e["is_private"]]

    past = [e for e in entries if e["date"] < today]
    present = [e for e in entries if e["date"] == today]
    future = [e for e in entries if e["date"] > today]

    past_html = "\n".join(render_entry(e, public) for e in past)
    present_html = "\n".join(render_entry(e, public) for e in present)
    future_html = "\n".join(render_entry(e, public) for e in future)

    committee = effort_config.get("committee", [])
    committee_html = render_committee(committee)
    purpose = effort_config.get("purpose", "")

    committee_section = ""
    if committee_html:
        committee_section = f"""
    <div class="committee">
      <div class="section-label" style="padding-left: 0;" data-i18n="label_committee">Planning Committee</div>
      <div class="committee__grid">
        {committee_html}
      </div>
    </div>"""

    # Purpose section
    map_html = effort_config.get("map_html", "")
    purpose_section = ""
    if purpose:
        purpose_section = f"""<div class="effort__purpose-section">
      <p class="effort__purpose">{purpose}</p>
      {map_html}
    </div>"""

    # Governance phase tracker
    topics = effort_config.get("topics", [])
    phase_tracker = ""
    if topics:
        PHASES = ["define", "propose", "discuss", "decide", "record"]
        PHASE_LABELS = {
            "define": "Define", "propose": "Propose",
            "discuss": "Discuss", "decide": "Vote", "record": "Record"
        }
        phase_header = ""
        for p in PHASES:
            label = PHASE_LABELS[p]
            cls = "phase__label phase__label--vote" if p == "decide" else "phase__label"
            phase_header += f'<div class="{cls}">{label}</div>'
        topic_rows = ""
        for t in topics:
            tname = t.get("name", "")
            tphase = t.get("phase", "define")
            tsummary = t.get("summary", "")
            phase_idx = PHASES.index(tphase) if tphase in PHASES else 0
            pct = (phase_idx / (len(PHASES) - 1)) * 100
            # Place the marker at the center of each column
            marker_pct = (phase_idx / len(PHASES)) * 100 + (100 / len(PHASES) / 2)
            topic_rows += f"""
            <div class="phase__row">
              <div class="phase__topic">
                <div class="phase__topic-name">{tname}</div>
                <div class="phase__topic-summary">{tsummary}</div>
              </div>
              <div class="phase__track">
                <div class="phase__line-bg"></div>
                <div class="phase__line-fill" style="width: {marker_pct}%"></div>
                <div class="phase__marker" style="left: {marker_pct}%"></div>
              </div>
            </div>"""

        phase_tracker = f"""
    <div class="phase-tracker">
      <div class="section-label" style="padding-left: 0;" data-i18n="label_process">Governance Process</div>
      <div class="phase__header">
        <div class="phase__topic-spacer"></div>
        <div class="phase__labels">{phase_header}</div>
      </div>
      {topic_rows}
    </div>"""

    status_badge = ""
    if status:
        status_badge = f'<span class="effort-status" data-i18n="effort_status_{status}">{status}</span>'

    return f"""
  <div class="effort" id="effort-{eid}" data-effort="{eid}" style="display: none;">
    <div class="effort__header">
      <div>
        <h2 class="effort__name">{ename}</h2>
        <p class="effort__desc">{desc}</p>
      </div>
      {status_badge}
    </div>

    {purpose_section}
    {phase_tracker}
    {committee_section}

    <div class="section-label" data-i18n="label_past">Past</div>
    <div class="effort__past">
      {past_html if past_html.strip() else '<div class="empty" data-i18n="empty_past">No past entries.</div>'}
    </div>

    <div class="today-anchor" id="today-{eid}"></div>
    <div class="today-marker" data-i18n="today_marker">Today &mdash; {today_str}</div>

    <div class="effort__present">
      {present_html if present_html.strip() else ""}
    </div>

    <div class="section-label" data-i18n="label_future">Future Zone</div>
    <div class="future-zone">
      {future_html if future_html.strip() else '<div class="empty" data-i18n="empty_future">Nothing scheduled yet.</div>'}
    </div>
  </div>"""


def build_html(config, efforts_data, members=None, public=True):
    """Generate the full multi-effort timeline HTML."""
    today = date.today()
    today_str = today.strftime("%B %d, %Y")
    ting_name = config.get("ting_name", "Ting")

    # Build effort tabs and content
    effort_tabs = ""
    effort_content = ""
    first = True
    for effort_config, entries in efforts_data:
        eid = effort_config.get("effort_id", "unknown")
        ename = effort_config.get("effort_name", "Effort")
        ename_es = effort_config.get("effort_name_es", ename)
        active_class = " active" if first else ""
        effort_tabs += f'<button class="effort-tab{active_class}" data-effort="{eid}" data-en="{ename}" data-es="{ename_es}">{ename}</button>\n      '
        effort_content += render_effort_timeline(effort_config, entries, public)
        first = False

    # Build About tab with members
    about_content = ""
    if members:
        streets = {"Morada Pl": [], "Mar Vista Ave": [], "New York Dr": []}
        for m in members:
            s = m.get("street", "")
            if s in streets:
                streets[s].append(m)
        street_sections = ""
        for street_name, street_members in streets.items():
            if not street_members:
                continue
            member_pills = "".join(
                f'<span class="member__pill" title="{m["address"]}">{m["name"]}</span>'
                for m in street_members
            )
            street_sections += f"""
            <div class="members__street">
              <div class="members__street-name">{street_name} <span class="members__count">({len(street_members)})</span></div>
              <div class="members__list">{member_pills}</div>
            </div>"""

        about_content = f"""
  <div class="effort" id="effort-about" data-effort="about" style="display: none;">

    <div class="about">
      <h2 class="effort__name">About Zone 129</h2>

      <div class="about__section">
        <h3 class="about__heading">What is Zone 129?</h3>
        <p class="about__text">Zone 129 is a neighborhood block in Altadena, California, covering three streets: Morada Place, Mar Vista Avenue, and New York Drive. We are {len(members)} people. Some of us have lived here for decades. Some moved in last year. After the Eaton Fire, we realized we needed a way to come together, not just to recover, but to build something lasting.</p>
      </div>

      <div class="about__section">
        <h3 class="about__heading">What is a Ting?</h3>
        <p class="about__text">A <strong>Ting</strong> is a group of people who trust each other enough to decide together. The word comes from Old Norse, where a ting was a public assembly where free people gathered to govern themselves. Zone 129 is our Ting. It is how we organize, deliberate, and make decisions as a neighborhood.</p>
        <p class="about__text">Every Ting follows the same process: <strong>Define</strong> the question. <strong>Propose</strong> options. <strong>Discuss</strong> openly. <strong>Vote</strong> (one person, one vote). <strong>Record</strong> the decision. The record is the product: proof that we decided together.</p>
      </div>

      <div class="about__section">
        <h3 class="about__heading">Our Values</h3>
        <div class="about__values">
          <div class="about__value">
            <div class="about__value-name">One Person, One Vote</div>
            <p class="about__value-desc">Every neighbor has an equal voice. Consensus is tied to personhood, not property, seniority, or influence.</p>
          </div>
          <div class="about__value">
            <div class="about__value-name">Transparency</div>
            <p class="about__value-desc">Every decision, every discussion, every concern is recorded. The process is visible to everyone in the Ting.</p>
          </div>
          <div class="about__value">
            <div class="about__value-name">Belonging</div>
            <p class="about__value-desc">This is not a committee. It is a neighborhood. Everyone on these three streets is part of Zone 129, whether they participate actively or not.</p>
          </div>
          <div class="about__value">
            <div class="about__value-name">Bottom Up</div>
            <p class="about__value-desc">We don't wait for institutions to organize us. We organize ourselves and bring our decisions to the institutions that serve us.</p>
          </div>
        </div>
      </div>

      <div class="about__section">
        <h3 class="about__heading">Our Vision</h3>
        <p class="about__text">Zone 129 is a neighborhood that governs itself. Where neighbors know each other's names, share what they have, and make decisions together about the things that affect their daily lives. We start small: a block party, a garden, a shared conversation about what this street should feel like. Each effort is practice. Each decision record is proof that we can do this.</p>
      </div>

      <div class="about__section">
        <h3 class="about__heading">Block Captain</h3>
        <div class="about__captain">
          <div class="about__captain-name">Petra Wennberg</div>
          <div class="about__captain-address">1184 Morada Pl, Altadena, CA 91001</div>
          <div class="about__captain-role">Altagether Block Captain &mdash; Zone 129</div>
          <div class="about__captain-contact"><a href="mailto:petra_wennberg@icloud.com">petra_wennberg@icloud.com</a></div>
        </div>
      </div>

      <div class="members-section">
        <h3 class="about__heading" data-i18n="label_neighbors">Our Neighbors</h3>
        <p class="members__summary">{len(members)} people across 3 streets</p>
        {street_sections}
      </div>

    </div>
  </div>"""

    # Add About tab at the beginning
    effort_tabs = f'<button class="effort-tab" data-effort="about" data-en="About" data-es="Acerca de">About</button>\n      ' + effort_tabs

    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{ting_name} &mdash; Timeline</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&family=DM+Serif+Display&display=swap" rel="stylesheet">
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}

    :root[data-theme="dark"] {{
      --bg: #1A2316; --bg-header: #1A2316; --bg-footer: #151d11;
      --text: #FAF6F0; --text-secondary: #a8b0a0; --text-muted: #6b7563;
      --border: rgba(122,138,110,0.25); --sage: #7A8A6E; --amber: #E5905A; --gold: #c4956a;
      --tag-bg: rgba(122,138,110,0.15);
      --status-complete-bg: rgba(122,138,110,0.2); --status-decided-bg: rgba(196,149,106,0.2);
      --status-active-bg: rgba(229,144,90,0.2); --status-proposed-bg: rgba(250,246,240,0.1);
      --toggle-bg: rgba(122,138,110,0.2); --toggle-active: #7A8A6E;
    }}
    :root[data-theme="light"] {{
      --bg: #FAF6F0; --bg-header: #FAF6F0; --bg-footer: #f0ebe4;
      --text: #1A2316; --text-secondary: #4a5542; --text-muted: #7a8a6e;
      --border: rgba(46,61,38,0.15); --sage: #5a6a4e; --amber: #c47040; --gold: #a07550;
      --tag-bg: rgba(46,61,38,0.08);
      --status-complete-bg: rgba(90,106,78,0.12); --status-decided-bg: rgba(160,117,80,0.12);
      --status-active-bg: rgba(196,112,64,0.12); --status-proposed-bg: rgba(26,35,22,0.06);
      --toggle-bg: rgba(46,61,38,0.1); --toggle-active: #2E3D26;
    }}

    body {{ font-family: 'DM Sans', sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; transition: background 0.3s, color 0.3s; }}

    .header {{ position: sticky; top: 0; z-index: 100; background: var(--bg-header); border-bottom: 1px solid var(--border); padding: 16px 40px; display: flex; justify-content: space-between; align-items: center; gap: 16px; }}
    .header__left {{ display: flex; flex-direction: column; }}
    .header__brand {{ display: flex; align-items: baseline; gap: 8px; }}
    .header__alting {{ font-family: 'DM Serif Display', serif; font-size: 18px; color: var(--sage); text-decoration: none; }}
    .header__alting:hover {{ opacity: 0.8; }}
    .header__separator {{ color: var(--border); font-size: 18px; font-weight: 300; }}
    .header__title {{ font-family: 'DM Serif Display', serif; font-size: 24px; color: var(--text); text-decoration: none; }}
    .header__title:hover {{ opacity: 0.8; }}
    .header__today {{ font-size: 14px; color: var(--text-secondary); }}
    .header__right {{ display: flex; gap: 12px; align-items: center; }}

    .toggle {{ display: flex; align-items: center; background: var(--toggle-bg); border-radius: 20px; padding: 2px; }}
    .toggle__btn {{ background: none; border: none; color: var(--text-muted); padding: 4px 10px; border-radius: 18px; font-size: 12px; font-family: inherit; font-weight: 500; cursor: pointer; transition: all 0.2s; }}
    .toggle__btn.active {{ background: var(--toggle-active); color: #FAF6F0; }}

    /* --- Effort tabs --- */
    .effort-tabs {{ display: flex; gap: 0; padding: 0 40px; border-bottom: 1px solid var(--border); background: var(--bg-header); }}
    .effort-tab {{ background: none; border: none; border-bottom: 2px solid transparent; color: var(--text-muted); padding: 12px 20px; font-size: 14px; font-family: inherit; font-weight: 500; cursor: pointer; transition: all 0.2s; }}
    .effort-tab:hover {{ color: var(--text-secondary); }}
    .effort-tab.active {{ color: var(--text); border-bottom-color: var(--amber); }}

    /* --- Filter row --- */
    .filter-row {{ display: flex; gap: 8px; padding: 12px 40px; align-items: center; justify-content: flex-end; }}
    .filter-btn {{ background: none; border: 1px solid var(--border); color: var(--text-secondary); padding: 4px 12px; border-radius: 20px; font-size: 12px; cursor: pointer; font-family: inherit; transition: all 0.2s; }}
    .filter-btn:hover, .filter-btn.active {{ background: var(--sage); color: #FAF6F0; border-color: var(--sage); }}

    /* --- Timeline --- */
    .timeline {{ max-width: 800px; margin: 0 auto; padding: 0 40px; }}

    /* --- Effort header --- */
    .effort__header {{ display: flex; justify-content: space-between; align-items: flex-start; padding: 32px 0 8px; }}
    .effort__name {{ font-family: 'DM Serif Display', serif; font-size: 28px; }}
    .effort__desc {{ font-size: 14px; color: var(--text-secondary); margin-top: 4px; max-width: 600px; }}
    .effort-status {{ font-size: 11px; padding: 4px 12px; border-radius: 12px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; background: var(--status-active-bg); color: var(--amber); }}

    .section-label {{ font-size: 13px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--text-secondary); font-weight: 700; padding: 32px 0 16px 24px; }}
    .today-marker {{ background: var(--toggle-bg); color: var(--text-secondary); font-weight: 600; font-size: 12px; letter-spacing: 0.08em; text-transform: uppercase; padding: 6px 16px; border-radius: 20px; display: inline-block; margin: 24px 0 20px 24px; border: 1px solid var(--border); }}
    .future-zone {{ border-left: 2px dashed var(--border); margin-left: 10px; padding-left: 38px; }}

    .entry {{ display: flex; gap: 16px; padding: 20px 0; border-bottom: 1px solid var(--border); }}
    .entry__marker {{ font-size: 18px; width: 24px; text-align: center; flex-shrink: 0; padding-top: 2px; }}
    .entry__content {{ flex: 1; min-width: 0; }}
    .entry__meta {{ display: flex; align-items: center; gap: 12px; margin-bottom: 6px; }}
    .entry__date {{ font-size: 13px; color: var(--text-muted); }}
    .entry__type {{ font-size: 11px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; }}
    .status {{ font-size: 10px; padding: 2px 8px; border-radius: 10px; font-weight: 500; letter-spacing: 0.04em; text-transform: uppercase; }}
    .status--complete {{ background: var(--status-complete-bg); color: var(--sage); }}
    .status--decided {{ background: var(--status-decided-bg); color: var(--gold); }}
    .status--active {{ background: var(--status-active-bg); color: var(--amber); }}
    .status--proposed {{ background: var(--status-proposed-bg); color: var(--text-secondary); }}
    .entry__title {{ font-family: 'DM Serif Display', serif; font-size: 20px; margin-bottom: 8px; color: var(--text); }}
    .entry__body {{ font-size: 14px; color: var(--text-secondary); line-height: 1.7; }}
    .entry__body p {{ margin-bottom: 8px; }}
    .entry__body ul {{ margin: 8px 0; padding-left: 20px; }}
    .entry__body li {{ margin-bottom: 4px; }}
    .entry__body strong {{ color: var(--text); }}
    /* --- Featured entry --- */
    .entry--featured {{
      background: linear-gradient(135deg, rgba(229,144,90,0.12) 0%, rgba(122,138,110,0.08) 100%);
      border: 1px solid rgba(229,144,90,0.25);
      border-radius: 12px;
      padding: 28px 24px;
      margin: 8px 0;
      border-bottom: 1px solid rgba(229,144,90,0.25);
      position: relative;
      overflow: hidden;
    }}
    .entry--featured::before {{
      content: '';
      display: none;
    }}
    .entry--featured .entry__title {{
      font-size: 28px;
      color: #E5905A;
    }}
    .entry--featured .entry__body {{
      font-size: 16px;
      line-height: 1.8;
      color: var(--text-secondary);
    }}
    .entry--featured .entry__body p {{ margin-bottom: 12px; }}
    .entry--featured .entry__meta {{ display: none; }}

    .entry__img {{ max-width: 100%; border-radius: 8px; margin: 8px 0; }}
    .entry__gallery {{ display: flex; gap: 12px; margin: 12px 0; flex-wrap: wrap; }}
    .entry__gallery .entry__img {{ width: calc(50% - 6px); height: 200px; object-fit: cover; }}
    .entry__link {{ color: var(--amber); text-decoration: none; font-weight: 600; }}
    .entry__link:hover {{ text-decoration: underline; }}
    .entry__cta {{ display: inline-block; background: #E5905A; color: #1A2316; font-weight: 700; font-size: 12px; padding: 5px 12px; border-radius: 6px; text-decoration: none; margin-top: 12px; transition: background 0.2s; }}
    .entry__cta:hover {{ background: #d07a48; text-decoration: none; }}
    .entry__tags {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 12px; }}
    .tag {{ font-size: 11px; padding: 2px 10px; border-radius: 12px; background: var(--tag-bg); color: var(--sage); font-weight: 500; }}
    .empty {{ padding: 20px 0 20px 48px; font-size: 14px; color: var(--text-muted); font-style: italic; }}

    /* --- Purpose --- */
    .effort__purpose-section {{ display: flex; gap: 32px; align-items: flex-start; margin: 8px 0 24px; }}
    .effort__purpose {{ font-size: 15px; color: var(--text-secondary); line-height: 1.7; flex: 1; }}
    .effort__map {{ flex-shrink: 0; width: 200px; background: var(--toggle-bg); border-radius: 8px; padding: 12px; }}
    .effort__map svg {{ width: 100%; height: auto; }}
    .effort__map-label {{ font-size: 10px; color: var(--text-muted); text-align: center; margin-top: 6px; }}

    /* --- Phase tracker --- */
    .phase-tracker {{ margin-bottom: 24px; padding-bottom: 24px; border-bottom: 1px solid var(--border); }}
    .phase__header {{ display: flex; align-items: center; margin-bottom: 4px; }}
    .phase__topic-spacer {{ width: 240px; flex-shrink: 0; }}
    .phase__labels {{ display: flex; flex: 1; }}
    .phase__label {{ flex: 1; text-align: center; font-size: 11px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; color: var(--text-muted); padding: 8px 0; }}
    .phase__row {{ display: flex; align-items: center; padding: 10px 0; border-top: 1px solid var(--border); }}
    .phase__topic {{ width: 240px; flex-shrink: 0; padding-right: 16px; }}
    .phase__topic-name {{ font-size: 14px; font-weight: 600; color: var(--text); }}
    .phase__topic-summary {{ font-size: 12px; color: var(--text-muted); margin-top: 2px; line-height: 1.4; }}
    .phase__track {{ flex: 1; position: relative; height: 20px; display: flex; align-items: center; }}
    .phase__line-bg {{ position: absolute; left: 0; right: 0; height: 3px; background: var(--toggle-bg); border-radius: 2px; }}
    .phase__line-fill {{ position: absolute; left: 0; height: 3px; background: var(--sage); border-radius: 2px; transition: width 0.3s; }}
    .phase__marker {{ position: absolute; width: 12px; height: 12px; border-radius: 50%; background: var(--amber); transform: translateX(-50%); box-shadow: 0 0 8px rgba(229,144,90,0.35); transition: left 0.3s; }}

    /* --- Comments --- */
    .comments {{ margin-top: 12px; padding-top: 12px; border-top: 1px dashed var(--border); }}
    .comments__label {{ font-size: 11px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; color: var(--text-muted); margin-bottom: 8px; }}
    .comment {{ padding: 8px 0; }}
    .comment + .comment {{ border-top: 1px solid var(--border); }}
    .comment__meta {{ font-size: 12px; color: var(--text-muted); }}
    .comment__meta strong {{ color: var(--text-secondary); }}
    .comment__text {{ font-size: 13px; color: var(--text-secondary); margin-top: 4px; line-height: 1.5; }}

    /* --- Entry actions --- */
    .entry__actions {{ display: flex; gap: 8px; margin-top: 14px; align-items: center; flex-wrap: wrap; }}
    .entry__action {{ display: flex; align-items: center; gap: 5px; background: none; border: 1px solid var(--border); color: var(--text-muted); padding: 5px 12px; border-radius: 6px; font-size: 12px; font-family: inherit; cursor: pointer; transition: all 0.2s; }}
    .entry__action:hover {{ border-color: var(--sage); color: var(--text-secondary); background: var(--toggle-bg); }}
    .entry__action-icon {{ font-size: 14px; }}
    .entry__vote-btn {{ display: flex; align-items: center; gap: 5px; background: #E5905A; color: #1A2316; border: 1px solid #E5905A; padding: 5px 12px; border-radius: 6px; font-size: 12px; font-weight: 700; font-family: inherit; cursor: pointer; transition: all 0.2s; }}
    .entry__vote-btn:hover {{ background: #d07a48; border-color: #d07a48; }}

    /* --- Phase vote label --- */
    .phase__label--vote {{ color: #E5905A; font-weight: 700; }}

    .committee {{ margin-top: 8px; padding-bottom: 24px; border-bottom: 1px solid var(--border); }}
    .committee__grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 20px; margin-top: 16px; }}
    .committee__member {{ padding: 16px; background: var(--toggle-bg); border-radius: 8px; }}
    .committee__name {{ font-weight: 600; font-size: 14px; color: var(--text); }}
    .committee__role {{ font-size: 12px; color: var(--sage); margin-top: 2px; }}
    .committee__address {{ font-size: 12px; color: var(--text-muted); margin-top: 6px; }}
    .committee__contact {{ font-size: 12px; color: var(--text-secondary); margin-top: 4px; }}
    .committee__contact a {{ color: var(--sage); text-decoration: none; }}
    .committee__contact a:hover {{ text-decoration: underline; }}

    .footer {{ text-align: center; padding: 48px 40px; margin-top: 64px; font-size: 12px; color: var(--text-muted); background: var(--bg-footer); }}
    .footer a {{ color: var(--sage); text-decoration: none; }}
    .footer__brand {{ margin-bottom: 8px; }}
    .footer__alting {{ font-family: 'DM Serif Display', serif; font-size: 20px; color: var(--text-secondary); }}
    .footer__tagline {{ display: block; font-size: 11px; letter-spacing: 0.12em; text-transform: uppercase; color: var(--text-muted); margin-top: 4px; }}
    .footer__meta {{ font-size: 12px; color: var(--text-muted); }}

    /* --- About section --- */
    .about {{ padding: 48px 0 16px; }}
    .about__section {{ margin-bottom: 32px; }}
    .about__heading {{ font-family: 'DM Serif Display', serif; font-size: 20px; color: var(--text); margin-bottom: 10px; }}
    .about__text {{ font-size: 15px; color: var(--text-secondary); line-height: 1.7; margin-bottom: 10px; max-width: 700px; }}
    .about__text strong {{ color: var(--text); }}
    .about__values {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; margin-top: 12px; }}
    .about__value {{ padding: 20px; background: var(--toggle-bg); border-radius: 8px; }}
    .about__value-name {{ font-size: 15px; font-weight: 700; color: var(--text); margin-bottom: 6px; }}
    .about__value-desc {{ font-size: 13px; color: var(--text-secondary); line-height: 1.6; }}

    /* --- Block Captain --- */
    .about__captain {{ padding: 20px; background: var(--toggle-bg); border-radius: 8px; border-left: 3px solid var(--amber); max-width: 400px; }}
    .about__captain-name {{ font-family: 'DM Serif Display', serif; font-size: 18px; color: var(--text); }}
    .about__captain-address {{ font-size: 13px; color: var(--text-muted); margin-top: 4px; }}
    .about__captain-role {{ font-size: 13px; color: var(--sage); margin-top: 4px; font-weight: 500; }}
    .about__captain-contact {{ font-size: 13px; margin-top: 8px; }}
    .about__captain-contact a {{ color: var(--amber); text-decoration: none; }}
    .about__captain-contact a:hover {{ text-decoration: underline; }}

    /* --- Members section --- */
    .members-section {{ padding: 32px 0; }}
    .members__summary {{ font-size: 14px; color: var(--text-secondary); margin-bottom: 20px; }}
    .members__street {{ margin-bottom: 16px; }}
    .members__street-name {{ font-size: 13px; font-weight: 600; color: var(--text-secondary); margin-bottom: 8px; }}
    .members__count {{ font-weight: 400; color: var(--text-muted); }}
    .members__list {{ display: flex; flex-wrap: wrap; gap: 6px; }}
    .member__pill {{ font-size: 12px; padding: 3px 10px; border-radius: 14px; background: var(--toggle-bg); color: var(--text-secondary); cursor: default; transition: all 0.2s; }}
    .member__pill:hover {{ background: var(--sage); color: #FAF6F0; }}

    @media (max-width: 600px) {{
      .header {{ padding: 12px 16px; flex-wrap: wrap; }}
      .effort-tabs {{ padding: 0 16px; overflow-x: auto; }}
      .filter-row {{ padding: 12px 16px; flex-wrap: wrap; }}
      .about__values {{ grid-template-columns: 1fr; }}
      .phase__topic-spacer {{ width: 140px; }}
      .phase__topic {{ width: 140px; }}
      .phase__topic-summary {{ display: none; }}
      .phase__label {{ font-size: 9px; }}
      .timeline {{ padding: 0 20px; }}
      .section-label, .today-marker {{ margin-left: 40px; }}
      .future-zone {{ padding-left: 30px; }}
    }}
  </style>
</head>
<body>

  <header class="header">
    <div class="header__left">
      <div class="header__brand">
        <a href="dashboard.html" class="header__alting">Alting</a>
        <span class="header__separator">/</span>
        <a href="dashboard.html" class="header__title">{ting_name}</a>
      </div>
      <div class="header__today" data-i18n="today_date">{today_str}</div>
    </div>
    <div class="header__right">
      <div class="toggle" id="lang-toggle">
        <button class="toggle__btn active" data-lang="en">EN</button>
        <button class="toggle__btn" data-lang="es">ES</button>
      </div>
      <div class="toggle" id="theme-toggle">
        <button class="toggle__btn active" data-theme-val="dark">&#9789;</button>
        <button class="toggle__btn" data-theme-val="light">&#9788;</button>
      </div>
    </div>
  </header>

  <nav class="effort-tabs">
    {effort_tabs}
  </nav>

  <div class="filter-row">
    <button class="filter-btn active" data-filter="all" data-i18n="filter_all">All</button>
    <button class="filter-btn" data-filter="event" data-i18n="filter_events">Events</button>
    <button class="filter-btn" data-filter="decision" data-i18n="filter_decisions">Decisions</button>
    <button class="filter-btn" data-filter="discussion" data-i18n="filter_discussions">Discussions</button>
    <button class="filter-btn" data-filter="document" data-i18n="filter_documents">Documents</button>
  </div>

  <div class="timeline">
    {about_content}
    {effort_content}
  </div>

  <footer class="footer">
    <div class="footer__brand">
      <span class="footer__alting">Alting</span>
      <span class="footer__tagline">Govern From Within</span>
    </div>
    <div class="footer__meta">
      {ting_name} &middot; <a href="https://joinalting.org">joinalting.org</a>
    </div>
  </footer>

  <script>
    var STRINGS = {{
      en: {{
        filter_all: "All", filter_events: "Events", filter_decisions: "Decisions",
        filter_discussions: "Discussions", filter_documents: "Documents",
        label_past: "Past", label_future: "Future Zone", label_committee: "Planning Committee",
        today_marker: "Today &mdash; {today_str}", today_date: "{today_str}",
        empty_past: "No past entries.", empty_future: "Nothing scheduled yet.",
        footer_powered: "Powered by",
        type_event: "Event", type_decision: "Decision", type_discussion: "Discussion", type_document: "Document",
        status_complete: "complete", status_decided: "decided", status_active: "active",
        status_proposed: "proposed", status_exploring: "exploring",
        effort_status_active: "active", effort_status_exploring: "exploring",
        label_process: "Governance Process", label_comments: "Comments",
        action_comment: "Comment", action_concern: "Concern", btn_vote: "&#9745; Vote on this",
        label_members: "Zone 129 Members",
        label_neighbors: "Our Neighbors"
      }},
      es: {{
        filter_all: "Todo", filter_events: "Eventos", filter_decisions: "Decisiones",
        filter_discussions: "Discusiones", filter_documents: "Documentos",
        label_past: "Pasado", label_future: "Zona Futura", label_committee: "Comit&eacute; de Planificaci&oacute;n",
        today_marker: "Hoy &mdash; {today_str}", today_date: "{today_str}",
        empty_past: "No hay entradas pasadas.", empty_future: "Nada programado a&uacute;n.",
        footer_powered: "Impulsado por",
        type_event: "Evento", type_decision: "Decisi&oacute;n", type_discussion: "Discusi&oacute;n", type_document: "Documento",
        status_complete: "completo", status_decided: "decidido", status_active: "activo",
        status_proposed: "propuesto", status_exploring: "explorando",
        effort_status_active: "activo", effort_status_exploring: "explorando",
        label_process: "Proceso de Gobernanza", label_comments: "Comentarios",
        action_comment: "Comentar", action_concern: "Preocupaci&oacute;n", btn_vote: "&#9745; Votar",
        label_members: "Miembros de Zona 129",
        label_neighbors: "Nuestros Vecinos"
      }}
    }};

    var currentLang = "en";
    var currentEffort = null;

    function setLang(lang) {{
      currentLang = lang;
      document.documentElement.lang = lang;
      document.querySelectorAll("[data-i18n]").forEach(function(el) {{
        var key = el.dataset.i18n;
        if (STRINGS[lang][key]) el.innerHTML = STRINGS[lang][key];
      }});
      document.querySelectorAll(".entry__type").forEach(function(el) {{
        var type = el.closest(".entry").dataset.type;
        if (STRINGS[lang]["type_" + type]) el.innerHTML = STRINGS[lang]["type_" + type];
      }});
      document.querySelectorAll(".status").forEach(function(el) {{
        var s = el.dataset.status;
        if (STRINGS[lang]["status_" + s]) el.textContent = STRINGS[lang]["status_" + s];
      }});
      document.querySelectorAll(".effort-status").forEach(function(el) {{
        var key = el.dataset.i18n;
        if (STRINGS[lang][key]) el.textContent = STRINGS[lang][key];
      }});
      // Update effort tab labels
      document.querySelectorAll(".effort-tab").forEach(function(tab) {{
        tab.textContent = tab.dataset[lang] || tab.dataset.en;
      }});
      document.querySelectorAll("#lang-toggle .toggle__btn").forEach(function(btn) {{
        btn.classList.toggle("active", btn.dataset.lang === lang);
      }});
      localStorage.setItem("ting-lang", lang);
    }}

    function setTheme(theme) {{
      document.documentElement.dataset.theme = theme;
      document.querySelectorAll("#theme-toggle .toggle__btn").forEach(function(btn) {{
        btn.classList.toggle("active", btn.dataset.themeVal === theme);
      }});
      localStorage.setItem("ting-theme", theme);
    }}

    function setEffort(effortId) {{
      currentEffort = effortId;
      document.querySelectorAll(".effort-tab").forEach(function(tab) {{
        tab.classList.toggle("active", tab.dataset.effort === effortId);
      }});
      document.querySelectorAll(".effort").forEach(function(el) {{
        el.style.display = el.dataset.effort === effortId ? "block" : "none";
      }});
      // Hide filters on About tab
      document.querySelector(".filter-row").style.display = effortId === "about" ? "none" : "flex";
      // Scroll to today
      var anchor = document.getElementById("today-" + effortId);
      if (anchor) {{
        setTimeout(function() {{
          anchor.scrollIntoView({{ behavior: "smooth", block: "center" }});
        }}, 200);
      }}
      localStorage.setItem("ting-effort", effortId);
    }}

    function applyFilter(filter) {{
      document.querySelectorAll(".filter-btn").forEach(function(b) {{ b.classList.remove("active"); }});
      document.querySelector('.filter-btn[data-filter="' + filter + '"]').classList.add("active");
      document.querySelectorAll(".entry").forEach(function(entry) {{
        entry.style.display = (filter === "all" || entry.dataset.type === filter) ? "flex" : "none";
      }});
    }}

    document.addEventListener("DOMContentLoaded", function() {{
      var savedTheme = localStorage.getItem("ting-theme") || "dark";
      var savedLang = localStorage.getItem("ting-lang") || "en";
      setTheme(savedTheme);
      setLang(savedLang);

      // Set initial effort
      var savedEffort = localStorage.getItem("ting-effort");
      var firstTab = document.querySelector(".effort-tab");
      setEffort(savedEffort || (firstTab ? firstTab.dataset.effort : ""));

      // Effort tabs
      document.querySelectorAll(".effort-tab").forEach(function(tab) {{
        tab.addEventListener("click", function() {{ setEffort(this.dataset.effort); }});
      }});

      // Filter buttons
      document.querySelectorAll(".filter-btn").forEach(function(btn) {{
        btn.addEventListener("click", function() {{ applyFilter(this.dataset.filter); }});
      }});

      // Theme toggle
      document.querySelectorAll("#theme-toggle .toggle__btn").forEach(function(btn) {{
        btn.addEventListener("click", function() {{ setTheme(this.dataset.themeVal); }});
      }});

      // Language toggle
      document.querySelectorAll("#lang-toggle .toggle__btn").forEach(function(btn) {{
        btn.addEventListener("click", function() {{ setLang(this.dataset.lang); }});
      }});
    }});
  </script>

</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description="Build Ting timeline")
    parser.add_argument("--output", "-o", default=str(OUTPUT_DEFAULT))
    parser.add_argument("--private", action="store_true")
    args = parser.parse_args()

    config = load_config()

    # Load zone-wide entries (appear in all efforts)
    zone_wide_dir = VAULT_DIR / "zone-wide"
    zone_entries = load_entries(zone_wide_dir) if zone_wide_dir.exists() else []

    # Discover efforts
    efforts_data = []
    for d in sorted(VAULT_DIR.iterdir()):
        if d.is_dir() and (d / "_effort.md").exists():
            effort_config = load_effort(d)
            if effort_config:
                entries = load_entries(d)
                entries.sort(key=lambda e: e["date"])
                efforts_data.append((effort_config, entries))
                print(f"  {effort_config['effort_name']}: {len(entries)} entries")

    print(f"Found {len(efforts_data)} efforts")

    members = load_members()
    print(f"Loaded {len(members)} members")

    html = build_html(config, efforts_data, members=members, public=not args.private)
    output_path = Path(args.output)
    output_path.write_text(html, encoding="utf-8")
    print(f"Timeline saved to {output_path}")


if __name__ == "__main__":
    main()
