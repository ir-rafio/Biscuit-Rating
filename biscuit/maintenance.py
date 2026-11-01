import json
import re
import shutil
from datetime import date
from pathlib import Path

import pandas as pd

from contests import load_contests
from institution_finder import InstitutionFinder
from members import find_team, is_missing
from parser import get_parser


def write_contests(path: Path, contests: dict) -> None:
    """Write contests.json with one field per line and each file list on one line."""
    entries = [
        "    {\n" + ",\n".join(f"      {json.dumps(key)}: {json.dumps(value, ensure_ascii=False)}" for key, value in contest.items()) + "\n    }"
        for contest in contests["contests"]
    ]
    path.write_text('{\n  "contests": [\n' + ",\n".join(entries) + "\n  ]\n}\n")


def saved_page_url(html_path: Path) -> str:
    """The address a browser saved the page from, as it notes at the top of the file."""
    match = re.search(r"saved from url=\(\d+\)(\S+)", html_path.read_text(errors="ignore")[:4096])
    return match.group(1) if match else ""


def add_contest(
    root: Path,
    html_paths: list[Path],
    name: str,
    contest_date: str,
    parser: str,
    credit: float = 1,
    standings: str = "",
) -> None:
    """Copy a contest's standings in and register it with the parser and the rating calculator.

    `standings` is the public standings page; by default it is the address the
    first HTML file was saved from.
    """
    name = name.strip().upper()
    date.fromisoformat(contest_date)
    get_parser(parser)
    if credit < 0:
        raise ValueError("Credit must be zero or more.")
    if not html_paths:
        raise ValueError("At least one contest HTML file is required.")
    contests_path = root / "parser/input/contests.json"
    credits_path = root / "rating_calculator/input/credits.json"
    contests = json.loads(contests_path.read_text())
    credits = json.loads(credits_path.read_text())
    if any(contest["name"].upper() == name for contest in contests["contests"]) or name in credits:
        raise ValueError(f"Contest already exists: {name}")
    destinations = [root / "parser/input/contest_files" / path.name for path in html_paths]
    for source, destination in zip(html_paths, destinations):
        if not source.is_file():
            raise FileNotFoundError(f"Contest HTML not found: {source}")
        if destination.exists():
            raise FileExistsError(f"Contest HTML already exists: {destination}")
    for source, destination in zip(html_paths, destinations):
        shutil.copy2(source, destination)
    contests["contests"].append({
        "name": name,
        "filenames": [path.name for path in html_paths],
        "parser": parser.upper(),
        "date": contest_date,
        "standings": standings or saved_page_url(html_paths[0]),
    })
    credits[name] = credit
    write_contests(contests_path, contests)
    credits_path.write_text(json.dumps(credits, indent=2) + "\n")


def unresolved_institutions(
    contests_directory: Path,
    database_path: Path,
    contest_names: list[str] | None = None,
) -> dict[str, list[str]]:
    """Map each institution name in parsed standings that does not resolve to its contests."""
    finder = InstitutionFinder(database_path)
    contests = load_contests(contests_directory)
    if contest_names:
        selected = {name.upper() for name in contest_names}
        unknown = selected - {contest.name for contest in contests}
        if unknown:
            raise ValueError(f"Parsed contest not found: {', '.join(sorted(unknown))}")
        contests = [contest for contest in contests if contest.name in selected]
    unresolved = {}
    for contest in contests:
        for team in contest.teams:
            if team.institution and finder.resolve(team.institution) is None:
                appearances = unresolved.setdefault(team.institution.upper(), [])
                if contest.name not in appearances:
                    appearances.append(contest.name)
    return dict(sorted(unresolved.items()))


def complete_members(members_path: Path, contests_directory: Path, database_path: Path) -> int:
    """Give every team of a known institution a row in the members file.

    Teams without one get a row with empty members, to be filled in later.
    Institutions are written with their canonical names, and rows are sorted
    by institution, contest date, and team name. Returns the number of rows
    added.
    """
    finder = InstitutionFinder(database_path)
    contests = load_contests(contests_directory)
    order = {contest.name: position for position, contest in enumerate(contests)}
    by_name = {contest.name: contest for contest in contests}
    frame = pd.read_csv(members_path, dtype=str, keep_default_na=False)
    member_columns = [column for column in frame.columns if column.startswith("member")]

    rows = []
    listed = set()
    for row in frame.to_dict("records"):
        contest = by_name.get(row["contest"].upper())
        team = find_team(contest, row["team_name"], row["institution"]) if contest else None
        if team is not None:
            row["institution"] = finder.resolve(team.institution) or row["institution"]
            listed.add((contest.name, team.name))
        for column in member_columns:
            if is_missing(row[column]):
                row[column] = ""
        rows.append(row)

    added = 0
    for contest in contests:
        for team in contest.teams:
            institution = finder.resolve(team.institution)
            if institution is None or (contest.name, team.name) in listed:
                continue
            listed.add((contest.name, team.name))
            rows.append({
                **{column: "" for column in frame.columns},
                "contest": contest.name,
                "institution": institution,
                "team_name": team.name,
                **{column: "" for column in member_columns},
            })
            added += 1

    rows.sort(key=lambda row: (row["institution"], order.get(row["contest"].upper(), len(order)), row["team_name"].lower()))
    pd.DataFrame(rows, columns=frame.columns).to_csv(members_path, index=False)
    return added


def import_form_responses(members_path: Path, response_paths: list[Path], apply: bool = False) -> tuple[list[str], list[str]]:
    """Add the handles from "Get listed" form responses to the members file.

    Each response names a person, their handle, and their team in each contest,
    with optional teammates. A handle goes into its team's first free member
    cell; a handle already listed elsewhere in that contest, a full team, or a
    team not in the standings is reported for review instead. A person's latest
    response replaces their earlier ones. Writes the file only with `apply`.
    Returns the changes and the problems.
    """
    frame = pd.read_csv(members_path, dtype=str, keep_default_na=False)
    member_columns = [column for column in frame.columns if column.startswith("member")]
    index = {(row.contest.upper(), row.team_name): i for i, row in frame.iterrows()}

    sheets = []
    for path in response_paths:
        sheet = pd.read_csv(path, dtype=str, keep_default_na=False)
        sheet.columns = [column.strip().lower() for column in sheet.columns]
        sheets.append(sheet)
    rows = pd.concat(sheets, ignore_index=True)
    # Google Sheets writes month/day/year times and the page's own file ISO ones;
    # compare them as times, not text, to find each person's latest response.
    rows["time"] = pd.to_datetime(rows.get("timestamp", ""), format="mixed", errors="coerce")
    responses = {}
    for row in rows.sort_values("time", kind="stable", na_position="first").to_dict("records"):
        responses[row["handle"].strip().lower()] = row

    changes, problems = [], []
    for row in responses.values():
        handle = row["handle"].strip()
        who = f"{row['name'].strip()} ({handle})"
        try:
            teams = json.loads(row["teams"])
        except json.JSONDecodeError:
            problems.append(f"{who}: the Teams answer is not readable.")
            continue
        for entry in teams:
            contest, team = entry["contest"].upper(), entry["team"].strip()
            target = index.get((contest, team))
            if target is None:
                problems.append(f"{who}: {contest} has no team {team!r} in {members_path.name}.")
                continue
            for member in [handle, *entry.get("teammates", [])]:
                listed = [frame.at[target, column] for column in member_columns]
                if member.lower() in {value.lower() for value in listed}:
                    continue
                elsewhere = [
                    frame.at[i, "team_name"] for (name, _), i in index.items()
                    if name == contest and i != target
                    and member.lower() in {frame.at[i, column].lower() for column in member_columns}
                ]
                if elsewhere:
                    problems.append(f"{who}: {member} is already in {elsewhere[0]} in {contest}, not {team}.")
                    continue
                free = next((column for column in member_columns if is_missing(frame.at[target, column])), None)
                if free is None:
                    problems.append(f"{who}: {team} in {contest} is full ({', '.join(listed)}); {member} not added.")
                    continue
                frame.at[target, free] = member
                changes.append(f"{contest} {team}: + {member} (from {who})")
    if apply:
        frame.to_csv(members_path, index=False)
    return changes, problems
