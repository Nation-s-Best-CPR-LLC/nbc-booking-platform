"""Render the app's pages to static HTML for a shareable preview.

Uses Flask's test client against a database loaded with schema + seed + demo
data, signs in as each demo account, and writes one HTML file per page with
links rewritten between the files and the stylesheet inlined. Buttons that
need the server are switched off by PREVIEW_MODE.

    DATABASE_URL=postgresql:///nbc python scripts/export_preview.py [out_dir]

The output's index.html is a landing page listing every rendered page. It has
no <html>/<head> wrapper so it can be published as a claude.ai Artifact; the
other files are complete pages.
"""

from __future__ import annotations

import html
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import text  # noqa: E402

from app import create_app, db  # noqa: E402

# Which demo account renders each role's dashboard.
ROLE_ACCOUNTS = {
    "admin": "admin@example.test",
    "manager": "manager@example.test",
    "customer_service": "cs@example.test",
    "operations": "ops@example.test",
    "helper_recruiting": "recruiting@example.test",
    "location_approver": "approver@example.test",
    "viewer": "viewer@example.test",
    "instructor": "marcus.hale@example.test",
}


def file_name(path: str) -> str:
    if path == "/":
        return "home.html"
    if path.startswith("/admin/d/"):
        return "staff-" + path.rsplit("/", 1)[1].replace("_", "-") + ".html"
    if path in ("/admin/", "/admin/sign-in"):
        return "staff-sign-in.html"
    if path == "/portal/":
        return "instructor-portal.html"
    return path.strip("/").replace("/", "--") + ".html"


def main(out_dir: Path) -> None:
    app = create_app({
        "APP_ENV": "local",
        "DATABASE_URL": os.environ["DATABASE_URL"],
        "DEV_SIGN_IN": True,
        "PREVIEW_MODE": True,
        "PUBLIC_BASE_URL": "https://classes.nationsbestcpr.com",
    })
    css = (ROOT / "app" / "static" / "app.css").read_text()

    with app.app_context():
        conn = db.connection()
        metros = [r[0] for r in conn.execute(text(
            "SELECT slug FROM metros WHERE booking_system = 'engine' AND is_active ORDER BY name"))]
        courses = [(m, c) for m, c in conn.execute(text("""
            SELECT DISTINCT m.slug, cf.slug FROM sessions s
              JOIN metros m ON m.id = s.metro_id JOIN course_families cf ON cf.id = s.course_family_id
             WHERE m.booking_system = 'engine' AND s.is_published AND s.status = 'scheduled' AND s.starts_at > now()
             ORDER BY 1, 2"""))]
        classes = [(m, c, s) for m, c, s in conn.execute(text("""
            SELECT m.slug, cf.slug, s.slug FROM sessions s
              JOIN metros m ON m.id = s.metro_id JOIN course_families cf ON cf.id = s.course_family_id
             WHERE m.booking_system = 'engine' AND s.is_published AND s.status = 'scheduled' AND s.starts_at > now()
             ORDER BY s.starts_at"""))]
        accounts = {email: uid for email, uid in conn.execute(text(
            "SELECT email, id FROM user_accounts WHERE email = ANY(:e)"), {"e": list(ROLE_ACCOUNTS.values())})}
        role_names = dict(conn.execute(text("SELECT code, name FROM roles")).all())

    # (path, signed-in account email or None, group, label)
    pages: list[tuple[str, str | None, str, str]] = [("/", None, "Public class finder", "Choose a city")]
    pages += [(f"/{m}/", None, "Public class finder", "Choose a course") for m in metros]
    pages += [(f"/{m}/{c}/", None, "Public class finder", f"Dates and locations: {c.replace('-', ' ')}") for m, c in courses]
    pages += [(f"/{m}/{c}/{s}/", None, "Class pages", f"{c.replace('-', ' ')} · {s}") for m, c, s in classes]
    pages.append(("/admin/sign-in", None, "Staff", "Sign-in (pick a demo account)"))
    for role, email in ROLE_ACCOUNTS.items():
        if email in accounts:
            path = "/portal/" if role == "instructor" else f"/admin/d/{role}"
            group = "Instructor portal" if role == "instructor" else "Staff dashboards (one per role)"
            pages.append((path, email, group, role_names.get(role, role)))

    known = {p for p, *_ in pages}
    known.add("/admin/")
    out_dir.mkdir(parents=True, exist_ok=True)

    def rewrite(body: str) -> str:
        body = re.sub(r'<link rel="stylesheet" href="/static/app\.css">', f"<style>\n{css}\n</style>", body)

        def link(m: re.Match) -> str:
            target = m.group(1)
            if target == "/__preview_index__":
                return 'href="index.html"'
            path = target.split("#", 1)[0].split("?", 1)[0]
            return f'href="{file_name(path)}"' if path in known else 'href="#" aria-disabled="true"'

        return re.sub(r'href="(/[^"]*)"', link, body)

    for path, email, _group, _label in pages:
        client = app.test_client()
        if email:
            with client.session_transaction() as sess:
                sess["user_id"] = accounts[email]
        res = client.get(path)
        if res.status_code != 200:
            raise SystemExit(f"{path} returned {res.status_code}")
        (out_dir / file_name(path)).write_text(rewrite(res.get_data(as_text=True)))

    write_index(out_dir, pages, css)
    print(f"Wrote {len(pages) + 1} files to {out_dir}")


def write_index(out_dir: Path, pages: list, css: str) -> None:
    def git(*args: str) -> str:
        try:
            return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()
        except (OSError, subprocess.CalledProcessError):
            return "unknown"

    groups: dict[str, list[tuple[str, str]]] = {}
    for path, _email, group, label in pages:
        groups.setdefault(group, []).append((file_name(path), label))

    blurbs = {
        "Public class finder": "What customers see: city, then course, then date and location.",
        "Class pages": "One page per class, with both prices, live seats and Google's event data.",
        "Staff": "Office staff sign in with Microsoft 365 (coming in phase 4b). The preview lets you pick a demo account.",
        "Staff dashboards (one per role)": "Each role opens its own dashboard. What it shows follows the role's permissions in the database.",
        "Instructor portal": "Instructors see only their own classes, as lead or helper.",
    }
    sections = []
    for group, items in groups.items():
        links = "\n".join(
            f'<a class="panel choice" href="{html.escape(f)}"><h3>{html.escape(label[:1].upper() + label[1:])}</h3>'
            f'<span class="muted small">{html.escape(f)}</span></a>'
            for f, label in items
        )
        sections.append(f"""
<section class="stack">
  <div class="stack" style="gap:4px"><h2>{html.escape(group)}</h2><p class="muted">{html.escape(blurbs.get(group, ''))}</p></div>
  <div class="grid">{links}</div>
</section>""")

    generated = datetime.now(timezone.utc).strftime("%b %-d, %Y %H:%M UTC")
    page = f"""<title>NBC Booking Engine Preview</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@600;700&family=Public+Sans:wght@400;500;600&display=swap">
<style>
{css}
</style>
<header class="site-header"><div class="wrap">
  <span class="brand"><span class="brand-mark" aria-hidden="true"></span>
  <span><span class="brand-name">Nation's Best CPR</span> <span class="brand-sub">Booking engine preview</span></span></span>
</div></header>
<main><div class="wrap stack-lg">
  <div class="page-head">
    <span class="eyebrow">Static preview · demo data</span>
    <h1>Every page the Flask app serves today</h1>
    <p class="muted">Rendered from the real app against the database schema, with invented Richmond classes, students and staff for January 2027. Booking, sign-in and payments need the running server, so those buttons are switched off here.</p>
    <p class="small muted num">Branch {html.escape(git('rev-parse', '--abbrev-ref', 'HEAD'))} · commit {html.escape(git('rev-parse', '--short', 'HEAD'))} · generated {generated}</p>
  </div>
  {''.join(sections)}
  <section class="notice small">Regenerate after changes: <code>python scripts/export_preview.py</code> (see README).</section>
</div></main>
"""
    (out_dir / "index.html").write_text(page)


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "build" / "preview")
