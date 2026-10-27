from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

from pypdf import PdfReader


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = PROJECT_ROOT / "apps" / "web"


def load_brand_audit():
    path = PROJECT_ROOT / "scripts" / "brand_audit.py"
    spec = importlib.util.spec_from_file_location("brand_audit", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load brand audit module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BrandingTests(unittest.TestCase):
    def test_repository_has_no_unapproved_legacy_branding(self) -> None:
        report = load_brand_audit().audit()
        self.assertEqual(report["status"], "pass", report["violations"])
        self.assertEqual(report["path_violations"], [])

    def test_public_pages_use_senim_risk_metadata(self) -> None:
        legacy_name = "Micro" + "Score"
        for name in ("index.html", "showcase.html", "evidence.html"):
            html = (WEB_ROOT / name).read_text(encoding="utf-8")
            self.assertIn("Senim Risk", html)
            self.assertIn('name="application-name" content="Senim Risk"', html)
            self.assertIn('property="og:title"', html)
            self.assertIn('property="og:image"', html)
            self.assertIn("senim-risk-social-preview.png", html)
            self.assertNotIn(legacy_name, html)

    def test_public_brand_assets_and_documents_use_new_names(self) -> None:
        for name in (
            "senim-risk-mark.svg",
            "senim-risk-mark.png",
            "senim-risk-lockup.svg",
            "senim-risk-lockup.png",
            "senim-risk-social-preview.png",
            "favicon.svg",
            "favicon-32.png",
            "apple-touch-icon.png",
        ):
            self.assertTrue((WEB_ROOT / "assets" / name).exists(), name)
        legacy_name = "Micro" + "Score"
        for name in ("Senim_Risk_Research_Paper.pdf", "Senim_Risk_Engineering_Case_Study.pdf"):
            web_document = WEB_ROOT / "assets" / name
            output_document = PROJECT_ROOT / "output" / "pdf" / name
            self.assertTrue(web_document.exists())
            self.assertTrue(output_document.exists())
            reader = PdfReader(str(output_document))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
            self.assertIn("Senim Risk", text)
            self.assertNotIn(legacy_name, text)


if __name__ == "__main__":
    unittest.main()
