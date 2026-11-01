"""Institution ratings for the site, read from the rating and score calculators' outputs."""

from datetime import date
from pathlib import Path

import pandas as pd

from contests import load_contests
from contests.store import contest_id


def institution_key(name: str) -> str:
    """The institution's page name: its name in lower case, words joined by hyphens."""
    return "-".join("".join(c.lower() if c.isalnum() else " " for c in name).split())


def _wide(path: Path, prefix: str) -> dict[str, dict[str, float]]:
    """Institution -> contest -> value, from a file with one `{prefix}{contest}` column per contest."""
    frame = pd.read_csv(path, keep_default_na=False, na_values=[""]).set_index("Institution")
    return {
        institution: {
            column.removeprefix(prefix): value
            for column, value in row.items()
            if column.startswith(prefix) and pd.notna(value)
        }
        for institution, row in frame.iterrows()
    }


def load_institutions(
    rating_directory: Path,
    score_directory: Path,
    performances_path: Path,
    contests_directory: Path,
    people: list[dict],
    standings: dict[str, str] | None = None,
) -> list[dict]:
    """Rated institutions, best first, each with its contest history (every team's
    result included) and rated contestants. `standings` maps contests to their
    public standings pages."""
    standings = standings or {}
    latest = pd.read_csv(rating_directory / "latest_ratings.csv", keep_default_na=False)
    ratings = _wide(rating_directory / "ratings_history.csv", "Rating After ")
    scores = _wide(score_directory / "score_history.csv", "Score In ")
    score_ranks = _wide(score_directory / "score_rank_history.csv", "Score Rank In ")
    contests = {contest.name: contest for contest in load_contests(contests_directory)}

    # performances.csv lists each contest's teams in standings order, with resolved institutions.
    performances = pd.read_csv(performances_path, keep_default_na=False, na_values={"Performance": [""]}, dtype={"Team": str})
    entries: dict[tuple[str, str], list] = {}
    for name, rows in performances.groupby("Contest", sort=False):
        contest = contests[name]
        ranked = sum(team.rank is not None for team in contest.teams)
        for team, institution, performance in zip(contest.teams, rows["Institution"], rows["Performance"]):
            if institution:
                entries.setdefault((institution, name), []).append((team, ranked, None if pd.isna(performance) else round(performance)))
    # How many institutions got a score in each contest.
    scored = {}
    for by_contest in scores.values():
        for contest_name in by_contest:
            scored[contest_name] = scored.get(contest_name, 0) + 1

    members = {}
    for person in people:
        members.setdefault(person["institution"], []).append(person)

    institutions = []
    position, previous = 0, None
    for index, row in enumerate(latest.to_dict("records"), start=1):
        name, rating = row["Institution"], int(row["Rating"])
        if rating != previous:
            position, previous = index, rating
        history = []
        for contest_name, score in sorted(scores.get(name, {}).items(), key=lambda item: contests[item[0]].date):
            if contest_name not in ratings[name]:
                continue  # zero-credit contests before the first credited one leave no rating
            teams = entries.get((name, contest_name), [])
            ranked_teams = [team for team, _, _ in teams if team.rank is not None]
            best = min(ranked_teams, key=lambda team: team.rank, default=None)
            history.append({
                "contest": contest_name,
                "date": date.fromisoformat(contests[contest_name].date),
                "teams_entered": len(teams),
                "best_team": best.name if best else (teams[0][0].name if teams else ""),
                "rank": best.rank if best else None,
                "teams": teams[0][1] if teams else len(contests[contest_name].teams),
                "score": round(score),
                "score_rank": int(score_ranks.get(name, {}).get(contest_name, 0)) or None,
                "scored": scored[contest_name],
                "rating": int(ratings[name][contest_name]),
                "id": contest_id(contest_name),
                "standings": standings.get(contest_name, ""),
                "problems": contests[contest_name].problems,
                "entries": [
                    {
                        "team": team.name,
                        "rank": team.rank,
                        "solved": team.solved,
                        "penalty": team.penalty,
                        "first_solves": team.first_solve_count,
                        "performance": performance,
                    }
                    for team, _, performance in teams
                ],
            })
        if not history:
            continue
        institutions.append({
            "key": institution_key(name),
            "name": name,
            "rating": rating,
            "peak": max(h["rating"] for h in history),
            "position": position,
            "contests": len(history),
            "history": history,
            "people": members.get(name, []),
        })
    return institutions
