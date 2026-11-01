from pathlib import Path

import pandas as pd


def _column_letter(number: int) -> str:
    result = ""
    while number >= 0:
        result = chr(number % 26 + ord("A")) + result
        number = number // 26 - 1
    return result


def _format_sheet(workbook, worksheet, frame: pd.DataFrame) -> None:
    header = workbook.add_format({"bg_color": "#535FC1", "font_color": "white"})
    worksheet.set_row(0, None, header)
    if not frame.empty:
        cell_range = f"A2:{_column_letter(len(frame.columns) - 1)}{len(frame) + 1}"
        for formula, color in [("=ISEVEN(ROW())", "#C9DAF8"), ("=ISODD(ROW())", "#FFFFFF")]:
            worksheet.conditional_format(cell_range, {
                "type": "formula",
                "criteria": formula,
                "format": workbook.add_format({"bg_color": color}),
            })
    for index, column in enumerate(frame.columns):
        value_width = frame[column].map(lambda value: len(str(value))).max() if not frame.empty else 0
        worksheet.set_column(index, index, max(value_width, len(column)) + 2)


def _build_slot_sheet(slots: pd.DataFrame) -> pd.DataFrame:
    sheet = slots.rename(columns={"Slots": "General Slots"}).copy()
    # Reserved slots are added by hand by the organizers after distribution.
    sheet["Reserved Slots"] = 0
    sheet["Explanation for Reserved Slots"] = ""
    sheet["Total Slots"] = sheet["General Slots"] + sheet["Reserved Slots"]
    sheet = sheet.sort_values(
        by=["Total Slots", "Rating"],
        ascending=[False, False],
        na_position="last",
        kind="stable",
    ).reset_index(drop=True)
    return sheet[[
        "Institution",
        "Rating",
        "General Slots",
        "Reserved Slots",
        "Total Slots",
        "Explanation for Reserved Slots",
    ]]


def _write_readme(workbook, worksheet) -> None:
    title = workbook.add_format({"bold": True, "font_size": 16, "font_color": "#535FC1"})
    header = workbook.add_format({"bold": True, "font_size": 12, "font_color": "#535FC1"})
    body = workbook.add_format({"valign": "top"})

    worksheet.hide_gridlines(2)
    worksheet.set_column(0, 0, 100)

    content = [
        ("title", "Slot Distribution"),
        ("blank",),
        ("body", "These slots were distributed automatically using a priority-based algorithm."),
        ("body", "Each slot goes to the institution with the highest priority for its next slot."),
        ("body", "First slot: priority = rating + absence bonus."),
        ("body", "Later slots: priority = rating / slot number."),
        ("blank",),
        ("header", "What each tab means"),
        ("item", "Slots — the slots each registered institution receives. This is the main result."),
        ("item", "Waiting List — the ordered queue used when more slots become available."),
        ("item", "Ratings — the institution ratings used as input to the algorithm."),
        ("blank",),
        ("header", "Columns in the Slots tab"),
        ("item", "Institution — the registered institution."),
        ("item", "Rating — current rating; blank for institutions that were never rated."),
        ("item", "General Slots — slots earned through the algorithm."),
        ("item", "Reserved Slots — extra slots added manually by the organizers."),
        ("item", "Total Slots — General Slots + Reserved Slots; updates automatically."),
        ("item", "Explanation for Reserved Slots — the reason for any reserved slots."),
        ("blank",),
        ("header", "Adding reserved slots (organizers)"),
        ("body", "Increase the institution's Reserved Slots value and write the reason in the"),
        ("body", "Explanation for Reserved Slots cell. Total Slots then updates on its own."),
        ("blank",),
        ("header", "Unused slots and the waiting list (organizers)"),
        ("body", "If an institution does not use all of its slots, the freed slots go to the next"),
        ("body", "available position in the Waiting List, starting at Position 1 and going down."),
        ("body", "Each entry shows the institution and the slot number it would receive next."),
    ]

    for row, item in enumerate(content):
        kind = item[0]
        if kind == "title":
            worksheet.write(row, 0, item[1], title)
        elif kind == "header":
            worksheet.write(row, 0, item[1], header)
        elif kind == "item":
            worksheet.write(row, 0, f"•  {item[1]}", body)
        elif kind == "body":
            worksheet.write(row, 0, item[1], body)

    worksheet.protect()


def generate_excel(
    ratings: pd.DataFrame,
    slots: pd.DataFrame,
    waiting_list: pd.DataFrame,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    slot_sheet = _build_slot_sheet(slots)

    with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
        workbook = writer.book
        _write_readme(workbook, workbook.add_worksheet("Read Me"))
        for name, frame in [
            ("Slots", slot_sheet),
            ("Waiting List", waiting_list),
            ("Ratings", ratings),
        ]:
            frame.to_excel(writer, sheet_name=name, index=False, header=False, startrow=1)
            worksheet = writer.sheets[name]
            for column, heading in enumerate(frame.columns):
                worksheet.write(0, column, heading)
            _format_sheet(workbook, worksheet, frame)
            worksheet.protect()

        worksheet = writer.sheets["Slots"]
        general = slot_sheet.columns.get_loc("General Slots")
        reserved = slot_sheet.columns.get_loc("Reserved Slots")
        total = slot_sheet.columns.get_loc("Total Slots")
        explanation = slot_sheet.columns.get_loc("Explanation for Reserved Slots")
        unlocked = workbook.add_format({"locked": False})
        for row in range(len(slot_sheet)):
            excel_row = row + 2
            worksheet.write_formula(
                row + 1,
                total,
                f"={_column_letter(general)}{excel_row}+{_column_letter(reserved)}{excel_row}",
            )
            worksheet.write(row + 1, reserved, slot_sheet.iloc[row, reserved], unlocked)
            worksheet.write(row + 1, explanation, slot_sheet.iloc[row, explanation], unlocked)
