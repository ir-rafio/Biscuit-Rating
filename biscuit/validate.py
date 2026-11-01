import json
from collections import Counter
from datetime import date
from pathlib import Path

import institution_finder
import members
from parser import get_parser


def validate(root: Path) -> list[str]:
    """Return every inconsistency in the hand-maintained data files."""
    return [
        *_validate_contests(root),
        *institution_finder.validate(root / "institution_finder/data/institutions.json"),
        *members.validate(root / "members/data/members.csv", root / "parser/output"),
    ]


def _validate_contests(root: Path) -> list[str]:
    errors = []
    contests = json.loads((root / "parser/input/contests.json").read_text())["contests"]
    credits = json.loads((root / "rating_calculator/input/credits.json").read_text())
    names = [contest["name"] for contest in contests]
    errors += [
        f"Contest listed {count} times in contests.json: {name}"
        for name, count in Counter(name.upper() for name in names).items()
        if count > 1
    ]
    source_directory = root / "parser/input/contest_files"
    referenced = set()
    for contest in contests:
        name = contest["name"]
        if name != name.upper():
            errors.append(f"Contest name must be uppercase: {name}")
        try:
            date.fromisoformat(contest["date"])
        except (TypeError, ValueError):
            errors.append(f"Contest {name} has an invalid date: {contest.get('date')}")
        try:
            get_parser(contest["parser"])
        except ValueError as error:
            errors.append(f"Contest {name}: {error}")
        if not contest.get("filenames"):
            errors.append(f"Contest {name} has no standings files.")
        if contest.get("standings") and not contest["standings"].startswith("https://"):
            errors.append(f"Contest {name} has a standings link that is not an https:// address: {contest['standings']}")
        for filename in contest.get("filenames", []):
            referenced.add(filename)
            if not (source_directory / filename).is_file():
                errors.append(f"Contest {name} references a missing file: {filename}")
        if name not in credits:
            errors.append(f"Contest {name} has no credit in credits.json.")
    for name, credit in credits.items():
        if name not in names:
            errors.append(f"credits.json has a credit for an unknown contest: {name}")
        if not isinstance(credit, (int, float)) or credit < 0:
            errors.append(f"Contest {name} must have a non-negative credit, not {credit!r}.")
    errors += [
        f"Standings file is not used by any contest: {path.name}"
        for path in sorted(source_directory.glob("*.html"))
        if path.name not in referenced
    ]
    return errors
