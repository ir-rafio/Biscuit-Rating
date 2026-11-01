import json
import math
import tempfile
from pathlib import Path

import pandas as pd
import pytest

import codeforces.client as client
import contestant_rating
import website
from contests import load_contests
from members import load_members, validate

ROOT = Path(__file__).resolve().parents[1]
CONTESTS = ROOT / "parser/output"


def contest(name):
    return next(c for c in load_contests(CONTESTS) if c.name == name)


def write_members(path: Path, rows: list[list[str]]) -> Path:
    pd.DataFrame(rows, columns=["contest", "institution", "team_name", "member1", "member2", "member3"]).to_csv(path, index=False)
    return path


def test_members_validation_explains_every_problem():
    winner = contest("ICPC 2025").teams[0]
    with tempfile.TemporaryDirectory() as directory:
        path = write_members(Path(directory) / "members.csv", [
            ["ICPC 2025", winner.institution, winner.name, "good_handle", "", ""],
            ["ICPC 2025", winner.institution, winner.name[:-1], "other_handle", "", ""],
            ["NOPE 2020", "X", "Y", "zz_top", "", ""],
            ["ICPC 2025", winner.institution, winner.name, "good_handle", "bad handle", ""],
            ["NSU 2026", "INSTITUTE", "first_name", "placeholder", "", ""],
        ])
        errors = validate(path, CONTESTS)
        assert any("line 3" in e and f"Did you mean {winner.name!r}" in e for e in errors)
        assert any("line 4" in e and "unknown contest" in e for e in errors)
        assert any("line 5" in e and "already listed" in e for e in errors)
        assert any("line 5" in e and "not a valid Codeforces handle" in e for e in errors)
        assert any("line 6" in e and "11 teams" in e for e in errors)
        assert not any(e.startswith("members.csv line 2:") for e in errors)
        # Empty member cells are skipped.
        assert [m.handle for m in load_members(path)][:1] == ["good_handle"]


def test_contestant_rating_starts_from_a_virtual_contest():
    winner = contest("ICPC 2025").teams[0]
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        members = write_members(root / "members.csv", [
            ["ICPC 2025", winner.institution, winner.name, "Solo_Winner", "", ""],
        ])
        contestant_rating.run(
            ROOT / "contestant_rating/input", members, ROOT / "performance_calculator/output",
            CONTESTS, ROOT / "rating_calculator/input", root / "out",
        )
        ratings = pd.read_csv(root / "out/ratings.csv")
        history = pd.read_csv(root / "out/history.csv")
    # One 4000 performance against the 1000-rated, credit-1 virtual contest.
    assert ratings["Handle"].tolist() == ["solo_winner"]
    assert ratings["Rating"].iloc[0] == round(math.sqrt((1000 ** 2 + 4000 ** 2) / 2))
    assert history.iloc[0][["Rank", "Solved", "Performance"]].tolist() == [1, winner.solved, 4000]


def test_virtual_contest_share_depends_on_credits_not_time():
    icpc, aust = contest("ICPC 2024").teams[0], contest("ICPC 2025").teams[0]
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        members = write_members(root / "members.csv", [
            ["ICPC 2024", icpc.institution, icpc.name, "champion", "", ""],
            ["ICPC 2025", aust.institution, aust.name, "champion", "", ""],
        ])
        contestant_rating.run(
            ROOT / "contestant_rating/input", members, ROOT / "performance_calculator/output",
            CONTESTS, ROOT / "rating_calculator/input", root / "out",
        )
        history = pd.read_csv(root / "out/history.csv")
    assert history["Performance"].tolist() == [4000, 4000]
    # The prior's share is 1/(1 + 1) after the first ICPC and 1/(1 + 1 + 1) after the second,
    # however much the first has decayed: winning again raises the rating.
    assert history["Rating"].tolist() == [round(math.sqrt((1000 ** 2 + 4000 ** 2) / 2)), round(math.sqrt((1000 ** 2 + 2 * 4000 ** 2) / 3))]


def test_codeforces_fetch_skips_unknown_and_records_renames(monkeypatch):
    replies = [
        {"status": "FAILED", "comment": "handles: User with handle ghost not found"},
        {"status": "OK", "result": [{"handle": "NewName", "rank": "expert"}, {"handle": "same", "rank": "pupil"}]},
    ]
    monkeypatch.setattr(client, "_request", lambda handles: replies.pop(0))
    monkeypatch.setattr(client, "PAUSE_SECONDS", 0)
    profiles, missing, renamed = client.fetch(["OldName", "ghost", "same"], log=lambda message: None)
    assert missing == ["ghost"]
    assert renamed == {"OldName": "NewName"}
    assert set(profiles) == {"newname", "same"}
    cache = {"users": profiles, "missing": missing}
    assert client.profile(cache, "NEWNAME")["rank"] == "expert"
    assert client.current_handles(cache, ["newname", "same"]) == {"newname": "NewName"}


def test_website_builds_every_page_and_escapes_text():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        ratings = root / "ratings"
        ratings.mkdir()
        pd.DataFrame([{"Handle": "alice", "Rating": 2100, "Peak": 2200, "Contests": 2, "Last Contest": "IUT 2026", "Institution": "UNIVERSITY OF DHAKA"}]).to_csv(ratings / "ratings.csv", index=False)
        pd.DataFrame([
            {"Handle": "alice", "Contest": "ICPC 2025", "Date": "2025-12-20", "Team": "<script>x</script>", "Institution": "UNIVERSITY OF DHAKA",
             "Rank": 3, "Teams": 300, "Solved": 6, "Problems": 11, "First Solves": 1, "Performance": 3500, "Rating": 2200},
            {"Handle": "alice", "Contest": "IUT 2026", "Date": "2026-07-25", "Team": "Team A", "Institution": "UNIVERSITY OF DHAKA",
             "Rank": None, "Teams": 110, "Solved": 0, "Problems": 12, "First Solves": 0, "Performance": None, "Rating": 2100},
        ]).to_csv(ratings / "history.csv", index=False)
        cache = root / "users.json"
        cache.write_text(json.dumps({"users": {"alice": {"handle": "Alice", "firstName": "Alice", "rank": "pupil", "rating": 1300, "maxRank": "expert", "maxRating": 1900}}}))
        out = website.build(root / "site", ratings, cache, ROOT / "rating_calculator/input/credits.json")
        page = (out / "u/alice.html").read_text()
        assert {p.name for p in out.iterdir()} >= {"index.html", "about.html", "assets", "u"}
        assert "&lt;script&gt;" in page and "<script>x" not in page
        assert "Codeforces max rating: <strong class=\"cf-blue\">1900</strong> <span class=muted>(Expert)</span>" in page and "Pupil" not in page
        assert '<span class="team-members" hidden><strong>Team A</strong>' in page and ">Alice</span>" in page
        assert '<a class="member" href="../u/alice.html">' in page  # members link to their profiles
        assert "×3" not in page and "unranked" in page
        # Rating and change are separate columns; the best rating (2200, at ICPC 2025) is highlighted.
        assert '<th class="num">Change</th>' in page and 'class="num nowrap best"><strong class="tier-5">2200</strong>' in page
        assert 'href="u/alice.html"' in (out / "index.html").read_text()


def test_cli_builds_the_site(capsys):
    from biscuit.cli import main

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        for folder in ["contestant_rating", "rating_calculator/input", "codeforces/data"]:
            source = ROOT / folder
            if source.exists():
                (root / folder).parent.mkdir(parents=True, exist_ok=True)
                import shutil
                shutil.copytree(source, root / folder, ignore=shutil.ignore_patterns("__pycache__"))
        main(["--root", str(root), "site"])
        assert (root / "website/output/index.html").exists()
    assert "Built the site" in capsys.readouterr().out


def test_complete_members_adds_null_rows_and_sorts():
    from biscuit.maintenance import complete_members

    winner = contest("MU 2025").teams[0]
    with tempfile.TemporaryDirectory() as directory:
        path = write_members(Path(directory) / "members.csv", [
            ["MU 2025", winner.institution, winner.name, "solo", "", ""],
        ])
        added = complete_members(path, CONTESTS, ROOT / "institution_finder/data/institutions.json")
        frame = pd.read_csv(path, dtype=str, keep_default_na=False)
        assert added == len(frame) - 1 > 100
        # The existing team keeps its handle; its empty cells and every new team's cells stay empty.
        row = frame[(frame.contest == "MU 2025") & (frame.team_name == winner.name)].iloc[0]
        assert [row.member1, row.member2, row.member3] == ["solo", "", ""]
        assert [m.handle for m in load_members(path)] == ["solo"]
        assert validate(path, CONTESTS) == []
        assert frame["institution"].tolist() == sorted(frame["institution"])
        assert complete_members(path, CONTESTS, ROOT / "institution_finder/data/institutions.json") == 0


def test_codeforces_cache_forgets_unlisted_handles(monkeypatch):
    monkeypatch.setattr(client, "_request", lambda handles: {"status": "OK", "result": [{"handle": h} for h in handles]})
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "users.json"
        client.update_cache(path, ["alice", "bob"], log=lambda message: None)
        cache, renamed = client.update_cache(path, ["alice"], log=lambda message: None)
        assert renamed == {}
        assert set(cache["users"]) == {"alice"}
        assert set(json.loads(path.read_text())["users"]) == {"alice"}


def test_renamed_handles_are_rewritten_everywhere_in_the_members_file():
    from members import rename_handles

    with tempfile.TemporaryDirectory() as directory:
        path = write_members(Path(directory) / "members.csv", [
            ["IUT 2026", "X", "A", "old_name", "VOLCABIT", ""],
            ["SUST 2026", "X", "B", "Old_Name", "other", ""],
        ])
        assert rename_handles(path, {"old_name": "NewName", "volcabit": "VolcaBit"}) == 3
        frame = pd.read_csv(path, dtype=str, keep_default_na=False)
        assert frame[["member1", "member2", "member3"]].values.tolist() == [["NewName", "VolcaBit", ""], ["NewName", "other", ""]]
        assert rename_handles(path, {}) == 0


def test_every_listed_handle_is_written_as_on_codeforces():
    from codeforces import current_handles, load_cache

    cache = load_cache(ROOT / "codeforces/data/users.json")
    handles = [m.handle for m in load_members(ROOT / "members/data/members.csv")]
    assert current_handles(cache, handles) == {}, "run `biscuit fetch-codeforces` to fix the spelling"


def test_form_responses_fill_free_cells_and_report_conflicts():
    from biscuit.maintenance import import_form_responses

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        members = root / "members.csv"
        pd.DataFrame([
            {"contest": "IUT 2026", "institution": "X", "team_name": "Open", "member1": "known", "member2": "", "member3": ""},
            {"contest": "SUST 2026", "institution": "X", "team_name": "Full", "member1": "a1", "member2": "a2", "member3": "a3"},
            {"contest": "IUT 2026", "institution": "X", "team_name": "Other", "member1": "taken", "member2": "", "member3": ""},
        ]).to_csv(members, index=False)
        teams = [
            {"contest": "IUT 2026", "team": "Open", "teammates": ["Known", "taken"]},
            {"contest": "SUST 2026", "team": "Full", "teammates": []},
            {"contest": "IUT 2026", "team": "Missing", "teammates": []},
        ]
        responses = root / "responses.csv"
        pd.DataFrame([
            {"Timestamp": "10/2/2026 09:00:00", "Name": "New", "Handle": "newbie", "Institution": "X", "Teams": json.dumps(teams)},
            {"Timestamp": "9/30/2026 18:00:00", "Name": "Old", "Handle": "newbie", "Institution": "X", "Teams": "[]"},
        ]).to_csv(responses, index=False)

        changes, problems = import_form_responses(members, [responses])
        assert changes == ["IUT 2026 Open: + newbie (from New (newbie))"]
        assert pd.read_csv(members, keep_default_na=False)["member2"].tolist()[0] == ""  # not written without apply
        assert any("taken is already in Other" in p for p in problems)
        assert any("Full in SUST 2026 is full" in p for p in problems)
        assert any("no team 'Missing'" in p for p in problems)

        import_form_responses(members, [responses], apply=True)
        written = pd.read_csv(members, keep_default_na=False)
        assert written.iloc[0][["member1", "member2", "member3"]].tolist() == ["known", "newbie", ""]
        assert list(written.columns) == ["contest", "institution", "team_name", "member1", "member2", "member3"]


def test_form_data_lists_each_institutions_teams_newest_contest_first():
    from website.form import form_data

    data = form_data(ROOT / "members/data/members.csv", ROOT / "parser/input/contests.json")
    names = [contest["name"] for contest in data["contests"]]
    assert names[0] == "IUT 2026" and names[-1] == "CUET 2024"
    iut = {team["name"]: team["members"] for team in data["contests"][0]["teams"]["ISLAMIC UNIVERSITY OF TECHNOLOGY"]}
    assert iut["IUT_HomeComing"] == ["flying_saucer", "greenbinjack", "sssatty"]
    assert all(contest["standings"].startswith("https://") for contest in data["contests"])


def test_institution_pages_are_built_from_institution_ratings():
    latest = pd.read_csv(ROOT / "rating_calculator/output/latest_ratings.csv", keep_default_na=False)
    top = latest.iloc[0]
    with tempfile.TemporaryDirectory() as directory:
        out = website.build(
            Path(directory) / "site", ROOT / "contestant_rating/output", ROOT / "codeforces/data/users.json",
            ROOT / "rating_calculator/input/credits.json",
            rating_directory=ROOT / "rating_calculator/output", score_directory=ROOT / "score_calculator/output",
            performances_path=ROOT / "performance_calculator/output/performances.csv", contests_directory=CONTESTS,
        )
        from website.institutions import institution_key

        page = (out / "i" / f"{institution_key(top['Institution'])}.html").read_text()
        listing = (out / "institutions.html").read_text()
        rankings = (out / "index.html").read_text()
        contest_page = (out / "i/islamic-university-of-technology/iut-2026.html").read_text()
        profile = (out / "u/rafio.html").read_text()
    # One page per institution and contest lists every team of the institution in it.
    iut_teams = [t.name for t in contest("IUT 2026").teams if t.institution.upper().startswith("ISLAMIC UNIVERSITY OF TECHNOLOGY")]
    assert iut_teams and all(f">{name}<" in contest_page for name in iut_teams)
    assert 'href="../i/islamic-university-of-technology/icpc-2024.html"' in profile
    assert f'<span class="rating-value tier-' in page and f">{top['Rating']}</span>" in page
    assert f'href="i/{institution_key(top["Institution"])}.html"' in listing
    # Institution names in the contestant rankings lead to the institution's page.
    assert 'href="i/islamic-university-of-technology.html"' in rankings
