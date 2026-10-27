from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEGACY_TERMS = {
    "legacy_pascal": "Micro" + "Score",
    "legacy_hyphen": "micro" + "-score",
    "legacy_lower": "micro" + "score",
    "legacy_upper": "MICRO" + "SCORE",
}
IMMUTABLE_URL_FRAGMENTS = (
    "github.com/alex-tereshkovv/" + LEGACY_TERMS["legacy_hyphen"],
    "alex-tereshkovv.github.io/" + LEGACY_TERMS["legacy_hyphen"],
    "alex-tereshkovv/" + LEGACY_TERMS["legacy_hyphen"],
)
SKIPPED_PATHS = {
    Path("scripts/brand_audit.py"),
}
SKIPPED_SUFFIXES = {
    ".gif",
    ".ico",
    ".jpeg",
    ".jpg",
    ".pdf",
    ".png",
    ".pyc",
    ".webp",
    ".xlsx",
    ".xls",
}


def repository_paths() -> list[Path]:
    completed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return sorted(
        (Path(raw_path) for raw_path in completed.stdout.splitlines()),
        key=lambda item: item.as_posix().lower(),
    )


def repository_files() -> list[Path]:
    return [
        relative
        for relative in repository_paths()
        if relative not in SKIPPED_PATHS
        and relative.suffix.lower() not in SKIPPED_SUFFIXES
        and (ROOT / relative).is_file()
    ]


def is_identifier_character(value: str) -> bool:
    return value.isalnum() or value == "_"


def category_for(relative: Path, line: str, term_key: str, column: int) -> tuple[str, str, bool]:
    term = LEGACY_TERMS[term_key]
    before = line[column - 1] if column else ""
    after_index = column + len(term)
    after = line[after_index] if after_index < len(line) else ""

    if term_key == "legacy_hyphen":
        if any(fragment in line for fragment in IMMUTABLE_URL_FRAGMENTS):
            return (
                "immutable_repository_or_pages_url",
                "The current GitHub repository and Pages paths must remain unchanged until redirects exist.",
                True,
            )
        return ("public_brand_violation", "Legacy hyphenated branding is not an approved public identifier.", False)

    if term_key == "legacy_pascal":
        if f"X-{term}-Delivery" in line:
            return (
                "http_header_compatibility",
                "Existing webhook header names remain supported as a versioned API contract.",
                True,
            )
        if (before and is_identifier_character(before)) or (after and is_identifier_character(after)):
            return (
                "code_identifier_compatibility",
                "A Python class or browser global is preserved to avoid breaking imports and runtime integration.",
                True,
            )
        return ("public_brand_violation", "Standalone legacy product branding is not allowed.", False)

    if term_key == "legacy_upper":
        if after == "_" or f"{term}_" in line:
            return (
                "environment_variable_compatibility",
                "Existing environment-variable names remain supported for deployment compatibility.",
                True,
            )
        return ("public_brand_violation", "Standalone uppercase legacy branding is not allowed.", False)

    path_text = relative.as_posix()
    if path_text.startswith("src/micro" + "score") or path_text.startswith("tests/"):
        return (
            "python_or_test_identifier_compatibility",
            "Python package/import names and tests that exercise them remain unchanged for compatibility.",
            True,
        )
    if "localStorage" in line or f'"{term}.' in line or f"'{term}." in line:
        return (
            "browser_storage_compatibility",
            "Browser storage keys remain unchanged so existing demo sessions and saved evidence continue to load.",
            True,
        )
    if relative == Path("pyproject.toml") and f"{term}-" in line:
        return (
            "legacy_cli_alias",
            "Legacy command aliases remain alongside the new Senim Risk commands for backward compatibility.",
            True,
        )
    if any(token in line.lower() for token in ("sqlite", "postgres", "database", "docker", "user ", "service", "logger", "logging", "temp", "schema_version", "prefix=")):
        return (
            "runtime_or_storage_compatibility",
            "A database, service, logger, container, temporary-file, or versioned schema identifier is preserved.",
            True,
        )
    if any(token in line for token in ("import ", "from ", "python -m ", "src/", "src\\", "module", "MICROSCORE_")):
        return (
            "module_or_environment_compatibility",
            "An import path, module command, source path, or environment contract is preserved.",
            True,
        )
    return (
        "internal_compatibility_identifier",
        "An established internal identifier is preserved because changing it is outside the branding-only migration.",
        True,
    )


def audit() -> dict[str, object]:
    occurrences: list[dict[str, object]] = []
    for relative in repository_files():
        path = ROOT / relative
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        for line_number, line in enumerate(text.splitlines(), start=1):
            for term_key, term in LEGACY_TERMS.items():
                start = 0
                while True:
                    column = line.find(term, start)
                    if column < 0:
                        break
                    category, rationale, allowed = category_for(relative, line, term_key, column)
                    occurrences.append(
                        {
                            "file": relative.as_posix(),
                            "line": line_number,
                            "column": column + 1,
                            "term": term_key,
                            "category": category,
                            "allowed": allowed,
                            "rationale": rationale,
                        }
                    )
                    start = column + len(term)

    path_violations = []
    for relative in repository_paths():
        if not (ROOT / relative).exists():
            continue
        path_text = relative.as_posix()
        if LEGACY_TERMS["legacy_pascal"] in path_text or LEGACY_TERMS["legacy_hyphen"] in path_text:
            path_violations.append(path_text)

    categories = Counter(str(item["category"]) for item in occurrences)
    terms = Counter(str(item["term"]) for item in occurrences)
    files_by_category: dict[str, list[str]] = defaultdict(list)
    for item in occurrences:
        category = str(item["category"])
        file_name = str(item["file"])
        if file_name not in files_by_category[category]:
            files_by_category[category].append(file_name)

    violations = [item for item in occurrences if not bool(item["allowed"])]
    return {
        "brand": "Senim Risk",
        "status": "pass" if not violations and not path_violations else "fail",
        "occurrence_count": len(occurrences),
        "term_counts": dict(sorted(terms.items())),
        "category_counts": dict(sorted(categories.items())),
        "files_by_category": dict(sorted(files_by_category.items())),
        "path_violations": path_violations,
        "violations": violations,
        "occurrences": occurrences,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit the repository for legacy public branding and approved compatibility identifiers.")
    parser.add_argument("--details", action="store_true", help="Print every remaining legacy occurrence with its rationale.")
    parser.add_argument("--json", action="store_true", help="Print the complete machine-readable audit report.")
    args = parser.parse_args()

    report = audit()
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"Senim Risk brand audit: {report['status']}")
        print(f"Approved compatibility occurrences: {report['occurrence_count'] - len(report['violations'])}")
        for term, count in report["term_counts"].items():
            print(f"  {term}: {count}")
        print("Categories:")
        for category, count in report["category_counts"].items():
            print(f"  {category}: {count}")
        if args.details:
            for item in report["occurrences"]:
                print(
                    f"{item['file']}:{item['line']}:{item['column']} "
                    f"[{item['term']}] {item['category']} - {item['rationale']}"
                )
        for path in report["path_violations"]:
            print(f"Legacy public filename: {path}", file=sys.stderr)
        for item in report["violations"]:
            print(
                f"Brand violation: {item['file']}:{item['line']}:{item['column']} "
                f"({item['term']})",
                file=sys.stderr,
            )
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
