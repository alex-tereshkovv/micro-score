from __future__ import annotations

import json
import re
import subprocess
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = ROOT / "apps" / "web"
PUBLIC_PAGES = (
    WEB_ROOT / "index.html",
    WEB_ROOT / "showcase.html",
    WEB_ROOT / "evidence.html",
)
MARKDOWN_ENTRY_POINTS = (
    ROOT / "README.md",
    ROOT / "docs" / "PROJECT_BRIEF.md",
)
DEPLOYMENT_ONLY_ASSETS = {
    "assets/Senim_Risk_Engineering_Case_Study.pdf",
    "assets/Senim_Risk_Research_Paper.pdf",
}
FORBIDDEN_TRACKED_PARTS = {
    ".ipynb_checkpoints",
    ".pytest_cache",
    ".venv",
    "__pycache__",
}


class PublicPageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.references: list[str] = []
        self.ids: set[str] = set()
        self.milestones = 0
        self.decisions = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag in {"a", "link"} and values.get("href"):
            self.references.append(str(values["href"]))
        if tag in {"img", "script"} and values.get("src"):
            self.references.append(str(values["src"]))
        if values.get("id"):
            self.ids.add(str(values["id"]))
        if "data-milestone" in values:
            self.milestones += 1
        if "data-decision" in values:
            self.decisions += 1


def local_web_target(page: Path, reference: str) -> Path | None:
    parsed = urlsplit(reference)
    if parsed.scheme or parsed.netloc or reference.startswith(("#", "data:")):
        return None
    relative = parsed.path.removeprefix("./")
    if not relative or relative in DEPLOYMENT_ONLY_ASSETS:
        return None
    return (page.parent / relative).resolve()


def markdown_targets(document: Path) -> list[tuple[str, Path]]:
    text = document.read_text(encoding="utf-8")
    targets: list[tuple[str, Path]] = []
    for reference in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
        parsed = urlsplit(reference)
        if parsed.scheme or parsed.netloc or reference.startswith("#"):
            continue
        relative = parsed.path
        if relative:
            targets.append((reference, (document.parent / relative).resolve()))
    return targets


def tracked_hygiene_violations() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    violations: list[str] = []
    for tracked in result.stdout.splitlines():
        path = Path(tracked)
        lowered = tracked.lower()
        if any(part in FORBIDDEN_TRACKED_PARTS for part in path.parts):
            violations.append(tracked)
        elif lowered.endswith((".sqlite", ".sqlite3", ".db", ".pem", ".key")):
            violations.append(tracked)
        elif path.name == ".env":
            violations.append(tracked)
    return violations


def main() -> None:
    page_parsers: dict[Path, PublicPageParser] = {}
    broken_local_links: list[str] = []
    local_references_checked = 0
    for page in PUBLIC_PAGES:
        html = page.read_text(encoding="utf-8")
        parser = PublicPageParser()
        parser.feed(html)
        page_parsers[page] = parser
        for reference in parser.references:
            target = local_web_target(page, reference)
            if target is None:
                continue
            local_references_checked += 1
            if not target.is_relative_to(WEB_ROOT) or not target.exists():
                broken_local_links.append(f"{page.name}: {reference}")
    if broken_local_links:
        raise AssertionError(f"Broken local reviewer links: {broken_local_links}")

    broken_markdown_links: list[str] = []
    markdown_links_checked = 0
    for document in MARKDOWN_ENTRY_POINTS:
        for reference, target in markdown_targets(document):
            markdown_links_checked += 1
            if not target.is_file():
                broken_markdown_links.append(f"{document.name}: {reference}")
    if broken_markdown_links:
        raise AssertionError(f"Broken reviewer Markdown links: {broken_markdown_links}")

    index_html = PUBLIC_PAGES[0].read_text(encoding="utf-8")
    showcase_html = PUBLIC_PAGES[1].read_text(encoding="utf-8")
    evidence_html = PUBLIC_PAGES[2].read_text(encoding="utf-8")
    styles = (WEB_ROOT / "styles.css").read_text(encoding="utf-8")
    release_gate = (ROOT / "scripts" / "check.ps1").read_text(encoding="utf-8")

    for claim in ["0.492", "0.775", "155", "52 / 52"]:
        if claim not in index_html:
            raise AssertionError(f"Reviewer home is missing evidence claim: {claim}")
    for boundary in [
        "Synthetic data only",
        "human decision support",
        "not a production lending model",
    ]:
        if boundary.lower() not in index_html.lower():
            raise AssertionError(f"Reviewer home is missing evidence boundary: {boundary}")

    evidence_parser = page_parsers[PUBLIC_PAGES[2]]
    missing_sections = sorted({"journey", "decisions", "proof", "limits"} - evidence_parser.ids)
    if missing_sections:
        raise AssertionError(f"Missing evidence sections: {missing_sections}")
    if evidence_parser.milestones != 13:
        raise AssertionError(f"Expected 13 milestones, found {evidence_parser.milestones}")
    if evidence_parser.decisions != 5:
        raise AssertionError(f"Expected 5 engineering decisions, found {evidence_parser.decisions}")
    for claim in ["0.501", "0.775", "155", "52 / 52", "90+"]:
        if claim not in evidence_html:
            raise AssertionError(f"Evidence hub is missing claim: {claim}")

    github_links = [
        reference
        for reference in evidence_parser.references
        if reference.startswith("https://github.com/")
    ]
    if len(github_links) < 15:
        raise AssertionError(f"Expected at least 15 GitHub proof links, found {len(github_links)}")
    if any("alex-tereshkovv/micro-score" not in link for link in github_links):
        raise AssertionError("Evidence hub links outside the Senim Risk repository")

    public_release_text = "\n".join([index_html, showcase_html, evidence_html, styles]).lower()
    if "admissions" in public_release_text:
        raise AssertionError("Public release still contains admissions-specific positioning")
    if "Engineering portfolio" not in showcase_html:
        raise AssertionError("Technical walkthrough is missing neutral portfolio positioning")
    if "20261027-senim-risk-brand-v2" not in index_html:
        raise AssertionError("Reviewer home cache version is stale")

    accessibility_contracts = {
        "index.html": [
            'class="skip-link" href="#reviewer-main"',
            'id="reviewer-main" class="reviewer-main" tabindex="-1"',
        ],
        "evidence.html": [
            'class="skip-link" href="#evidence-main"',
            '<main id="evidence-main" tabindex="-1">',
            "20261027-senim-risk-brand-v2",
        ],
        "showcase.html": [
            'class="skip-link" href="#showcase-main"',
            'id="showcase-main" class="showcase-stage" tabindex="-1"',
            "20261027-senim-risk-brand-v2",
            'role="tabpanel"',
            'aria-controls="showcase-scene-1"',
            'id="showcase-tab-7"',
            "aria-hidden=\"true\" inert",
        ],
    }
    page_text = {
        "index.html": index_html,
        "evidence.html": evidence_html,
        "showcase.html": showcase_html,
    }
    accessibility_checks = 0
    for page_name, markers in accessibility_contracts.items():
        for marker in markers:
            accessibility_checks += 1
            if marker not in page_text[page_name]:
                raise AssertionError(f"{page_name} is missing accessibility marker: {marker}")

    if showcase_html.count('role="tabpanel"') != 7:
        raise AssertionError("Walkthrough must expose seven tab panels")
    if showcase_html.count('aria-controls="showcase-scene-') != 7:
        raise AssertionError("Walkthrough tabs must control all seven scenes")

    showcase_script = (WEB_ROOT / "showcase.js").read_text(encoding="utf-8")
    for marker in [
        'button.tabIndex = active ? 0 : -1',
        'slide.hidden = !active',
        'event.stopPropagation()',
        'prefers-reduced-motion: reduce',
    ]:
        accessibility_checks += 1
        if marker not in showcase_script:
            raise AssertionError(f"Walkthrough keyboard contract is missing: {marker}")

    evidence_styles = (WEB_ROOT / "evidence.css").read_text(encoding="utf-8")
    showcase_styles = (WEB_ROOT / "showcase.css").read_text(encoding="utf-8")
    for stylesheet in [styles, evidence_styles, showcase_styles]:
        for marker in [".skip-link", "prefers-reduced-motion: reduce"]:
            accessibility_checks += 1
            if marker not in stylesheet:
                raise AssertionError(f"Public stylesheet is missing accessibility marker: {marker}")

    for marker in [
        "width: min(calc(100% + 80px), calc(100vw - 32px));",
        "margin-left: max(-40px, calc((100% - (100vw - 32px)) / 2));",
    ]:
        accessibility_checks += 1
        if marker not in evidence_styles:
            raise AssertionError(f"Evidence full-bleed section can overflow the viewport: {marker}")

    responsive_contracts = {
        "evidence.css": (evidence_styles, ["[hidden]", "min-width: 0"]),
        "showcase.css": (showcase_styles, ["[hidden]", "min-width: 0"]),
    }
    for stylesheet_name, (stylesheet, markers) in responsive_contracts.items():
        for marker in markers:
            accessibility_checks += 1
            if marker not in stylesheet:
                raise AssertionError(
                    f"{stylesheet_name} is missing responsive overflow protection: {marker}"
                )

    expected_grid = (
        "grid-template-columns: repeat(3, minmax(0, 1fr) minmax(18px, auto)) "
        "minmax(0, 1fr);"
    )
    if expected_grid not in styles:
        raise AssertionError("Reviewer architecture grid can regress into horizontal overflow")

    smoke_workflows = sum(
        1 for line in release_gate.splitlines() if 'Invoke-Step "' in line and "smoke" in line.lower()
    )
    if smoke_workflows != 13 or "13 local smoke workflows" not in evidence_html:
        raise AssertionError(
            f"Evidence hub and release gate disagree on smoke workflows: {smoke_workflows}"
        )

    hygiene_violations = tracked_hygiene_violations()
    if hygiene_violations:
        raise AssertionError(f"Tracked repository hygiene violations: {hygiene_violations}")

    print(
        json.dumps(
            {
                "mode": "reviewer-experience-smoke",
                "public_pages": len(PUBLIC_PAGES),
                "local_references_checked": local_references_checked,
                "markdown_links_checked": markdown_links_checked,
                "evidence_milestones": evidence_parser.milestones,
                "engineering_decisions": evidence_parser.decisions,
                "github_proof_links": len(github_links),
                "accessibility_checks": accessibility_checks,
                "smoke_workflows": smoke_workflows,
                "tracked_hygiene_violations": 0,
                "horizontal_overflow_regression": False,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
