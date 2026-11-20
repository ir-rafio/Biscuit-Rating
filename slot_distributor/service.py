import json
from pathlib import Path

import pandas as pd

from contests import load_contests
from institution_finder import InstitutionFinder

from .distributors import create
from .exporter import generate_excel

REGISTRATION_COLUMNS = ["Institution", "Max Slots"]


def load_registrations(registered_path: Path) -> pd.DataFrame:
    registrations = pd.read_csv(registered_path, dtype={"Institution": str}, skipinitialspace=True)
    registrations.columns = [str(column).strip() for column in registrations.columns]
    if registrations.columns.tolist() != REGISTRATION_COLUMNS:
        raise ValueError(f"{registered_path.name} must have exactly the columns: {', '.join(REGISTRATION_COLUMNS)}.")
    registrations["Institution"] = registrations["Institution"].fillna("").str.strip()
    registrations = registrations[registrations["Institution"] != ""].reset_index(drop=True)
    if registrations.empty:
        raise ValueError(f"{registered_path.name} does not contain any institutions.")
    max_slots = pd.to_numeric(registrations["Max Slots"], errors="coerce")
    invalid = registrations.loc[max_slots.isna() | (max_slots < 1) | (max_slots % 1 != 0), "Institution"]
    if not invalid.empty:
        raise ValueError(f"Max Slots must be a positive integer for: {', '.join(invalid)}.")
    registrations["Max Slots"] = max_slots.astype(int)
    return registrations


def unresolved_registrations(registered_path: Path, institution_database: Path) -> list[str]:
    finder = InstitutionFinder(institution_database)
    names = load_registrations(registered_path)["Institution"]
    return sorted({name for name in names if finder.resolve(name) is None})


def rename_registrations(registered_path: Path, renames: dict[str, str]) -> None:
    """Replace registered institution names, for example to fix typos."""
    raw = pd.read_csv(registered_path, dtype=str, keep_default_na=False)
    raw["Institution"] = raw["Institution"].map(lambda name: renames.get(name.strip(), name))
    raw.to_csv(registered_path, index=False)


def missed_contests(contests_directory: Path, finder: InstitutionFinder) -> tuple[dict[str, int], int]:
    """Count, per institution, how many of the latest contests in a row it missed.

    Returns the streak of every institution that took part in at least one
    contest, plus the number of contests (the streak of everyone else).
    """
    contests = load_contests(contests_directory)
    streaks = {}
    for missed, contest in enumerate(reversed(contests)):
        for team in contest.teams:
            institution = finder.resolve(team.institution)
            if institution is not None:
                streaks.setdefault(institution, missed)
    return streaks, len(contests)


def run(
    input_directory: Path,
    ratings_directory: Path,
    output_directory: Path,
    institution_database: Path = Path("institution_finder/data/institutions.json"),
    contests_directory: Path = Path("parser/output"),
) -> Path:
    if input_directory.name.lower() == "example":
        raise ValueError("Example inputs cannot be used for slot distribution.")
    registered_path = input_directory / "registered.csv"
    options_path = input_directory / "options.json"
    missing_inputs = [path.name for path in (registered_path, options_path) if not path.is_file()]
    if missing_inputs:
        raise FileNotFoundError(f"Missing slot distributor input files: {', '.join(missing_inputs)}.")
    registrations = load_registrations(registered_path)
    with options_path.open() as file:
        options = json.load(file)

    output_directory.mkdir(parents=True, exist_ok=True)
    output_path = output_directory / "slots.xlsx"
    missing_path = output_directory / "missing.csv"
    for path in (output_path, missing_path, output_directory / "slots.csv", output_directory / "waiting_list.csv"):
        path.unlink(missing_ok=True)

    finder = InstitutionFinder(institution_database)
    missing = sorted({name for name in registrations["Institution"] if finder.resolve(name) is None})
    if missing:
        pd.DataFrame(
            [(name.upper(), *finder.best_match(name)) for name in missing],
            columns=["Missing Institution", "Best Possible Match", "Probability"],
        ).to_csv(missing_path, index=False)
        raise ValueError(f"Registered institutions were not found. See {missing_path}.")
    registrations["Institution"] = registrations["Institution"].map(finder.resolve)
    duplicated = registrations.loc[registrations["Institution"].duplicated(), "Institution"]
    if not duplicated.empty:
        raise ValueError(f"Institutions registered more than once: {', '.join(sorted(set(duplicated)))}.")

    ratings = pd.read_csv(ratings_directory / "latest_ratings.csv")
    rating_of = dict(zip(ratings["Institution"], ratings["Rating"]))
    streaks, contest_count = missed_contests(contests_directory, finder)
    considered = pd.DataFrame({
        "Institution": registrations["Institution"],
        "Rating": [rating_of.get(name, float("nan")) for name in registrations["Institution"]],
        "Registered Slots": registrations["Max Slots"],
        "Missed Contests": [streaks.get(name, contest_count) for name in registrations["Institution"]],
    }).sort_values(["Rating", "Institution"], ascending=[False, True], na_position="last", ignore_index=True)

    distributor = create(options["distributor"], options["parameters"])
    slots, waiting_list = distributor.distribute(considered)
    generate_excel(considered[["Institution", "Rating"]], slots, waiting_list, output_path)
    # Plain copies for tools that cannot read the workbook.
    slots[["Institution", "Rating", "Slots"]].to_csv(output_directory / "slots.csv", index=False)
    waiting_list.to_csv(output_directory / "waiting_list.csv", index=False)
    return output_path
