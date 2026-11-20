"""HTML for each page. Every function returns a complete page as a string."""

import hashlib
import math
from html import escape
from pathlib import Path
from urllib.parse import quote

from .chart import rating_chart
from contests.store import contest_id

from .institutions import institution_key
from .theme import codeforces_class, institution_name, institution_search_text, tier_class

TITLE = "Biscuit Rating"
def _biscuit() -> str:
    """A round chocolate biscuit: scalloped edge, raised rim, docking holes, and a highlight."""
    scallops = "".join(
        f'<circle cx="{32 + 25 * math.cos(2 * math.pi * i / 16):.2f}" cy="{32 + 25 * math.sin(2 * math.pi * i / 16):.2f}" r="5.6"/>'
        for i in range(16)
    )
    holes = "".join(
        f'<circle cx="{x}" cy="{y}" r="1.7"/>'
        for x, y in [(32, 32), (32, 23.5), (32, 40.5), (23.5, 32), (40.5, 32), (26, 26), (38, 26), (26, 38), (38, 38)]
    )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
        # The scallops' outlines show only on the outside, giving the edge a lighter rim.
        f'<g fill="#3f2416" stroke="#8a5636" stroke-width="1.4">{scallops}</g>'
        '<circle cx="32" cy="32" r="25" fill="#3f2416"/>'
        '<circle cx="32" cy="32" r="21.5" fill="#5a3420"/>'
        '<circle cx="32" cy="32" r="17" fill="none" stroke="#7b4a2e" stroke-width="1.8"/>'
        f'<g fill="#2e190f">{holes}</g>'
        '<path d="M17.5 24.5a17 17 0 0 1 11-9.5" fill="none" stroke="#fff" stroke-opacity=".28" '
        'stroke-width="2.4" stroke-linecap="round"/>'
        "</svg>"
    )


LOGO = _biscuit()
FAVICON = "data:image/svg+xml," + quote(LOGO)
# Changes whenever the stylesheet or script does, so browsers never keep a stale copy.
ASSET_VERSION = hashlib.sha256(
    b"".join(path.read_bytes() for path in sorted(Path(__file__).with_name("static").iterdir()))
).hexdigest()[:10]
FONTS = "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap"


def _icon(paths: str, cls: str = "icon") -> str:
    return f'<svg class="{cls}" viewBox="0 0 24 24" aria-hidden="true">{paths}</svg>'


SUN = _icon('<circle cx="12" cy="12" r="4.5"/><path d="M12 2v2.5M12 19.5V22M4.2 4.2l1.8 1.8M18 18l1.8 1.8M2 12h2.5M19.5 12H22M4.2 19.8 6 18M18 6l1.8-1.8"/>', "sun")
MOON = _icon('<path d="M20.5 14.5A8.5 8.5 0 0 1 9.5 3.5a8.5 8.5 0 1 0 11 11z"/>', "moon")
EXTERNAL = _icon('<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>')
ICON_BISCUIT = f'<span class="info-icon" aria-hidden="true">{LOGO}</span>'
ICON_TROPHY = _icon('<path d="M8 4h8v5a4 4 0 0 1-8 0zM8 6H5a3 3 0 0 0 3 4M16 6h3a3 3 0 0 1-3 4M12 13v4M9 20h6M10 17h4"/>', "info-icon trophy-icon")
ICON_STAR = _icon('<path d="m12 3 2.7 5.6 6.1.8-4.5 4.2 1.1 6.1L12 16.8l-5.4 2.9 1.1-6.1-4.5-4.2 6.1-.8z"/>', "info-icon star-icon")
ICON_CALENDAR = _icon('<rect x="3.5" y="5" width="17" height="15" rx="2"/><path d="M3.5 10h17M8 3v4M16 3v4"/>', "info-icon calendar-icon")
ICON_CF = _icon('<rect x="3" y="11" width="4" height="9" rx="1"/><rect x="10" y="4" width="4" height="16" rx="1"/><rect x="17" y="8" width="4" height="12" rx="1"/>', "info-icon cf-icon")


def layout(title: str, root: str, body: str, active: str = "") -> str:
    def tab(name: str, href: str, label: str) -> str:
        current = ' aria-current="page"' if active == name else ""
        return f'<a href="{root}{href}"{current}>{label}</a>'

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<meta name="description" content="Contestant and institution ratings from onsite programming contests in Bangladesh.">
<link rel="icon" href="{FAVICON}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{FONTS}">
<link rel="stylesheet" href="{root}assets/style.css?v={ASSET_VERSION}">
<script>
(function () {{
  var theme = null;
  try {{ theme = localStorage.getItem("theme"); }} catch (e) {{}}
  if (!theme) theme = matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  document.documentElement.dataset.theme = theme;
}})();
</script>
</head>
<body>
<header class="topbar">
  <div class="topbar-inner">
    <a class="brand" href="{root}index.html"><span class="logo" aria-hidden="true">{LOGO}</span><span class="brand-name">{TITLE}</span></a>
    <nav class="tabs">{tab("rankings", "index.html", "Rankings")}{tab("form", "form.html", "Get listed")}{tab("about", "about.html", "About")}</nav>
    <button class="theme-toggle" type="button" aria-label="Switch between light and dark mode">{SUN}{MOON}</button>
  </div>
</header>
<main>
{body}
</main>
<footer class="footer">
  <p>Ratings come from official onsite contest standings since 2024. <a href="{root}about.html">About</a></p>
</footer>
<div class="tooltip" role="tooltip" hidden></div>
<script src="{root}assets/app.js?v={ASSET_VERSION}" defer></script>
</body>
</html>
"""


def panel(title: str, body: str, cls: str = "") -> str:
    """A boxed section with a title strip, after Codeforces' sidebar boxes."""
    return f"""<section class="panel {cls}">
  <h2 class="panel-title"><span class="arrow" aria-hidden="true">→</span> {title}</h2>
  <div class="panel-body">{body}</div>
</section>"""


# Institutions with a page of their own, and (institution, contest id) pairs with a
# contest page; set by the builder. Other institutions link to the filtered rankings.
INSTITUTION_PAGES: set[str] = set()
INSTITUTION_CONTEST_PAGES: set[tuple[str, str]] = set()


def contest_link(contest: str, institution: str, root: str) -> str:
    """The contest's name, linking to the institution's results in it when that page exists."""
    key, contest_key = institution_key(institution), contest_id(contest)
    if (key, contest_key) not in INSTITUTION_CONTEST_PAGES:
        return f"<strong>{escape(contest)}</strong>"
    return f'<a class="contest-link" href="{root}i/{key}/{contest_key}.html"><strong>{escape(contest)}</strong></a>'


def institution_link(institution: str, root: str) -> str:
    """The institution's name, linking to its page, or to the rankings filtered to it."""
    key = institution_key(institution)
    href = f"{root}i/{key}.html" if key in INSTITUTION_PAGES else f"{root}index.html?institution={quote(institution, safe='')}"
    return f'<a class="institution-link" href="{href}">{escape(institution_name(institution))}</a>'


def display_name(person: dict) -> str:
    profile = person.get("profile") or {}
    name = " ".join(part for part in (profile.get("firstName"), profile.get("lastName")) if part)
    return name or person["handle"]


def avatar(person: dict, size: str) -> str:
    """Initials, covered by the Codeforces photo when it loads; a failed photo removes itself."""
    profile = person.get("profile") or {}
    photo = profile.get("titlePhoto") or ""
    # userpic.codeforces.org refuses other sites; codeforces.com serves the same file.
    if photo.startswith("https://userpic.codeforces.org/"):
        photo = "https://codeforces.com/" + photo.removeprefix("https://")
    initials = "".join(word[0] for word in display_name(person).split()[:2]).upper()
    image = (
        f'<img src="{escape(photo)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">'
        if photo and "no-title" not in photo else ""
    )
    return f'<span class="avatar {size}" aria-hidden="true">{escape(initials)}{image}</span>'


def team_label(name: str, members: list[dict], root: str) -> str:
    """A team name that shows its members, linked to their profiles, on hover or focus."""
    items = "".join(
        f'<a class="member" href="{root}u/{escape(m["key"])}.html"><span class="handle-text {tier_class(m["rating"])}">{escape(m["handle"])}</span>'
        f'{" <span class=muted>" + escape(m["name"]) + "</span>" if m["name"] != m["handle"] else ""}</a>'
        for m in members
    )
    return (
        f'<span class="team-label" tabindex="0">{escape(name)}'
        f'<span class="team-members" hidden><strong>{escape(name)}</strong>{items}</span></span>'
    )


def ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def standing(position: int, total: int) -> str:
    if total >= 20:
        return f"Top {max(1, math.ceil(100 * position / total))}%"
    return f"#{position} of {total}"


def best_finish(history: list[dict]) -> dict | None:
    """The contest where the person's team placed highest; a larger field breaks ties."""
    ranked = [h for h in history if h["rank"] is not None]
    return min(ranked, key=lambda h: (h["rank"], -h["teams"]), default=None)


def rankings_page(people: list[dict], stats: dict, legend: str) -> str:
    institutions = sorted({p["institution"] for p in people})
    rows = []
    for person in people:
        name = display_name(person)
        tier = tier_class(person["rating"])
        profile_url = f'u/{escape(person["key"])}.html'
        handle = f'<a href="{profile_url}" class="handle-text {tier}">{escape(person["handle"])}</a>'
        institution = institution_link(person["institution"], "")
        # The rating colour goes on the handle, as on Codeforces; without a public
        # name, the handle stands in for it.
        if name != person["handle"]:
            title = f'<a href="{profile_url}" class="person-name">{escape(name)}</a>'
            handle_line = f'<span class="sub">{handle} · {institution}</span>'
        else:
            title = f'<span class="person-name">{handle}</span>'
            handle_line = f'<span class="sub">{institution}</span>'
        search = " ".join([name, person["handle"], institution_search_text(person["institution"])]).lower()
        best = best_finish(person["history"])
        finish = ordinal(best["rank"]) if best else '<span class="muted">—</span>'
        rows.append(f"""<tr data-search="{escape(search)}" data-institution="{escape(person['institution'])}">
  <td class="num muted">{person['position']}</td>
  <td><div class="person"><a href="{profile_url}" tabindex="-1">{avatar(person, 'small')}</a><span class="who">{title}{handle_line}</span></div></td>
  <td class="num rating-cell {tier_class(person['rating'])}">{person['rating']}</td>
  <td class="num muted hide-small">{person['peak']}</td>
  <td class="num hide-small">{finish}</td>
  <td class="num hide-small">{person['contests']}</td>
</tr>""")
    options = "".join(
        f'<option value="{escape(i)}" data-search="{escape(institution_search_text(i))}">{escape(institution_name(i))}</option>'
        for i in institutions
    )
    contests = "".join(
        f'<li><span>{escape(name)}{f" <span class=credit>×{credit:g}</span>" if credit != 1 else ""}</span>'
        f'<span class="muted">{day:%b %Y}</span></li>'
        for name, day, credit in reversed(stats["contest_list"])
    )
    table = f"""<div class="table-wrap">
  <table class="table rankings" id="rankings">
    <thead><tr><th class="num">#</th><th>Contestant</th><th class="num">Rating</th><th class="num hide-small">Peak</th><th class="num hide-small nowrap">Best finish</th><th class="num hide-small">Contests</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
  <p class="empty" id="empty" hidden>No contestant matches your search.</p>
</div>"""
    finder = f"""<label class="field"><span>Name, handle, or institution</span>
  <input id="search" type="search" placeholder="Search" autocomplete="off"></label>
<label class="field"><span>Institution</span>
  <select id="institution" data-combobox><option value="">All institutions</option>{options}</select></label>"""
    body = f"""{hero(stats, "contestants")}
<div class="columns">
  <div class="main-column">{panel("Contestants", table, "flush")}</div>
  <aside class="sidebar">
    {panel("Find contestant", finder)}
    {panel("Rating colours", f'<div class="tier-legend">{legend}</div>')}
    {panel("Contests", f'<ul class="plain-list">{contests}</ul>')}
  </aside>
</div>"""
    return layout(TITLE, "", body, "rankings")


def hero(stats: dict, current: str) -> str:
    """The rankings' heading, figures, and the switch between contestants and institutions."""
    def switch(name: str, href: str, label: str) -> str:
        selected = ' aria-current="page"' if name == current else ""
        return f'<a href="{href}"{selected}>{label}</a>'

    return f"""<section class="hero">
  <h1>Ratings from onsite contests in Bangladesh</h1>
  <p class="lead">Ratings for contestants and institutions of inter-university programming contests and the ICPC Dhaka Regional, computed from official onsite standings since 2024.</p>
  <div class="stat-row">
    <div class="stat"><span class="stat-value">{stats['people']}</span><span class="stat-label">rated contestants</span></div>
    <div class="stat"><span class="stat-value">{stats['rated_institutions']}</span><span class="stat-label">rated institutions</span></div>
    <div class="stat"><span class="stat-value">{stats['contests']}</span><span class="stat-label">contests</span></div>
    <div class="stat"><span class="stat-value">{escape(stats['updated'])}</span><span class="stat-label">latest contest</span></div>
  </div>
</section>
<nav class="switch" aria-label="Rankings">{switch("contestants", "index.html", "Contestants")}{switch("institutions", "institutions.html", "Institutions")}</nav>"""


def institutions_page(institutions: list[dict], stats: dict, legend: str) -> str:
    rows = []
    for inst in institutions:
        best = best_finish(inst["history"])
        rows.append(f"""<tr data-search="{escape(institution_search_text(inst['name']))}">
  <td class="num muted">{inst['position']}</td>
  <td><a class="institution-name" href="i/{inst['key']}.html">{escape(institution_name(inst['name']))}</a></td>
  <td class="num rating-cell {tier_class(inst['rating'])}">{inst['rating']}</td>
  <td class="num muted hide-small">{inst['peak']}</td>
  <td class="num hide-small">{ordinal(best['rank']) if best else '<span class="muted">—</span>'}</td>
  <td class="num hide-small">{inst['contests']}</td>
  <td class="num hide-small">{len(inst['people']) or '<span class="muted">—</span>'}</td>
</tr>""")
    table = f"""<div class="table-wrap">
  <table class="table rankings" id="rankings">
    <thead><tr><th class="num">#</th><th>Institution</th><th class="num">Rating</th><th class="num hide-small">Peak</th><th class="num hide-small nowrap">Best finish</th><th class="num hide-small">Contests</th><th class="num hide-small">Contestants</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
  <p class="empty" id="empty" hidden>No institution matches your search.</p>
</div>"""
    finder = """<label class="field"><span>Institution name</span>
  <input id="search" type="search" placeholder="Search" autocomplete="off"></label>"""
    body = f"""{hero(stats, "institutions")}
<div class="columns">
  <div class="main-column">{panel("Institutions", table, "flush")}</div>
  <aside class="sidebar">
    {panel("Find institution", finder)}
    {panel("Rating colours", f'<div class="tier-legend">{legend}</div>')}
    {panel("About these ratings", '<p class="muted panel-note">An institution is rated from the results of its teams in each contest. Contestants are listed under the institution of their latest contest.</p>')}
  </aside>
</div>"""
    return layout(f"Institutions · {TITLE}", "", body, "rankings")


def institution_page(inst: dict, total: int) -> str:
    history = inst["history"]
    current = inst["rating"]
    tier = tier_class(current)
    best = best_finish(history)
    changes = [h["rating"] - history[i - 1]["rating"] if i else None for i, h in enumerate(history)]

    def best_of(values: list) -> set:
        present = [v for v in values if v is not None]
        return {v for v in present if v == max(present)} if len(history) > 1 and present else set()

    finish_key = lambda h: (-h["rank"], h["teams"]) if h["rank"] is not None else None
    bests = {
        "rank": best_of([finish_key(h) for h in history]),
        "score": best_of([h["score"] for h in history]),
        "rating": best_of([h["rating"] for h in history]),
        "change": best_of(changes),
    }
    mark = lambda column, value: " best" if value is not None and value in bests[column] else ""

    info = [
        f'{ICON_BISCUIT}<span>Biscuit rating: <strong class="{tier}">{current}</strong> '
        f'<span class="muted">(max. <strong class="{tier_class(inst["peak"])}">{inst["peak"]}</strong>)</span></span>',
        f'{ICON_TROPHY}<span>Best finish: <strong>{ordinal(best["rank"]) if best else "—"}</strong>'
        f'{" <span class=muted>of " + str(best["teams"]) + " teams at " + escape(best["contest"]) + "</span>" if best else ""}</span>',
        f'{ICON_CALENDAR}<span>Contests: <strong>{inst["contests"]}</strong></span>',
    ]
    rows = []
    for i, h in enumerate(history):
        change = changes[i]
        delta = (
            '<span class="delta new">new</span>' if change is None
            else f'<span class="delta {"up" if change > 0 else "down" if change < 0 else ""}">{change:+d}</span>'
        )
        rank = f'{h["rank"]}<span class="muted"> / {h["teams"]}</span>' if h["rank"] is not None else '<span class="muted">unranked</span>'
        best_members = next((e.get("members", []) for e in h["entries"] if e["team"] == h["best_team"]), [])
        rows.append(f"""<tr>
  <td class="nowrap">{contest_link(h['contest'], inst['name'], "../")}<span class="sub">{h['date']:%d %b %Y}</span></td>
  <td class="num hide-small">{h['teams_entered']}</td>
  <td class="team">{team_label(h['best_team'], best_members, "../") if best_members else escape(h['best_team'])}</td>
  <td class="num nowrap{mark('rank', finish_key(h))}">{rank}</td>
  <td class="num hide-small{mark('score', h['score'])}"><span class="{tier_class(h['score'])}">{h['score']}</span></td>
  <td class="num nowrap{mark('rating', h['rating'])}"><strong class="{tier_class(h['rating'])}">{h['rating']}</strong></td>
  <td class="num nowrap{mark('change', change)}">{delta}</td>
</tr>""")
    contests_table = f"""<div class="table-wrap">
  <table class="table history">
    <thead><tr><th>Contest</th><th class="num hide-small">Teams</th><th>Best team</th><th class="num">Rank</th><th class="num hide-small">Score</th><th class="num">Rating</th><th class="num">Change</th></tr></thead>
    <tbody>{''.join(reversed(rows))}</tbody>
  </table>
</div>"""
    shown = inst["people"][:10]
    people = "".join(
        f'<li><a class="person" href="../u/{escape(p["key"])}.html">{avatar(p, "small")}'
        f'<span class="who"><span class="person-name">{escape(display_name(p))}</span>'
        f'<span class="sub"><span class="handle-text {tier_class(p["rating"])}">{escape(p["handle"])}</span></span></span></a>'
        f'<span class="{tier_class(p["rating"])} rating-cell">{p["rating"]}</span></li>'
        for p in shown
    )
    everyone = (
        f'<p class="panel-more"><a href="../index.html?institution={quote(inst["name"], safe="")}">All {len(inst["people"])} contestants →</a></p>'
        if len(inst["people"]) > len(shown) else ""
    )
    contestants = (
        f'<ul class="plain-list teammates">{people}</ul>{everyone}' if shown
        else '<p class="muted">No contestants listed yet.</p>'
    )
    standing_box = f"""<div class="standing">
  <span class="rating-value {tier}">{current}</span>
  <span class="muted">{standing(inst['position'], total)}</span>
  <span class="muted">Rank #{inst['position']} of {total}</span>
</div>"""
    chart = rating_chart([{"date": h["date"], "rating": h["rating"], "contest": h["contest"], "rank": h["rank"], "teams": h["teams"]} for h in history])
    body = f"""<div class="columns">
  <div class="main-column">
    <section class="panel profile">
      <div class="profile-main">
        <p class="profile-institution">Institution</p>
        <h1 class="profile-name">{escape(institution_name(inst['name']))}</h1>
        <ul class="info-list">{''.join(f'<li>{item}</li>' for item in info)}</ul>
      </div>
    </section>
    {panel("Rating history", chart)}
    {panel("Contests", contests_table, "flush")}
  </div>
  <aside class="sidebar">
    {panel("Standing", standing_box)}
    {panel("Top contestants", contestants)}
  </aside>
</div>"""
    return layout(f"{institution_name(inst['name'])} · {TITLE}", "../", body, "rankings")


def profile_page(person: dict, total: int) -> str:
    profile = person.get("profile") or {}
    name = display_name(person)
    history = person["history"]
    current = person["rating"]
    tier = tier_class(current)

    handle_link = (
        f'<a class="handle" href="https://codeforces.com/profile/{escape(person["handle"])}" '
        f'rel="noopener" target="_blank"><span class="handle-text {tier}">{escape(person["handle"])}</span>{EXTERNAL}</a>'
    )
    best = best_finish(history)
    first_solves = sum(h["first_solves"] for h in history)
    institutions = list(dict.fromkeys(h["institution"] for h in reversed(history)))

    info = [
        f'{ICON_BISCUIT}<span>Biscuit rating: <strong class="{tier}">{current}</strong> '
        f'<span class="muted">(max. <strong class="{tier_class(person["peak"])}">{person["peak"]}</strong>)</span></span>',
        f'{ICON_TROPHY}<span>Best finish: <strong>{ordinal(best["rank"]) if best else "—"}</strong>'
        f'{" <span class=muted>of " + str(best["teams"]) + " teams at " + escape(best["contest"]) + "</span>" if best else ""}</span>',
        f'{ICON_STAR}<span>First solves: <strong>{first_solves}</strong></span>',
        f'{ICON_CALENDAR}<span>Contests: <strong>{person["contests"]}</strong></span>',
    ]
    # Codeforces' best: the max rating and its rank, not the current ones.
    if profile.get("maxRating"):
        info.append(
            f'{ICON_CF}<span>Codeforces max rating: <strong class="{codeforces_class(profile.get("maxRank"))}">'
            f'{profile["maxRating"]}</strong>'
            f'{" <span class=muted>(" + escape(profile["maxRank"].title()) + ")</span>" if profile.get("maxRank") else ""}</span>'
        )

    changes = [h["rating"] - history[i - 1]["rating"] if i else None for i, h in enumerate(history)]

    # The best value of each column is highlighted, ties included; one contest has nothing to compare.
    def best_of(values: list) -> set:
        present = [v for v in values if v is not None]
        return {v for v in present if v == max(present)} if len(history) > 1 and present else set()

    finish_key = lambda h: (-h["rank"], h["teams"]) if h["rank"] is not None else None
    best = {
        "rank": best_of([finish_key(h) for h in history]),
        "solved": best_of([h["solved"] for h in history]),
        "performance": best_of([h["performance"] for h in history]),
        "rating": best_of([h["rating"] for h in history]),
        "change": best_of(changes),
    }
    mark = lambda column, value: ' best' if value is not None and value in best[column] else ''

    table_rows = []
    for i, h in enumerate(history):
        change = changes[i]
        delta = (
            '<span class="delta new">new</span>' if change is None
            else f'<span class="delta {"up" if change > 0 else "down" if change < 0 else ""}">{change:+d}</span>'
        )
        stars = f'<span class="stars" title="First to solve {h["first_solves"]} problem(s)">★ {h["first_solves"]}</span>' if h["first_solves"] else '<span class="muted">—</span>'
        rank = f'{h["rank"]}<span class="muted"> / {h["teams"]}</span>' if h["rank"] is not None else '<span class="muted">unranked</span>'
        performance = f'<span class="{tier_class(h["performance"])}">{h["performance"]}</span>' if h["performance"] is not None else '<span class="muted">—</span>'
        table_rows.append(f"""<tr>
  <td class="nowrap">{contest_link(h['contest'], h['institution'], "../")}<span class="sub">{h['date']:%d %b %Y}</span></td>
  <td class="team">{team_label(h['team'], h['members'], "../")}</td>
  <td class="num nowrap{mark('rank', finish_key(h))}">{rank}</td>
  <td class="num nowrap hide-small{mark('solved', h['solved'])}">{h['solved']}<span class="muted"> / {h['problems']}</span></td>
  <td class="num hide-small">{stars}</td>
  <td class="num hide-small{mark('performance', h['performance'])}">{performance}</td>
  <td class="num nowrap{mark('rating', h['rating'])}"><strong class="{tier_class(h['rating'])}">{h['rating']}</strong></td>
  <td class="num nowrap{mark('change', change)}">{delta}</td>
</tr>""")

    # Teammates, most recent first: walking the history backwards meets each one
    # first at their latest contest together.
    teammates = {}
    for h in reversed(history):
        for member in h["members"]:
            if member["key"] != person["key"]:
                teammates.setdefault(member["key"], {"member": member, "latest": h["contest"], "together": 0})["together"] += 1
    teammate_list = "".join(
        f'<li><a class="person" href="{escape(t["member"]["key"])}.html">{avatar(t["member"], "small")}'
        f'<span class="who"><span class="person-name">{escape(t["member"]["name"])}</span>'
        f'<span class="sub"><span class="handle-text {tier_class(t["member"]["rating"])}">{escape(t["member"]["handle"])}</span>'
        f' · <span class="nowrap">{escape(t["latest"])}</span></span></span></a>'
        f'<span class="muted nowrap">{t["together"]} contest{"s" if t["together"] > 1 else ""}</span></li>'
        for t in teammates.values()
    )
    standing_box = f"""<div class="standing">
  <span class="rating-value {tier}">{current}</span>
  <span class="muted">{standing(person['position'], total)}</span>
  <span class="muted">Rank #{person['position']} of {total}</span>
  <span class="muted">Last active rank: #{person['last_active'][0]} of {person['last_active'][1]}</span>
</div>"""

    chart = rating_chart([{'date': h['date'], 'rating': h['rating'], 'contest': h['contest'], 'rank': h['rank'], 'teams': h['teams']} for h in history])
    contests_table = f"""<div class="table-wrap">
  <table class="table history">
    <thead><tr><th>Contest</th><th>Team</th><th class="num">Rank</th><th class="num hide-small">Solved</th><th class="num hide-small">First solves</th><th class="num hide-small">Performance</th><th class="num">Rating</th><th class="num">Change</th></tr></thead>
    <tbody>{''.join(reversed(table_rows))}</tbody>
  </table>
</div>"""
    body = f"""<div class="columns">
  <div class="main-column">
    <section class="panel profile">
      <div class="profile-main">
        <p class="profile-institution">{' · '.join(institution_link(i, "../") for i in institutions)}</p>
        <h1 class="profile-name">{escape(name)}</h1>
        <p class="profile-handle">{handle_link}</p>
        <ul class="info-list">{''.join(f'<li>{item}</li>' for item in info)}</ul>
      </div>
      <div class="profile-photo">{avatar(person, 'large')}</div>
    </section>
    {panel("Rating history", chart)}
    {panel("Contests", contests_table, "flush")}
  </div>
  <aside class="sidebar">
    {panel("Standing", standing_box)}
    {panel("Teammates", f'<ul class="plain-list teammates">{teammate_list}</ul>' if teammates else '<p class="muted">No teammates listed yet.</p>')}
  </aside>
</div>"""
    return layout(f"{name} ({person['handle']}) · {TITLE}", "../", body)


def about_page(legend: str) -> str:
    body = f"""<article class="panel prose">
  <h1>About</h1>
  <p>Biscuit Rating rates contestants of onsite programming contests in Bangladesh: inter-university programming contests (IUPCs) and the ICPC Dhaka Regional. Ratings are computed only from official final standings.</p>
  <p><strong>Contests are included from January 2024 onwards.</strong> Results from earlier contests are not counted, so ratings reflect only performance since then.</p>

  <h2>Rating colours</h2>
  <div class="tier-legend">{legend}</div>

  <h2>Getting listed and corrections</h2>
  <p>Team members are provided by contestants themselves. To be listed, or to correct a mistake, fill in the <a href="form.html">Get listed</a> form. Names and photos come from public Codeforces profiles.</p>
</article>"""
    return layout(f"About · {TITLE}", "", body, "about")


def form_page(data_url: str) -> str:
    """The "Get listed" form. form.js fills in the contests and handles each step."""
    body = f"""<section class="form-intro">
  <h1>Get listed</h1>
  <p class="lead">Tell us which teams you were part of. Your rating comes from your teams' official results.</p>
</section>
<div class="form-shell" id="form" data-src="{escape(data_url)}">
  <ol class="steps" aria-label="Steps">
    <li data-step="1" aria-current="step">You</li>
    <li data-step="2">Your contests</li>
    <li data-step="3">Review</li>
  </ol>

  <section class="panel form-step" data-step="1">
    <h2 class="panel-title"><span class="arrow" aria-hidden="true">→</span> About you</h2>
    <div class="panel-body">
      <label class="field"><span>Full name</span>
        <input id="name" autocomplete="name" required></label>
      <label class="field"><span>Codeforces handle</span>
        <input id="handle" autocomplete="off" autocapitalize="off" spellcheck="false" required></label>
      <label class="field"><span>Institution</span>
        <select id="institution" data-combobox required><option value="">Choose your institution</option></select></label>
      <div class="profile-check" id="profile-check" hidden></div>
      <p class="form-error" id="step1-error" role="alert" hidden></p>
      <div class="form-actions">
        <button type="button" class="button primary" id="check">Check handle</button>
        <button type="button" class="button primary" id="to-step2" hidden>Yes, this is me</button>
      </div>
    </div>
  </section>

  <section class="panel form-step" data-step="2" hidden>
    <h2 class="panel-title"><span class="arrow" aria-hidden="true">→</span> Your contests</h2>
    <div class="panel-body">
      <p class="muted form-note">Pick your team in each contest you took part in, and leave the rest as "Did not take part". Teams already known to include you are picked for you. Teammates' handles are optional.</p>
      <div id="contest-list"></div>
      <p class="form-error" id="step2-error" role="alert" hidden></p>
      <div class="form-actions">
        <button type="button" class="button" data-back="1">Back</button>
        <button type="button" class="button primary" id="to-step3">Review</button>
      </div>
    </div>
  </section>

  <section class="panel form-step" data-step="3" hidden>
    <h2 class="panel-title"><span class="arrow" aria-hidden="true">→</span> Review</h2>
    <div class="panel-body">
      <div id="review"></div>
      <p class="form-error" id="step3-error" role="alert" hidden></p>
      <div class="form-actions">
        <button type="button" class="button" data-back="2">Back</button>
        <button type="button" class="button primary" id="submit">Submit</button>
      </div>
    </div>
  </section>

  <section class="panel form-step" data-step="4" hidden>
    <div class="panel-body form-done">
      <h2>Thank you</h2>
      <p id="done-message">Your answers will appear on the site once they are checked.</p>
    </div>
  </section>
</div>
<script src="assets/form.js?v={ASSET_VERSION}" defer></script>"""
    return layout(f"Get listed · {TITLE}", "", body, "form")


def institution_contest_page(inst: dict, index: int, total: int) -> str:
    """One institution's teams in one contest, with its score and rating."""
    h = inst["history"][index]
    previous = inst["history"][index - 1]["rating"] if index else None
    change = h["rating"] - previous if previous is not None else None
    name = institution_name(inst["name"])
    tier = tier_class(h["rating"])
    delta = (
        '<span class="delta new">first contest</span>' if change is None
        else f'<span class="delta {"up" if change > 0 else "down" if change < 0 else ""}">{change:+d}</span>'
    )
    best = best_finish([h]) if h["rank"] is not None else None
    standings = (
        f' · <a href="{escape(h["standings"])}" rel="noopener" target="_blank">Standings{EXTERNAL}</a>' if h["standings"] else ""
    )
    info = [
        f'{ICON_BISCUIT}<span>Rating after: <strong class="{tier}">{h["rating"]}</strong> {delta}</span>',
        f'{ICON_STAR}<span>Score: <strong class="{tier_class(h["score"])}">{h["score"]}</strong>'
        f'{" <span class=muted>(" + ordinal(h["score_rank"]) + " of " + str(h["scored"]) + " institutions)</span>" if h["score_rank"] else ""}</span>',
        f'{ICON_TROPHY}<span>Best finish: <strong>{ordinal(best["rank"]) if best else "—"}</strong>'
        f'{" <span class=muted>of " + str(h["teams"]) + " teams</span>" if best else ""}</span>',
        f'{ICON_CALENDAR}<span>Teams: <strong>{h["teams_entered"]}</strong></span>',
    ]
    problems = h["problems"] or max((e["solved"] for e in h["entries"]), default=0)
    rows = "".join(
        f"""<tr>
  <td class="num nowrap">{f'{e["rank"]}<span class="muted"> / {h["teams"]}</span>' if e["rank"] is not None else '<span class="muted">unranked</span>'}</td>
  <td class="team">{team_label(e["team"], e["members"], "../../") if e["members"] else escape(e["team"])}</td>
  <td class="num nowrap">{e["solved"]}<span class="muted"> / {problems}</span></td>
  <td class="num hide-small">{e["penalty"]}</td>
  <td class="num hide-small">{f'<span class="stars">★ {e["first_solves"]}</span>' if e["first_solves"] else '<span class="muted">—</span>'}</td>
  <td class="num">{f'<span class="{tier_class(e["performance"])}">{e["performance"]}</span>' if e["performance"] is not None else '<span class="muted">—</span>'}</td>
</tr>"""
        for e in h["entries"]
    )
    teams_table = f"""<div class="table-wrap">
  <table class="table history">
    <thead><tr><th class="num">Rank</th><th>Team</th><th class="num">Solved</th><th class="num hide-small">Penalty</th><th class="num hide-small">First solves</th><th class="num">Performance</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div>"""
    contests = "".join(
        f'<li{" class=current" if i == index else ""}><span>'
        + (f"<strong>{escape(c['contest'])}</strong>" if i == index else f'<a href="{c["id"]}.html">{escape(c["contest"])}</a>')
        + f'</span><span class="muted">{c["date"]:%b %Y}</span></li>'
        for i, c in reversed(list(enumerate(inst["history"])))
    )
    body = f"""<div class="columns">
  <div class="main-column">
    <section class="panel profile">
      <div class="profile-main">
        <p class="profile-institution"><a class="institution-link" href="../{inst['key']}.html">{escape(name)}</a></p>
        <h1 class="profile-name">{escape(h['contest'])}</h1>
        <p class="profile-handle muted">{h['date']:%d %B %Y}{standings}</p>
        <ul class="info-list">{''.join(f'<li>{item}</li>' for item in info)}</ul>
      </div>
    </section>
    {panel(f"Teams of {escape(name)}", teams_table, "flush")}
  </div>
  <aside class="sidebar">
    {panel("Contests", f'<ul class="plain-list contest-nav">{contests}</ul>')}
  </aside>
</div>"""
    return layout(f"{name} at {h['contest']} · {TITLE}", "../../", body, "rankings")

