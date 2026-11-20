import hashlib
import json
import shutil
from datetime import date
from pathlib import Path

import pandas as pd

from codeforces import load_cache, profile

from . import pages
from .form import form_data, form_settings
from .institutions import load_institutions
from .theme import TIERS

STATIC = Path(__file__).with_name("static")


def _int(value) -> int | None:
    return None if pd.isna(value) else int(value)


def _rosters(ratings: pd.DataFrame, history: pd.DataFrame, cache: dict) -> dict[tuple, list[dict]]:
    """Rated members of each team, keyed by contest, team, and institution."""
    current = dict(zip(ratings["Handle"], ratings["Rating"]))
    rosters = {}
    for row in history[["Contest", "Team", "Institution", "Handle"]].itertuples(index=False):
        cf = profile(cache, row.Handle)
        handle = cf["handle"] if cf else row.Handle
        name = " ".join(part for part in ((cf or {}).get("firstName"), (cf or {}).get("lastName")) if part) or handle
        rosters.setdefault((row.Contest, row.Team, row.Institution), []).append(
            {"key": row.Handle, "handle": handle, "name": name, "profile": cf, "rating": int(current[row.Handle])}
        )
    return rosters


def _last_active(history: pd.DataFrame) -> dict[str, tuple[int, int]]:
    """Each contestant's position in the rankings right after their last contest,
    with the number of contestants rated by then."""
    standings = {}
    rating = {}
    for _, rows in history.sort_values(["Date", "Contest"], kind="stable").groupby(["Date", "Contest"], sort=False):
        rating.update(zip(rows["Handle"], rows["Rating"]))
        ordered = sorted(rating.values(), reverse=True)
        # Equal ratings share a position, as in the rankings; later contests overwrite earlier ones.
        for handle in rows["Handle"]:
            standings[handle] = (ordered.index(rating[handle]) + 1, len(ordered))
    return standings


def _people(ratings: pd.DataFrame, history: pd.DataFrame, credits: dict, cache: dict, rosters: dict) -> list[dict]:
    people = []
    last_active = _last_active(history)
    by_handle = {handle: rows for handle, rows in history.groupby("Handle", sort=False)}
    position = 0
    previous_rating = None
    for index, row in enumerate(ratings.to_dict("records"), start=1):
        # Equal ratings share a position.
        if row["Rating"] != previous_rating:
            position, previous_rating = index, row["Rating"]
        cf = profile(cache, row["Handle"])
        people.append({
            "key": row["Handle"],
            "handle": cf["handle"] if cf else row["Handle"],
            "profile": cf,
            "rating": int(row["Rating"]),
            "peak": int(row["Peak"]),
            "contests": int(row["Contests"]),
            "last_contest": row["Last Contest"],
            "institution": row["Institution"],
            "position": position,
            "last_active": last_active[row["Handle"]],
            "history": [
                {
                    "date": date.fromisoformat(h["Date"]),
                    "contest": h["Contest"],
                    "credit": credits.get(h["Contest"], 1),
                    "team": h["Team"],
                    "members": rosters[h["Contest"], h["Team"], h["Institution"]],
                    "institution": h["Institution"],
                    "rank": _int(h["Rank"]),
                    "teams": int(h["Teams"]),
                    "solved": int(h["Solved"]),
                    "problems": int(h["Problems"]),
                    "first_solves": int(h["First Solves"]),
                    "performance": _int(h["Performance"]),
                    "rating": int(h["Rating"]),
                }
                for h in by_handle[row["Handle"]].to_dict("records")
            ],
        })
    return people


def build(
    output_directory: Path,
    ratings_directory: Path,
    codeforces_cache: Path,
    credits_path: Path,
    members_path: Path | None = None,
    contests_path: Path | None = None,
    form_path: Path | None = None,
    rating_directory: Path | None = None,
    score_directory: Path | None = None,
    performances_path: Path | None = None,
    contests_directory: Path | None = None,
) -> Path:
    """Write the static site: the rankings, one page per person, the about page,
    and, given the members and contests files, the "Get listed" form."""
    # Handles and names are text even when they look like numbers or "NA".
    ratings = pd.read_csv(ratings_directory / "ratings.csv", keep_default_na=False, dtype={"Handle": str})
    history = pd.read_csv(
        ratings_directory / "history.csv",
        keep_default_na=False,
        na_values={"Rank": [""], "Performance": [""]},
        dtype={"Handle": str, "Team": str, "Contest": str},
    )
    credits = {k.upper(): v for k, v in json.loads(credits_path.read_text()).items()}
    cache = load_cache(codeforces_cache)
    rosters = _rosters(ratings, history, cache)
    people = _people(ratings, history, credits, cache, rosters)

    if output_directory.exists():
        shutil.rmtree(output_directory)
    (output_directory / "u").mkdir(parents=True)
    shutil.copytree(STATIC, output_directory / "assets")

    latest = history.sort_values("Date").iloc[-1] if len(history) else None
    contest_list = [
        (name, date.fromisoformat(day), credits.get(name, 1))
        for name, day in history[["Contest", "Date"]].drop_duplicates().sort_values(["Date", "Contest"]).itertuples(index=False)
    ]
    stats = {
        "contest_list": contest_list,
        "people": len(people),
        "contests": history["Contest"].nunique(),
        "institutions": history["Institution"].nunique(),
        "rated_institutions": 0,
        "updated": latest["Contest"] if latest is not None else "—",
    }
    legend = "".join(
        f'<span class="tier-chip tier-{i}">{low}{"+" if i == len(TIERS) - 1 else f"–{TIERS[i + 1] - 1}"}</span>'
        for i, low in enumerate(TIERS)
    )
    institutions = []
    if rating_directory and score_directory and performances_path and contests_directory and rating_directory.exists():
        standings = {}
        if contests_path and contests_path.is_file():
            standings = {c["name"].upper(): c.get("standings", "") for c in json.loads(contests_path.read_text())["contests"]}
        institutions = load_institutions(rating_directory, score_directory, performances_path, contests_directory, people, standings)
        for inst in institutions:
            for h in inst["history"]:
                for entry in h["entries"]:
                    entry["members"] = rosters.get((h["contest"], entry["team"], inst["name"]), [])
    stats["rated_institutions"] = len(institutions)
    pages.INSTITUTION_PAGES.clear()
    pages.INSTITUTION_PAGES.update(inst["key"] for inst in institutions)
    pages.INSTITUTION_CONTEST_PAGES.clear()
    pages.INSTITUTION_CONTEST_PAGES.update((inst["key"], h["id"]) for inst in institutions for h in inst["history"])
    if institutions:
        (output_directory / "i").mkdir()
        (output_directory / "institutions.html").write_text(pages.institutions_page(institutions, stats, legend))
        for inst in institutions:
            (output_directory / "i" / f"{inst['key']}.html").write_text(pages.institution_page(inst, len(institutions)))
            (output_directory / "i" / inst["key"]).mkdir()
            for index, h in enumerate(inst["history"]):
                (output_directory / "i" / inst["key"] / f"{h['id']}.html").write_text(
                    pages.institution_contest_page(inst, index, len(institutions))
                )
    (output_directory / "index.html").write_text(pages.rankings_page(people, stats, legend))
    for person in people:
        (output_directory / "u" / f"{person['key']}.html").write_text(pages.profile_page(person, len(people)))
    (output_directory / "about.html").write_text(pages.about_page(legend))
    if members_path and contests_path and members_path.is_file() and contests_path.is_file():
        data = {**form_data(members_path, contests_path), "settings": form_settings(form_path)}
        text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        (output_directory / "assets/form-data.json").write_text(text)
        version = hashlib.sha256(text.encode()).hexdigest()[:10]
        (output_directory / "form.html").write_text(pages.form_page(f"assets/form-data.json?v={version}"))
    (output_directory / ".nojekyll").write_text("")
    return output_directory
