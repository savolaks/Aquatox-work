# aquatox/excel_utils.py
from __future__ import annotations

from pathlib import Path
from typing import Dict, Sequence, Union

try:
    import openpyxl
except ImportError:  # pragma: no cover - optional dependency
    openpyxl = None

CellValue = Union[str, float, int, None]


def write_excel_xml(path: str, sheets: Dict[str, Sequence[Sequence[CellValue]]]) -> None:
    workbook = [
        '<?xml version="1.0"?>',
        '<?mso-application progid="Excel.Sheet"?>',
        '<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"',
        ' xmlns:o="urn:schemas-microsoft-com:office:office"',
        ' xmlns:x="urn:schemas-microsoft-com:office:excel"',
        ' xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"',
        ' xmlns:html="http://www.w3.org/TR/REC-html40">',
    ]

    for sheet_name, rows in sheets.items():
        safe_name = _xml_escape(sheet_name)[:31]
        workbook.append(f'<Worksheet ss:Name="{safe_name}">')
        workbook.append("<Table>")
        for row in rows:
            workbook.append("<Row>")
            for value in row:
                workbook.append(_cell_xml(value))
            workbook.append("</Row>")
        workbook.append("</Table>")
        workbook.append("</Worksheet>")

    workbook.append("</Workbook>")
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write("\n".join(workbook))


def write_excel(path: str, sheets: Dict[str, Sequence[Sequence[CellValue]]]) -> None:
    suffix = Path(path).suffix.lower()
    if suffix == ".xlsx":
        _write_excel_xlsx(path, sheets)
    else:
        write_excel_xml(path, sheets)


def _write_excel_xlsx(path: str, sheets: Dict[str, Sequence[Sequence[CellValue]]]) -> None:
    if openpyxl is None:
        raise RuntimeError("openpyxl is required to write .xlsx files. Install with: pip install openpyxl")

    workbook = openpyxl.Workbook()
    workbook.remove(workbook.active)
    for sheet_name, rows in sheets.items():
        safe_name = sheet_name[:31]
        worksheet = workbook.create_sheet(title=safe_name)
        for row in rows:
            worksheet.append(list(row))
    workbook.save(path)


def _cell_xml(value: CellValue) -> str:
    if value is None:
        return '<Cell><Data ss:Type="String"></Data></Cell>'
    if isinstance(value, (int, float)):
        return f'<Cell><Data ss:Type="Number">{value}</Data></Cell>'
    text = _xml_escape(str(value))
    return f'<Cell><Data ss:Type="String">{text}</Data></Cell>'


def _xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )
