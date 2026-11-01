import shutil
import tempfile
import zipfile
from pathlib import Path

import pandas as pd
import pytest

from institution_finder import InstitutionFinder
from slot_distributor import rename_registrations, run, unresolved_registrations
from slot_distributor.distributors import PrioritySlotDistributor, SlotDistributor
from slot_distributor.exporter import _build_slot_sheet
from slot_distributor.service import missed_contests


ROOT = Path(__file__).resolve().parents[1]
RATINGS = ROOT / "rating_calculator/output"


def create_real_inputs(inputs: Path) -> None:
    examples = ROOT / "slot_distributor/input/example"
    inputs.mkdir()
    shutil.copy2(examples / "registered.csv", inputs / "registered.csv")
    shutil.copy2(examples / "options.json", inputs / "options.json")


def test_slot_distributor_model_is_abstract():
    with pytest.raises(TypeError):
        SlotDistributor()


def test_slot_distributor_generates_workbook():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        inputs = root / "distribution-input"
        output = root / "distribution-output"
        create_real_inputs(inputs)
        workbook = run(inputs, RATINGS, output)
        slots = pd.read_csv(output / "slots.csv")
        assert slots.columns.tolist() == ["Institution", "Rating", "Slots"]
        registered = pd.read_csv(inputs / "registered.csv").set_index("Institution")["Max Slots"]
        assert (slots.set_index("Institution")["Slots"] <= registered.reindex(slots["Institution"]).values).all()
        assert (output / "waiting_list.csv").exists()
        with zipfile.ZipFile(workbook) as archive:
            assert "xl/workbook.xml" in archive.namelist()
            workbook_xml = archive.read("xl/workbook.xml").decode()
            assert "Read Me" in workbook_xml
            assert "Waiting List" in workbook_xml
            assert "Ratings" in workbook_xml
            blob = b"".join(archive.read(name) for name in archive.namelist())
            assert b"therealbcs" not in blob
            assert b"facebook" not in blob


def frame(rows: list[tuple]) -> pd.DataFrame:
    # rows: (institution, rating, registered slots, missed contests)
    return pd.DataFrame(rows, columns=["Institution", "Rating", "Registered Slots", "Missed Contests"])


def test_waiting_list_continues_priority_sequence_and_allows_repeats():
    ratings = frame([("A", 4000, 5, 0), ("B", 1000, 5, 0)])
    distributor = PrioritySlotDistributor(total_slots=2, waiting_list_size=4, min_unique=2)
    slots, waiting = distributor.distribute(ratings)
    assert dict(zip(slots["Institution"], slots["Slots"])) == {"A": 1, "B": 1}
    assert waiting["Institution"].tolist().count("A") > 1
    assert waiting["Position"].tolist() == [1, 2, 3, 4]


def test_min_unique_caps_guaranteed_first_slots():
    ratings = frame([("A", 600, 5, 0), ("B", 400, 5, 0), ("C", 100, 5, 0)])
    distributor = PrioritySlotDistributor(total_slots=4, waiting_list_size=5, min_unique=2)
    slots, waiting = distributor.distribute(ratings)
    # Only the top two institutions are guaranteed a slot; the remaining two
    # slots follow priority, so B's later slots outrank C's first slot.
    assert dict(zip(slots["Institution"], slots["Slots"])) == {"A": 2, "B": 2, "C": 0}
    # The slotless institution waits for its first slot ahead of everyone else.
    assert waiting.iloc[0]["Institution"] == "C"
    assert waiting.iloc[0]["Potential Slot Number"] == 1


def test_equal_priority_breaks_ties_toward_fewer_slots():
    ratings = frame([("A", 600, 5, 0), ("B", 400, 5, 0)])
    distributor = PrioritySlotDistributor(total_slots=4, waiting_list_size=0, min_unique=2)
    slots, _ = distributor.distribute(ratings)
    # 2nd slot of B (400/2 == 200) ties 3rd slot of A (600/3 == 200); B wins
    # because it holds fewer slots, so the fourth slot goes to B not A.
    assert dict(zip(slots["Institution"], slots["Slots"])) == {"A": 2, "B": 2}


def test_absence_bonus_adds_200_per_missed_contest_capped_at_5():
    ratings = frame([("A", 1000, 5, 0), ("B", 1000, 5, 2), ("N", pd.NA, 5, 9)])
    distributor = PrioritySlotDistributor(total_slots=3, waiting_list_size=0, min_unique=0)
    slots, _ = distributor.distribute(ratings)
    by_name = slots.set_index("Institution")
    assert by_name["Missed Contests"].to_dict() == {"A": 0, "B": 2, "N": 5}
    assert by_name["Absence Bonus"].to_dict() == {"A": 0, "B": 400, "N": 1000}
    # First slots: B 1400, A 1000, N 1000; second slots are 500 at best.
    assert by_name["Slots"].to_dict() == {"A": 1, "B": 1, "N": 1}


def test_absence_bonus_applies_to_first_slot_only():
    ratings = frame([("A", 1000, 5, 0), ("B", 900, 5, 5)])
    distributor = PrioritySlotDistributor(total_slots=3, waiting_list_size=2, min_unique=0)
    slots, waiting = distributor.distribute(ratings)
    # B's first slot (900 + 1000) comes first, but its second slot is only
    # 900 / 2 = 450, behind A's second slot (1000 / 2 = 500).
    assert dict(zip(slots["Institution"], slots["Slots"])) == {"A": 2, "B": 1}
    assert waiting["Priority"].tolist() == [450, 1000 / 3]


def test_never_rated_institution_is_not_special():
    ratings = frame([("A", 3000, 5, 0), ("N", pd.NA, 5, 5)])
    distributor = PrioritySlotDistributor(total_slots=3, waiting_list_size=0, min_unique=1)
    slots, _ = distributor.distribute(ratings)
    # A new institution's first slot has priority 0 + 1000. A's second slot
    # (3000 / 2) outranks it; A's third (3000 / 3) ties it, and N wins the tie
    # because it holds fewer slots.
    assert dict(zip(slots["Institution"], slots["Slots"])) == {"A": 2, "N": 1}


def test_registered_slots_cap_slots_and_waiting_list():
    ratings = frame([("A", 4000, 1, 0), ("B", 1000, 5, 0)])
    distributor = PrioritySlotDistributor(total_slots=3, waiting_list_size=5, min_unique=2)
    slots, waiting = distributor.distribute(ratings)
    assert dict(zip(slots["Institution"], slots["Slots"])) == {"A": 1, "B": 2}
    assert set(waiting["Institution"]) == {"B"}
    assert waiting["Potential Slot Number"].tolist() == [3, 4, 5]


def test_slot_sheet_sorts_by_total_and_starts_without_reserved_slots():
    slots = pd.DataFrame({
        "Institution": ["LOW", "HIGH", "NEW"],
        "Rating": [1000.0, 3000.0, float("nan")],
        "Missed Contests": [0, 0, 5],
        "Absence Bonus": [0, 0, 1000],
        "Registered Slots": [2, 3, 1],
        "Slots": [1, 3, 1],
    })
    sheet = _build_slot_sheet(slots)
    # Highest total first; rated 1-slot team outranks the unrated 1-slot team.
    assert sheet["Institution"].tolist() == ["HIGH", "LOW", "NEW"]
    assert sheet["Total Slots"].tolist() == [3, 1, 1]
    assert sheet["Reserved Slots"].tolist() == [0, 0, 0]
    assert sheet.set_index("Institution").loc["NEW", "General Slots"] == 1


def test_missed_contests_counts_latest_absence_streak():
    finder = InstitutionFinder(ROOT / "institution_finder/data/institutions.json")
    streaks, count = missed_contests(ROOT / "parser/output", finder)
    assert count == len(list((ROOT / "parser/output/contests").glob("*.json")))
    assert streaks["BANGLADESH UNIVERSITY OF ENGINEERING AND TECHNOLOGY"] == 0
    assert all(0 <= streak < count for streak in streaks.values())


def test_missing_institutions_generate_report_then_crash():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        inputs = root / "distribution-input"
        output = root / "distribution-output"
        create_real_inputs(inputs)
        with (inputs / "registered.csv").open("a") as file:
            file.write("UNIVERSITY OF DHAKAA,2\nMISSING UNIVERSITY,1\n")
        with pytest.raises(ValueError, match="missing.csv"):
            run(inputs, RATINGS, output)
        assert not (output / "slots.xlsx").exists()
        report = pd.read_csv(output / "missing.csv")
        assert report.columns.tolist() == [
            "Missing Institution",
            "Best Possible Match",
            "Probability",
        ]
        assert report["Missing Institution"].tolist() == [
            "MISSING UNIVERSITY",
            "UNIVERSITY OF DHAKAA",
        ]
        assert report.loc[1, "Best Possible Match"] == "UNIVERSITY OF DHAKA"
        assert report["Probability"].between(0, 100).all()


def test_institution_alias_resolves_before_missing_report():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        inputs = root / "distribution-input"
        output = root / "distribution-output"
        create_real_inputs(inputs)
        (inputs / "registered.csv").write_text(
            "Institution,Max Slots\nBANGLADESH UNIVERSITY OF ENGINEERING & TECHNOLOGY,2\n"
        )
        workbook = run(inputs, RATINGS, output)
        assert workbook.exists()


def test_example_input_directory_is_rejected():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        with pytest.raises(ValueError, match="Example inputs cannot be used"):
            run(
                ROOT / "slot_distributor/input/example",
                root / "ratings",
                root / "output",
            )
        assert not (root / "output").exists()


def test_missing_real_inputs_are_rejected():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        inputs = root / "distribution-input"
        inputs.mkdir()
        with pytest.raises(FileNotFoundError, match="registered.csv, options.json"):
            run(inputs, root / "ratings", root / "output")
        assert not (root / "output").exists()


def test_empty_registered_list_is_rejected():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        inputs = root / "distribution-input"
        create_real_inputs(inputs)
        (inputs / "registered.csv").write_text("Institution,Max Slots\n")
        with pytest.raises(ValueError, match="does not contain any institutions"):
            run(inputs, root / "ratings", root / "output")
        assert not (root / "output").exists()


def test_duplicate_and_invalid_registrations_are_rejected():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        inputs = root / "distribution-input"
        create_real_inputs(inputs)
        (inputs / "registered.csv").write_text(
            "Institution,Max Slots\n"
            "BANGLADESH UNIVERSITY OF ENGINEERING AND TECHNOLOGY,2\n"
            "BANGLADESH UNIVERSITY OF ENGINEERING & TECHNOLOGY,1\n"
        )
        with pytest.raises(ValueError, match="registered more than once"):
            run(inputs, RATINGS, root / "output")
        (inputs / "registered.csv").write_text("Institution,Max Slots\nUNIVERSITY OF DHAKA,0\n")
        with pytest.raises(ValueError, match="positive integer"):
            run(inputs, RATINGS, root / "output")


def test_registration_helpers_find_and_rename_unknown_names():
    with tempfile.TemporaryDirectory() as directory:
        registered = Path(directory) / "registered.csv"
        registered.write_text('Institution,Max Slots\nUNIVERSITY OF DHAKAA,2\n"BRAC UNIVERSITY",1\n')
        database = ROOT / "institution_finder/data/institutions.json"
        assert unresolved_registrations(registered, database) == ["UNIVERSITY OF DHAKAA"]
        rename_registrations(registered, {"UNIVERSITY OF DHAKAA": "UNIVERSITY OF DHAKA"})
        assert unresolved_registrations(registered, database) == []
        assert pd.read_csv(registered)["Max Slots"].tolist() == [2, 1]
