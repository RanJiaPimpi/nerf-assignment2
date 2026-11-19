from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from docx import Document


ROOT = Path(__file__).resolve().parents[1]
DOCUMENT = ROOT / "docs" / "Assignment_2_NeRF_Pipeline_Documentation.docx"
CONTRIBUTION = "[例如 实验评估、指标汇总与失败案例分析]"
REPOSITORY_URL = "https://github.com/RanJiaPimpi/nerf-assignment2"
REPOSITORY_PLACEHOLDER = "https://github.com/your-group/nerf-3d-reconstruction"


def find_contribution_table(document: Document):
    for table in document.tables:
        if len(table.columns) != 3 or not table.rows:
            continue
        header = [cell.text.strip() for cell in table.rows[0].cells]
        if header == ["成员", "学号", "主要贡献"]:
            return table
    raise RuntimeError("Could not find the group contribution table")


def main() -> None:
    document = Document(DOCUMENT)
    table = find_contribution_table(document)
    if not any(CONTRIBUTION in cell.text for row in table.rows for cell in row.cells):
        new_row = deepcopy(table.rows[-1]._tr)
        table._tbl.append(new_row)
        cells = table.rows[-1].cells
        values = ["[成员4姓名]", "[学号]", CONTRIBUTION]
        for cell, value in zip(cells, values):
            cell.text = value

    for current_table in document.tables:
        for row in current_table.rows:
            for cell in row.cells:
                if cell.text.strip() == REPOSITORY_PLACEHOLDER:
                    cell.text = REPOSITORY_URL

    temporary = DOCUMENT.with_suffix(".contribution.tmp.docx")
    document.save(temporary)
    try:
        temporary.replace(DOCUMENT)
        print(f"Updated contribution and repository link: {DOCUMENT}")
    except PermissionError:
        print(f"Document is open; prepared replacement: {temporary}")


if __name__ == "__main__":
    main()
