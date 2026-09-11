import unittest
import os
from pathlib import Path

from app.resume_parser import MAX_PDF_BYTES, parse_pdf


class ResumeParserTests(unittest.TestCase):
    def test_rejects_non_pdf(self) -> None:
        with self.assertRaisesRegex(ValueError, "有效 PDF"):
            parse_pdf("resume.pdf", b"not a pdf")

    def test_rejects_oversized_pdf(self) -> None:
        with self.assertRaisesRegex(ValueError, "10 MB"):
            parse_pdf("resume.pdf", b"%PDF" + b"x" * MAX_PDF_BYTES)

    @unittest.skipUnless(os.getenv("PRIVATE_RESUME_PATH") and Path(os.environ["PRIVATE_RESUME_PATH"]).exists(), "private local resume is not configured")
    def test_private_resume_extracts_expected_sections(self) -> None:
        path = Path(os.environ["PRIVATE_RESUME_PATH"])
        result = parse_pdf(path.name, path.read_bytes())
        titles = {section.title for section in result.sections}
        self.assertEqual(result.page_count, 1)
        self.assertTrue({"教育经历", "项目经历", "技能/证书及其他"}.issubset(titles))


if __name__ == "__main__":
    unittest.main()
