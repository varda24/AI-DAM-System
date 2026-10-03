from zipfile import ZipFile

import pytest

from app.services.document_analyzer import _extract_document_content


@pytest.mark.parametrize(
    ("filename", "members", "expected"),
    [
        (
            "letter.docx",
            {"word/document.xml": "<w:document xmlns:w='urn:w'><w:t>Income Certificate</w:t></w:document>"},
            "Income Certificate",
        ),
        (
            "slides.pptx",
            {"ppt/slides/slide1.xml": "<p:sld xmlns:p='urn:p' xmlns:a='urn:a'><a:t>Project Demonstration</a:t></p:sld>"},
            "Project Demonstration",
        ),
        (
            "sheet.xlsx",
            {
                "xl/sharedStrings.xml": "<sst xmlns='urn:s'><si><t>Issue Date</t></si><si><t>01/02/2026</t></si></sst>",
                "xl/worksheets/sheet1.xml": "<worksheet xmlns='urn:s'><sheetData><row><c t='s'><v>0</v></c><c t='s'><v>1</v></c></row></sheetData></worksheet>",
            },
            "Issue Date\t01/02/2026",
        ),
    ],
)
def test_extracts_text_from_office_open_xml_files(tmp_path, filename, members, expected):
    path = tmp_path / filename
    with ZipFile(path, "w") as archive:
        for member, contents in members.items():
            archive.writestr(member, contents)

    text, page_count, ocr_used = _extract_document_content(path, None)

    assert expected in text
    assert page_count is None
    assert ocr_used is False


def test_legacy_office_format_reports_unsupported_extraction(tmp_path):
    path = tmp_path / "legacy.doc"
    path.write_bytes(b"not an OOXML document")

    with pytest.raises(ValueError, match="Legacy .doc files are not supported"):
        _extract_document_content(path, None)