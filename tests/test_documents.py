import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from docx import Document

from backend.documents import build_export, document_docx, document_html, statement_for


class DocumentsTest(unittest.TestCase):
    def setUp(self):
        self.report = {"id": "test-report", "plate": "А123ВС186", "address": "Тестовый адрес <не событие>",
                       "observed_at": "2026-11-21T18:30:00+05:00", "designation": "both", "confirmed": True,
                       "applicant_name": "Тестовый заявитель", "applicant_email": "test@example.invalid", "recipient": "В тестовое подразделение"}

    def test_statement_has_observed_fields_without_verdict(self):
        statement = statement_for(self.report)
        for value in ("А123ВС186", "18:30", "UTC+05:00", "Тестовый адрес"):
            self.assertIn(value, statement)
        self.assertIn("мне неизвестны", statement)
        self.assertNotIn("без разрешения", statement)

    def test_docx_formal_formatting_and_no_invented_personal_details(self):
        document = Document(io.BytesIO(document_docx(self.report, [])))
        self.assertEqual(document.styles["Normal"].font.name, "Times New Roman")
        self.assertEqual(document.styles["Normal"].font.size.pt, 14)
        self.assertAlmostEqual(document.sections[0].page_width.cm, 21, places=1)
        text = "\n".join(p.text for p in document.paragraphs)
        self.assertIn("Тестовый заявитель", text)
        self.assertIn("Приложения", text)

    def test_html_escapes_user_text(self):
        self.assertIn("&lt;не событие&gt;", document_html(self.report, []))

    def test_package_keeps_original_bytes_and_hashes_every_attachment(self):
        original = b"opaque-original-image-bytes"
        with tempfile.TemporaryDirectory() as directory:
            photo = Path(directory) / "scene.jpg"
            photo.write_bytes(original)
            exported = build_export(self.report, [{"kind": "scene", "path": str(photo), "source": "upload"}])
        with ZipFile(io.BytesIO(exported)) as archive:
            self.assertEqual(archive.read("photos/scene.jpg"), original)
            manifest = json.loads(archive.read("manifest.json"))
            for entry in manifest["files"]:
                self.assertEqual(hashlib.sha256(archive.read(entry["path"])).hexdigest(), entry["sha256"])
            self.assertIn("statement.docx", archive.namelist())
            self.assertEqual(manifest["photos"][0]["source"], "upload")


if __name__ == "__main__":
    unittest.main()
