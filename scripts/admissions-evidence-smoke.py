from __future__ import annotations

import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = ROOT / "apps" / "web"
EVIDENCE_PAGE = WEB_ROOT / "evidence.html"
DEPLOYMENT_ONLY_ASSETS = {"assets/MicroScore_Engineering_Case_Study.pdf"}


class EvidenceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []
        self.ids: set[str] = set()
        self.milestones = 0
        self.decisions = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "a" and values.get("href"):
            self.hrefs.append(str(values["href"]))
        if values.get("id"):
            self.ids.add(str(values["id"]))
        if "data-milestone" in values:
            self.milestones += 1
        if "data-decision" in values:
            self.decisions += 1


def local_target(href: str) -> Path | None:
    parsed = urlsplit(href)
    if parsed.scheme or parsed.netloc or href.startswith("#"):
        return None
    relative = parsed.path.removeprefix("./")
    if not relative or relative in DEPLOYMENT_ONLY_ASSETS:
        return None
    return (WEB_ROOT / relative).resolve()


def main() -> None:
    html = EVIDENCE_PAGE.read_text(encoding="utf-8")
    release_gate = (ROOT / "scripts" / "check.ps1").read_text(encoding="utf-8")
    parser = EvidenceParser()
    parser.feed(html)

    expected_sections = {"journey", "decisions", "proof", "limits"}
    missing_sections = sorted(expected_sections - parser.ids)
    if missing_sections:
        raise AssertionError(f"Missing evidence sections: {missing_sections}")
    if parser.milestones != 8:
        raise AssertionError(f"Expected 8 milestones, found {parser.milestones}")
    if parser.decisions != 5:
        raise AssertionError(f"Expected 5 engineering decisions, found {parser.decisions}")

    for claim in ["0.492", "0.775", "126", "52 / 52", "90+"]:
        if claim not in html:
            raise AssertionError(f"Missing evidence claim: {claim}")

    broken_local_links: list[str] = []
    for href in parser.hrefs:
        target = local_target(href)
        if target is not None and (not target.is_relative_to(WEB_ROOT) or not target.exists()):
            broken_local_links.append(href)
    if broken_local_links:
        raise AssertionError(f"Broken local evidence links: {broken_local_links}")

    github_links = [href for href in parser.hrefs if href.startswith("https://github.com/")]
    if len(github_links) < 15:
        raise AssertionError(f"Expected at least 15 GitHub proof links, found {len(github_links)}")
    if any("alex-tereshkovv/micro-score" not in href for href in github_links):
        raise AssertionError("Evidence page contains a GitHub link outside the MicroScore repository")

    smoke_workflows = sum(
        1 for line in release_gate.splitlines() if 'Invoke-Step "' in line and "smoke" in line.lower()
    )
    if smoke_workflows != 10 or "10 smoke workflows" not in html:
        raise AssertionError(
            f"Evidence page and release gate disagree on smoke workflows: {smoke_workflows}"
        )

    print(
        json.dumps(
            {
                "mode": "admissions-evidence-smoke",
                "milestones": parser.milestones,
                "decisions": parser.decisions,
                "proof_links": len(github_links),
                "local_links_checked": sum(local_target(href) is not None for href in parser.hrefs),
                "smoke_workflows": smoke_workflows,
                "claims": ["0.492", "0.775", "126", "52 / 52", "90+"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
