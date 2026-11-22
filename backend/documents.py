"""Formal citizen-appeal documents and verifiable, self-contained export package."""
from __future__ import annotations

import hashlib
import html
import io
import json
import mimetypes
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

SUBMISSION_URL = "https://госавтоинспекция.рф/request_main"
TITLE = "Заявление"
SUBJECT = "о проверке обстоятельств парковки транспортного средства"


def clean(value: object) -> str:
    """XML-safe user text. Keep newlines and printable Unicode, never field codes."""
    return "".join(c for c in str(value or "") if c in "\n\t" or (ord(c) >= 32 and ord(c) not in (0xFFFE, 0xFFFF)))


def display_time(value: object) -> str:
    raw = clean(value)
    if not raw:
        return "[укажите дату и время наблюдения]"
    try:
        moment = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        stamp = moment.strftime("%d.%m.%Y в %H:%M")
        offset = moment.strftime("%z")
        return stamp + (f" (UTC{offset[:3]}:{offset[3:]})" if offset else " (местное время, указано заявителем)")
    except ValueError:
        return raw


def statement_for(report: dict) -> str:
    """Use confirmed observations only; no automatic legal verdict or false facts."""
    designation = clean(report.get("designation"))
    descriptions = {
        "road_sign": "дорожный знак или табличка, обозначающие специальное парковочное место",
        "marking": "обозначение специального парковочного места на покрытии",
        "both": "дорожный знак и разметка специального парковочного места",
        "unclear": "обозначение парковочного места, значение которого прошу уточнить",
    }
    description = descriptions.get(designation, designation)
    paragraphs = [
        f"Прошу проверить обстоятельства парковки автомобиля с государственным регистрационным номером {clean(report.get('plate')) or '[укажите номер]'}.",
        f"Дата и время наблюдения: {display_time(report.get('observed_at'))}. Место наблюдения: {clean(report.get('address')) or '[укажите адрес или ориентир]' }.",
    ]
    if description:
        paragraphs.append(f"На месте наблюдения мной отмечено: {description}.")
    if report.get("observation"):
        paragraphs.append(clean(report["observation"]))
    if report.get("latitude") is not None and report.get("longitude") is not None:
        coords = f"Координаты, указанные заявителем: {report['latitude']}, {report['longitude']}"
        if report.get("accuracy") is not None:
            coords += f"; точность измерения устройством около {report['accuracy']} м"
        paragraphs.append(coords + ".")
    paragraphs.extend([
        "Фотографии прилагаются для проверки изложенных обстоятельств. Сведения о наличии у пользователя автомобиля права на использование указанного места мне неизвестны.",
        "Прошу рассмотреть обращение, проверить указанные обстоятельства и при наличии оснований принять предусмотренные законом меры. О результатах рассмотрения прошу сообщить по указанному адресу для ответа.",
    ])
    return "\n\n".join(paragraphs)


def header_lines(report: dict) -> list[str]:
    result = [clean(report.get("recipient")) or "В территориальное подразделение Госавтоинспекции [укажите подразделение]",
              f"от {clean(report.get('applicant_name')) or '[укажите фамилию, имя, отчество при наличии]'}"]
    if report.get("applicant_address"):
        result.append(f"Почтовый адрес: {clean(report['applicant_address'])}")
    if report.get("applicant_email"):
        result.append(f"Электронная почта: {clean(report['applicant_email'])}")
    if not report.get("applicant_address") and not report.get("applicant_email"):
        result.append("Адрес для ответа: [укажите почтовый или электронный адрес]")
    return result


def body_text(report: dict) -> str:
    return clean(report.get("statement")) or statement_for(report)


def attachment_names(photos: list[dict]) -> list[str]:
    names = {"scene": "Общий план автомобиля и парковочного места", "plate": "Фотография государственного регистрационного номера"}
    return [f"{i}. {names.get(p.get('kind'), 'Фотография')} — {p['export_name']}." for i, p in enumerate(photos, 1)]


def document_docx(report: dict, photos: list[dict]) -> bytes:
    document = Document()
    section = document.sections[0]
    section.page_width, section.page_height = Cm(21), Cm(29.7)
    section.top_margin = section.bottom_margin = Cm(2)
    section.left_margin, section.right_margin = Cm(3), Cm(1.5)
    section.header_distance = Cm(1)
    section.different_first_page_header_footer = True
    normal = document.styles["Normal"]
    normal.font.name, normal.font.size = "Times New Roman", Pt(14)
    normal.font.color.rgb = RGBColor(0, 0, 0)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    fmt = normal.paragraph_format
    fmt.line_spacing, fmt.space_after, fmt.first_line_indent = 1.5, Pt(0), Cm(1.25)
    fmt.widow_control = True
    normal.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    title_style = document.styles["Title"]
    title_style.font.name, title_style.font.size = "Times New Roman", Pt(14)
    title_style.font.color.rgb = RGBColor(0, 0, 0)
    for node in title_style.element.xpath("./w:pPr/w:pBdr"):
        node.getparent().remove(node)
    for line in header_lines(report):
        p = document.add_paragraph(line)
        p.paragraph_format.left_indent = Cm(8)
        p.paragraph_format.first_line_indent = Cm(0)
        p.paragraph_format.line_spacing = 1
        p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p.paragraph_format.keep_with_next = True
    p = document.add_paragraph(TITLE, style="Title")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(18)
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.first_line_indent = Cm(0)
    p.paragraph_format.keep_with_next = True
    for run in p.runs:
        run.font.name, run.font.size, run.bold = "Times New Roman", Pt(14), True
        run.font.color.rgb = RGBColor(0, 0, 0)
    p = document.add_paragraph(SUBJECT)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.first_line_indent = Cm(0)
    p.paragraph_format.space_after = Pt(12)
    p.paragraph_format.keep_with_next = True
    for text in body_text(report).split("\n"):
        if text.strip():
            document.add_paragraph(text.strip())
    p = document.add_paragraph("Приложения:")
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.first_line_indent = Cm(0)
    p.paragraph_format.keep_with_next = True
    for name in attachment_names(photos):
        p = document.add_paragraph(name)
        p.paragraph_format.first_line_indent = Cm(0)
        p.paragraph_format.line_spacing = 1
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p = document.add_paragraph("Дата: __________________    Подпись: __________________")
    p.paragraph_format.first_line_indent = Cm(0)
    p.paragraph_format.space_before = Pt(18)
    header = section.header.paragraphs[0]
    header.alignment = WD_ALIGN_PARAGRAPH.CENTER
    header.paragraph_format.first_line_indent = Cm(0)
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "PAGE")
    header._p.append(field)
    document.core_properties.title = f"{TITLE} {SUBJECT}"
    document.core_properties.author = clean(report.get("applicant_name"))
    result = io.BytesIO()
    document.save(result)
    return result.getvalue()


def document_html(report: dict, photos: list[dict]) -> str:
    esc = lambda s: html.escape(clean(s))
    paragraphs = "".join(f"<p>{esc(p)}</p>" for p in body_text(report).split("\n") if p.strip())
    header = "<br>".join(esc(line) for line in header_lines(report))
    attachments = "".join(f"<p class='attachment'>{esc(name)}</p>" for name in attachment_names(photos))
    return f"""<!doctype html><html lang="ru"><head><meta charset="utf-8"><title>Заявление</title>
<style>@page{{size:A4;margin:20mm 15mm 20mm 30mm}}*{{box-sizing:border-box}}body{{font:14pt/1.5 'Times New Roman',serif;color:#000;max-width:165mm;margin:20mm auto;background:white}}p{{margin:0;text-align:justify;text-indent:1.25cm;overflow-wrap:anywhere}}.recipient{{margin-left:80mm;line-height:1;text-indent:0;text-align:left}}h1{{font: bold 14pt 'Times New Roman',serif;text-align:center;margin:18pt 0 0}}.subject{{text-align:center;text-indent:0;margin-bottom:12pt}}.attachments{{margin-top:12pt}}.attachment{{text-indent:0;line-height:1}}.signature{{margin-top:18pt;text-indent:0}}@media screen{{body{{padding:24px;max-width:820px}}}}</style></head><body>
<p class="recipient">{header}</p><h1>{TITLE}</h1><p class="subject">{SUBJECT}</p>{paragraphs}
<p class="attachments attachment">Приложения:</p>{attachments}<p class="signature">Дата: __________________ &nbsp; Подпись: __________________</p></body></html>"""


def build_export(report: dict, photos: list[dict]) -> bytes:
    files: dict[str, bytes] = {}
    photo_manifest = []
    normalized = []
    for index, photo in enumerate(photos):
        path = Path(photo["path"])
        data = path.read_bytes()
        kind = photo.get("kind", f"photo-{index + 1}")
        kind = kind if kind in {"scene", "plate"} else f"photo-{index + 1}"
        suffix = path.suffix.lower()
        if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
            suffix = mimetypes.guess_extension(photo.get("mime_type", "image/jpeg")) or ".jpg"
        name = f"photos/{kind}{suffix}"
        if name in files:
            name = f"photos/{kind}-{index + 1}{suffix}"
        files[name] = data
        normalized.append({**photo, "export_name": name})
        photo_manifest.append({"path": name, "kind": kind, "source": photo.get("source", "upload"), "captured_at": photo.get("captured_at"), "received_at": photo.get("received_at"), "original_name": photo.get("original_name")})
    full_text = "\n".join(header_lines(report)) + f"\n\n{TITLE}\n{SUBJECT}\n\n{body_text(report)}\n\nПриложения:\n" + "\n".join(attachment_names(normalized)) + "\n\nДата: ______________ Подпись: ______________\n"
    files["statement.txt"] = full_text.encode("utf-8")
    files["statement.html"] = document_html(report, normalized).encode("utf-8")
    files["statement.docx"] = document_docx(report, normalized)
    instruction = f"""Пакет материалов к обращению

1. Откройте statement.docx в Word или statement.html в браузере и проверьте сведения.
2. Откройте официальный раздел приёма обращений: {SUBMISSION_URL}
3. Выполните вход и заполните обязательные поля официальной формы. Текст можно скопировать из statement.txt. Прикрепите исходные фотографии из папки photos. ZIP может не приниматься формой — распакуйте его.
4. Подачу выполняете вы. Этот пакет не подтверждает отправку или регистрацию обращения.
5. При бумажной подаче укажите дату и подпишите заявление собственноручно.

Указывайте только достоверные сведения. Расходы на рассмотрение обращения с заведомо ложными сведениями могут быть взысканы с заявителя по решению суда (ч. 2 ст. 16 Федерального закона № 59-ФЗ).

Хеши SHA-256 позволяют сверить файлы с manifest. Они не подтверждают подлинность события, времени или места. Указанная точность геолокации является оценкой устройства.
"""
    files["instruction.txt"] = instruction.encode("utf-8")
    manifest = {
        "schema_version": 1, "report_id": report.get("id"), "exported_at": datetime.now(timezone.utc).isoformat(),
        "observed_at": report.get("observed_at"), "location_source": report.get("location_source"),
        "location": {key: report.get(key) for key in ("latitude", "longitude", "accuracy", "address")},
        "confirmed": report.get("confirmed", False), "analysis": report.get("analysis"),
        "photos": photo_manifest,
        "files": [{"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()} for name, data in files.items()],
        "integrity_note": "Хеш подтверждает совпадение файла с manifest, но не достоверность события, времени или места.",
    }
    files["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
    output = io.BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return output.getvalue()
