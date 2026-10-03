import re
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree

from PIL import Image
import fitz
import pytesseract
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.document_analysis import DocumentAnalysis
from app.core.config import settings


DOCUMENT_KEYWORDS = {
    "AADHAAR": [
        "aadhaar",
        "aadhar",
        "unique identification",
        "uidai",
    ],
    "PAN": ["permanent account number", "income tax department", "pan card"],
    "CASTE_CERTIFICATE": ["caste certificate", "scheduled caste", "scheduled tribe", "other backward class"],
    "DOMICILE_CERTIFICATE": ["domicile certificate", "residence certificate", "permanent resident"],
    "BIRTH_CERTIFICATE": ["birth certificate", "date of birth", "registrar of births"],
    "INCOME_CERTIFICATE": [
        "income certificate",
        "annual income",
        "income",
        "revenue department",
    ],
    "MARKSHEET": [
        "marksheet",
        "mark sheet",
        "statement of marks",
        "marks obtained",
        "percentage",
        "grade",
        "semester",
    ],
    "COLLEGE_DOCUMENT": [
        "college",
        "university",
        "student",
        "enrollment",
        "roll number",
        "admission",
        "semester",
        "degree",
        "bachelor",
        "engineering",
    ],
    "DEGREE_CERTIFICATE": ["degree certificate", "bachelor of", "master of", "conferred upon"],
    "DRIVING_LICENSE": ["driving licence", "driving license", "transport department", "licence no"],
    "PASSPORT": ["passport", "nationality", "place of birth", "passport no"],
    "INSURANCE": ["insurance", "policy number", "sum insured", "premium"],
    "MEDICAL_DOCUMENT": ["medical", "hospital", "diagnosis", "prescription", "patient"],
    "BANK_DOCUMENT": ["bank", "account number", "ifsc", "statement of account"],
    "GOVERNMENT_DOCUMENT": [
        "government of india",
        "govt. of india",
        "government",
        "district",
        "tehsil",
        "taluka",
        "revenue department",
    ],
    "BILL": [
        "bill",
        "invoice",
        "invoice number",
        "total amount",
        "subtotal",
        "tax",
        "gst",
    ],
    "RECEIPT": [
        "receipt",
        "receipt number",
        "paid",
        "payment received",
        "amount received",
    ],
}


DATE_PATTERNS = [
    r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b",
    r"\b(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})\b",
    r"\b([A-Za-z]{3,9}\s+\d{1,2},\s+\d{4})\b",
]

ISSUE_DATE_LABELS = (
    "issue date", "date of issue", "issued on", "issued date",
    "valid from", "validity from",
)
EXPIRY_DATE_LABELS = (
    "expiry date", "expiration date", "date of expiry", "valid until",
    "valid till", "expires on", "expiry", "expiration",
)
DOCUMENT_DATE_LABELS = ("document date", "date", "dated on")


def _tesseract_command() -> str | None:
    configured = settings.TESSERACT_CMD
    candidates = [configured] if configured else []
    candidates.extend([
        shutil.which("tesseract"),
        r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe",
    ])
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(Path(candidate))
    return None


def ocr_diagnostics() -> dict[str, str | bool | None]:
    command = _tesseract_command()
    return {
        "available": command is not None,
        "command": command,
        "message": None if command else (
            "Tesseract is unavailable. Set TESSERACT_CMD or install Tesseract on PATH."
        ),
    }


def _configure_tesseract() -> None:
    command = _tesseract_command()
    if command is None:
        raise RuntimeError(ocr_diagnostics()["message"])
    pytesseract.pytesseract.tesseract_cmd = command


def _normalise_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _parse_date(value: str) -> datetime | None:
    formats = [
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d/%m/%y",
        "%d-%m-%y",
        "%d %B %Y",
        "%d %b %Y",
        "%B %d, %Y",
        "%b %d, %Y",
    ]

    for date_format in formats:
        try:
            parsed = datetime.strptime(value, date_format)
            return parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    return None


def _extract_dates(text: str) -> list[datetime]:
    dates: list[datetime] = []

    for pattern in DATE_PATTERNS:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            parsed = _parse_date(match.group(1))
            if parsed:
                dates.append(parsed)

    unique: dict[str, datetime] = {}

    for value in dates:
        unique[value.isoformat()] = value

    return sorted(unique.values())


def _extract_labeled_date(
    text: str,
    labels: tuple[str, ...],
) -> tuple[datetime | None, str | None, float]:
    for label in labels:
        label_pattern = re.escape(label).replace(r"\ ", r"\s+")
        match = re.search(
            rf"\b{label_pattern}\b\s*[:\-]?\s*(.{{0,48}})",
            text,
            flags=re.IGNORECASE,
        )
        if not match:
            continue
        nearby = match.group(1)
        for pattern in DATE_PATTERNS:
            date_match = re.search(pattern, nearby, flags=re.IGNORECASE)
            if date_match:
                parsed = _parse_date(date_match.group(1))
                if parsed:
                    source = f"{text[match.start():match.start() + len(label) + date_match.end(1) + 4]}".strip()
                    return parsed, source[:255], 0.95
    return None, None, 0.0


def _extract_label_value(text: str, labels: list[str]) -> str | None:
    for label in labels:
        pattern = rf"{re.escape(label)}\s*[:\-]\s*([^\n\r]+)"
        match = re.search(pattern, text, flags=re.IGNORECASE)

        if match:
            value = match.group(1).strip()
            value = re.sub(r"\s+", " ", value)

            if value:
                return value[:255]

    return None


def _classify_document(text: str, filename: str) -> tuple[str, float]:
    searchable = f"{filename} {text}".lower()

    scores: dict[str, int] = {}

    for document_type, keywords in DOCUMENT_KEYWORDS.items():
        score = 0

        for keyword in keywords:
            if keyword.lower() in searchable:
                score += 1

        if score:
            scores[document_type] = score

    if not scores:
        return "OTHER", 0.0

    document_type = max(scores, key=scores.get)
    score = scores[document_type]

    keyword_count = len(DOCUMENT_KEYWORDS[document_type])
    confidence = min(score / max(keyword_count * 0.45, 1), 1.0)

    return document_type, round(confidence, 3)


def _extract_pdf_text(path: Path) -> tuple[str, int, bool]:
    document = fitz.open(path)

    text_parts: list[str] = []

    for page in document:
        text_parts.append(page.get_text("text"))

    text = "\n".join(text_parts).strip()

    return text, len(document), False


def _ocr_image(path: Path) -> str:
    _configure_tesseract()
    image = Image.open(path)

    try:
        return pytesseract.image_to_string(image)
    finally:
        image.close()


def _ocr_pdf(path: Path) -> tuple[str, int]:
    _configure_tesseract()
    document = fitz.open(path)
    page_count = len(document)

    text_parts: list[str] = []

    try:
        for page in document:
            pixmap = page.get_pixmap(
                matrix=fitz.Matrix(1.5, 1.5),
                alpha=False,
            )

            image = Image.frombytes(
                "RGB",
                [pixmap.width, pixmap.height],
                pixmap.samples,
            )

            try:
                text_parts.append(pytesseract.image_to_string(image))
            finally:
                image.close()
    finally:
        document.close()

    return "\n".join(text_parts).strip(), page_count


def _extract_ooxml_text(path: Path, extension: str) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if extension == ".docx":
                xml_files = ["word/document.xml"]
            elif extension == ".pptx":
                xml_files = sorted(
                    (name for name in names if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)),
                    key=lambda name: int(re.search(r"slide(\d+)", name).group(1)),
                )
            else:
                shared: list[str] = []
                if "xl/sharedStrings.xml" in names:
                    root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
                    shared = [
                        "".join(node.text or "" for node in item.iter() if node.tag.endswith("}t"))
                        for item in root
                    ]
                sheets = sorted(name for name in names if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name))
                lines = []
                for sheet in sheets:
                    root = ElementTree.fromstring(archive.read(sheet))
                    for row in (node for node in root.iter() if node.tag.endswith("}row")):
                        values = []
                        for cell in (node for node in row if node.tag.endswith("}c")):
                            value = next((node.text or "" for node in cell if node.tag.endswith("}v")), "")
                            if cell.attrib.get("t") == "s" and value:
                                value = shared[int(value)]
                            elif cell.attrib.get("t") == "inlineStr":
                                value = "".join(node.text or "" for node in cell.iter() if node.tag.endswith("}t"))
                            values.append(value)
                        lines.append("\t".join(values))
                return "\n".join(lines)

            parts = []
            for xml_file in xml_files:
                if xml_file not in names:
                    continue
                root = ElementTree.fromstring(archive.read(xml_file))
                parts.append(" ".join(
                    node.text or ""
                    for node in root.iter()
                    if node.tag.endswith("}t") and node.text
                ))
            return "\n".join(parts)
    except (zipfile.BadZipFile, ElementTree.ParseError, KeyError, IndexError, ValueError) as exc:
        raise ValueError(f"Could not extract text from {extension} document: {exc}") from exc


def _extract_rtf_text(path: Path) -> str:
    raw_text = path.read_text(encoding="utf-8", errors="replace")
    raw_text = re.sub(
        r"\\'([0-9a-fA-F]{2})",
        lambda match: bytes.fromhex(match.group(1)).decode("cp1252", errors="replace"),
        raw_text,
    )
    raw_text = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", raw_text)
    return re.sub(r"[{}]", "", raw_text)


def _extract_document_content(
    path: Path,
    mime_type: str | None,
) -> tuple[str, int | None, bool]:
    extension = path.suffix.lower()

    if extension == ".pdf" or mime_type == "application/pdf":
        text, page_count, _ = _extract_pdf_text(path)

        if len(_normalise_text(text)) >= 30:
            return text, page_count, False

        ocr_text, ocr_page_count = _ocr_pdf(path)
        return ocr_text, ocr_page_count, True

    if extension in {".txt", ".csv", ".rtf"} or (mime_type and mime_type.startswith("text/")):
        text = _extract_rtf_text(path) if extension == ".rtf" else path.read_text(encoding="utf-8", errors="replace")
        return text, None, False

    if extension in {".docx", ".xlsx", ".pptx"}:
        return _extract_ooxml_text(path, extension), None, False

    if mime_type and mime_type.startswith("image/"):
        return _ocr_image(path), None, True

    if extension in {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}:
        return _ocr_image(path), None, True

    if extension in {".doc", ".xls", ".ppt"}:
        raise ValueError(
            f"Legacy {extension} files are not supported for text extraction. "
            "Save the file as its .docx, .xlsx, or .pptx equivalent and rescan."
        )

    raise ValueError(f"Unsupported document format: {extension or mime_type or 'unknown'}")


def analyze_document(
    db: Session,
    asset_id: int,
    force: bool = False,
) -> DocumentAnalysis:
    asset = db.query(Asset).filter(Asset.id == asset_id).first()

    if asset is None:
        raise ValueError(f"Asset {asset_id} was not found.")

    if asset.is_missing:
        raise FileNotFoundError(
            f"Asset file is missing: {asset.path}"
        )

    path = Path(asset.path)

    if not path.exists() or not path.is_file():
        asset.is_missing = True
        db.commit()

        raise FileNotFoundError(
            f"Asset file is missing: {asset.path}"
        )

    existing = (
        db.query(DocumentAnalysis)
        .filter(DocumentAnalysis.asset_id == asset_id)
        .first()
    )

    if existing and not force:
        return existing

    if existing is None:
        analysis = DocumentAnalysis(asset_id=asset_id)
        db.add(analysis)
    else:
        analysis = existing

    analysis.status = "PROCESSING"
    analysis.error_message = None
    db.commit()

    try:
        text, page_count, ocr_used = _extract_document_content(
            path=path,
            mime_type=asset.mime_type,
        )

        normalised_text = _normalise_text(text)

        document_type, confidence = _classify_document(
            text=normalised_text,
            filename=asset.name,
        )

        issue_date, issue_date_source, _ = _extract_labeled_date(
            normalised_text, ISSUE_DATE_LABELS
        )
        expiry_date, expiry_date_source, expiry_confidence = _extract_labeled_date(
            normalised_text, EXPIRY_DATE_LABELS
        )
        document_date, _, _ = _extract_labeled_date(
            normalised_text, DOCUMENT_DATE_LABELS
        )

        now = datetime.now(timezone.utc)

        if expiry_date is None:
            document_status = "UNKNOWN"
        elif expiry_date < now:
            document_status = "EXPIRED"
        else:
            days_remaining = (
                expiry_date - now
            ).total_seconds() / 86400

            if days_remaining <= 30:
                document_status = "EXPIRING_SOON"
            else:
                document_status = "VALID"

        extracted_name = _extract_label_value(
            normalised_text,
            [
                "Name",
                "Name of Applicant",
                "Student Name",
                "Candidate Name",
                "Customer Name",
            ],
        )
        issuing_organization = _extract_label_value(
            normalised_text,
            ["Issuing Authority", "Issued By", "Organization", "Department"],
        )

        analysis.document_type = document_type
        analysis.confidence = confidence
        analysis.extracted_text = normalised_text[:100000]
        analysis.extracted_name = extracted_name
        analysis.issue_date = issue_date
        analysis.document_date = document_date
        analysis.expiry_date = expiry_date
        analysis.issue_date_source = issue_date_source
        analysis.expiry_date_source = expiry_date_source
        analysis.expiry_confidence = expiry_confidence or None
        analysis.issuing_organization = issuing_organization
        analysis.document_status = document_status
        analysis.ocr_used = ocr_used
        analysis.page_count = page_count
        analysis.status = "ANALYZED"
        analysis.error_message = None
        analysis.analyzed_at = now

        db.commit()
        db.refresh(analysis)

        return analysis

    except Exception as exc:
        analysis.status = "ERROR"
        analysis.error_message = str(exc)[:4000]
        analysis.analyzed_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(analysis)

        raise
