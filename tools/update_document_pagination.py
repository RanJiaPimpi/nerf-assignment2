from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.oxml.ns import qn


ROOT = Path(__file__).resolve().parents[1]
DOCUMENT = ROOT / "docs" / "Assignment_2_NeRF_Pipeline_Documentation.docx"


def contains_page_break(paragraph) -> bool:
    return any(
        element.get(qn("w:type")) == "page"
        for element in paragraph._p.xpath(".//w:br")
    )


def next_nonempty_paragraph(paragraphs, start_index: int):
    for paragraph in paragraphs[start_index + 1 :]:
        if paragraph.text.strip():
            return paragraph
    return None


def remove_chapter_page_breaks(document: Document) -> int:
    paragraphs = list(document.paragraphs)
    removed = 0
    for index, paragraph in enumerate(paragraphs):
        if not contains_page_break(paragraph):
            continue
        following = next_nonempty_paragraph(paragraphs, index)
        if following is None:
            continue
        is_main_heading = following.style.name == "Heading 1"
        is_front_matter = following.text.strip() in {"目录", "摘要"}
        if is_main_heading and not is_front_matter:
            paragraph._element.getparent().remove(paragraph._element)
            removed += 1
    return removed


def main() -> None:
    document = Document(DOCUMENT)
    removed = remove_chapter_page_breaks(document)
    temporary = DOCUMENT.with_suffix(".pagination.tmp.docx")
    document.save(temporary)
    temporary.replace(DOCUMENT)
    print(f"Removed {removed} chapter page break(s): {DOCUMENT}")


if __name__ == "__main__":
    main()
