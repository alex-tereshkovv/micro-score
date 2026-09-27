from __future__ import annotations

import argparse
import re
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    Image,
    PageBreak,
    PageTemplate,
    Paragraph,
    Preformatted,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "docs" / "RESEARCH_PAPER.md"
DEFAULT_OUTPUT = ROOT / "output" / "pdf" / "MicroScore_Research_Paper.pdf"
REPOSITORY_URL = "https://github.com/alex-tereshkovv/micro-score"
LIVE_URL = "https://alex-tereshkovv.github.io/micro-score/"

NAVY = colors.HexColor("#10252D")
INK = colors.HexColor("#17282F")
MUTED = colors.HexColor("#60727B")
TEAL = colors.HexColor("#078B84")
TEAL_DARK = colors.HexColor("#05645F")
BLUE = colors.HexColor("#315F9F")
AMBER = colors.HexColor("#C87913")
LINE = colors.HexColor("#D7E3E6")
PALE = colors.HexColor("#F3F7F7")
PALE_TEAL = colors.HexColor("#E7F6F2")
PALE_BLUE = colors.HexColor("#EEF4FB")
WHITE = colors.white


def register_fonts() -> tuple[str, str]:
    candidates = [
        (
            Path("C:/Windows/Fonts/arial.ttf"),
            Path("C:/Windows/Fonts/arialbd.ttf"),
            "MicroScoreArial",
            "MicroScoreArialBold",
        ),
        (
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
            "MicroScoreSans",
            "MicroScoreSansBold",
        ),
    ]
    for regular, bold, regular_name, bold_name in candidates:
        if regular.exists() and bold.exists():
            pdfmetrics.registerFont(TTFont(regular_name, str(regular)))
            pdfmetrics.registerFont(TTFont(bold_name, str(bold)))
            return regular_name, bold_name
    return "Helvetica", "Helvetica-Bold"


FONT, FONT_BOLD = register_fonts()


def make_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "cover_eyebrow": ParagraphStyle(
            "CoverEyebrow",
            parent=base["BodyText"],
            fontName=FONT_BOLD,
            fontSize=8,
            leading=11,
            textColor=TEAL_DARK,
            spaceAfter=8,
        ),
        "cover_title": ParagraphStyle(
            "CoverTitle",
            parent=base["Title"],
            fontName=FONT_BOLD,
            fontSize=27,
            leading=31,
            textColor=NAVY,
            alignment=TA_LEFT,
            spaceAfter=12,
        ),
        "cover_meta": ParagraphStyle(
            "CoverMeta",
            parent=base["BodyText"],
            fontName=FONT,
            fontSize=10.5,
            leading=15,
            textColor=MUTED,
            spaceAfter=10,
        ),
        "cover_claim": ParagraphStyle(
            "CoverClaim",
            parent=base["BodyText"],
            fontName=FONT_BOLD,
            fontSize=13,
            leading=19,
            textColor=NAVY,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName=FONT,
            fontSize=9.25,
            leading=13.4,
            textColor=INK,
            alignment=TA_LEFT,
            spaceAfter=6,
            allowWidows=False,
        ),
        "small": ParagraphStyle(
            "Small",
            parent=base["BodyText"],
            fontName=FONT,
            fontSize=7.7,
            leading=10.5,
            textColor=MUTED,
        ),
        "metric": ParagraphStyle(
            "Metric",
            parent=base["BodyText"],
            fontName=FONT_BOLD,
            fontSize=19,
            leading=21,
            textColor=NAVY,
            alignment=TA_CENTER,
        ),
        "metric_label": ParagraphStyle(
            "MetricLabel",
            parent=base["BodyText"],
            fontName=FONT,
            fontSize=7.2,
            leading=9,
            textColor=MUTED,
            alignment=TA_CENTER,
        ),
        "H1": ParagraphStyle(
            "H1",
            parent=base["Heading1"],
            fontName=FONT_BOLD,
            fontSize=15,
            leading=19,
            textColor=NAVY,
            spaceBefore=10,
            spaceAfter=7,
            keepWithNext=True,
        ),
        "H2": ParagraphStyle(
            "H2",
            parent=base["Heading2"],
            fontName=FONT_BOLD,
            fontSize=10.7,
            leading=14,
            textColor=TEAL_DARK,
            spaceBefore=8,
            spaceAfter=5,
            keepWithNext=True,
        ),
        "bullet": ParagraphStyle(
            "Bullet",
            parent=base["BodyText"],
            fontName=FONT,
            fontSize=9,
            leading=13,
            leftIndent=12,
            firstLineIndent=-7,
            textColor=INK,
            spaceAfter=3,
        ),
        "code": ParagraphStyle(
            "Code",
            parent=base["Code"],
            fontName="Courier",
            fontSize=7.4,
            leading=10,
            leftIndent=7,
            rightIndent=7,
            textColor=NAVY,
            backColor=PALE,
            borderColor=LINE,
            borderWidth=0.5,
            borderPadding=7,
            spaceBefore=5,
            spaceAfter=8,
        ),
        "caption": ParagraphStyle(
            "Caption",
            parent=base["BodyText"],
            fontName=FONT,
            fontSize=7.6,
            leading=10.5,
            textColor=MUTED,
            alignment=TA_CENTER,
            spaceBefore=4,
            spaceAfter=8,
        ),
        "toc_title": ParagraphStyle(
            "TocTitle",
            parent=base["Heading1"],
            fontName=FONT_BOLD,
            fontSize=22,
            leading=26,
            textColor=NAVY,
            spaceAfter=12,
        ),
        "toc_0": ParagraphStyle(
            "TOC0",
            parent=base["BodyText"],
            fontName=FONT_BOLD,
            fontSize=9.5,
            leading=14,
            textColor=NAVY,
            leftIndent=0,
            firstLineIndent=0,
            spaceBefore=3,
        ),
        "toc_1": ParagraphStyle(
            "TOC1",
            parent=base["BodyText"],
            fontName=FONT,
            fontSize=8.3,
            leading=12,
            textColor=MUTED,
            leftIndent=12,
            firstLineIndent=0,
        ),
    }


def inline_markup(text: str) -> str:
    value = escape(text.strip())
    value = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda match: (
            f'<link href="{match.group(2)}" color="#315F9F">'
            f"{match.group(1)}</link>"
        ),
        value,
    )
    value = re.sub(r"`([^`]+)`", r'<font name="Courier">\1</font>', value)
    value = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", value)
    value = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", value)
    return value


def page_header_footer(canvas, doc) -> None:
    width, height = A4
    canvas.saveState()
    if doc.page == 1:
        canvas.setFillColor(NAVY)
        canvas.rect(0, height - 13 * mm, width, 13 * mm, stroke=0, fill=1)
        canvas.setFillColor(TEAL)
        canvas.rect(0, height - 15 * mm, width, 2 * mm, stroke=0, fill=1)
        canvas.restoreState()
        return

    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.5)
    canvas.line(doc.leftMargin, height - 16 * mm, width - doc.rightMargin, height - 16 * mm)
    canvas.setFont(FONT_BOLD, 7)
    canvas.setFillColor(TEAL_DARK)
    canvas.drawString(doc.leftMargin, height - 12.2 * mm, "MICROSCORE")
    canvas.setFont(FONT, 7)
    canvas.setFillColor(MUTED)
    canvas.drawRightString(width - doc.rightMargin, height - 12.2 * mm, "RESEARCH PAPER | SEPTEMBER 2026")
    canvas.line(doc.leftMargin, 15 * mm, width - doc.rightMargin, 15 * mm)
    canvas.setFont(FONT, 7)
    canvas.drawString(doc.leftMargin, 10.7 * mm, "Interpretable thin-file credit-risk decision support")
    canvas.drawRightString(width - doc.rightMargin, 10.7 * mm, str(doc.page))
    canvas.restoreState()


class ResearchDocTemplate(BaseDocTemplate):
    def afterFlowable(self, flowable) -> None:
        if not isinstance(flowable, Paragraph):
            return
        style_name = flowable.style.name
        if style_name not in {"H1", "H2"}:
            return
        level = 0 if style_name == "H1" else 1
        text = flowable.getPlainText()
        bookmark = getattr(flowable, "_bookmark_name", None)
        if bookmark is None:
            bookmark = f"section-{self.seq.nextf('section')}"
        self.canv.bookmarkPage(bookmark)
        self.canv.addOutlineEntry(text, bookmark, level=level, closed=False)
        if level == 0:
            self.notify("TOCEntry", (level, text, self.page, bookmark))


def cover_story(title: str, author_line: str, styles: dict[str, ParagraphStyle]) -> list:
    metrics = Table(
        [
            [
                Paragraph("0.830", styles["metric"]),
                Paragraph("0.492", styles["metric"]),
                Paragraph("0.775", styles["metric"]),
            ],
            [
                Paragraph("full synthetic RF<br/>ROC-AUC", styles["metric_label"]),
                Paragraph("RF without late-payment proxy<br/>ROC-AUC", styles["metric_label"]),
                Paragraph("public UCI RF<br/>ROC-AUC", styles["metric_label"]),
            ],
        ],
        colWidths=[54 * mm, 54 * mm, 54 * mm],
    )
    metrics.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PALE),
                ("BOX", (0, 0), (-1, -1), 0.7, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, 0), 12),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 3),
                ("TOPPADDING", (0, 1), (-1, 1), 3),
                ("BOTTOMPADDING", (0, 1), (-1, 1), 11),
            ]
        )
    )

    boundary = Table(
        [[Paragraph(
            "<b>Evidence boundary</b><br/>Synthetic Pavlodar-oriented data support engineering and diagnostic experiments. The public UCI benchmark tests pipeline portability. Neither validates real Kazakhstan lending decisions.",
            styles["body"],
        )]],
        colWidths=[162 * mm],
    )
    boundary.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PALE_TEAL),
                ("BOX", (0, 0), (-1, -1), 0.8, TEAL),
                ("LEFTPADDING", (0, 0), (-1, -1), 13),
                ("RIGHTPADDING", (0, 0), (-1, -1), 13),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )

    links = Table(
        [[
            Paragraph(f'<b>Repository</b><br/><link href="{REPOSITORY_URL}" color="#315F9F">{REPOSITORY_URL}</link>', styles["small"]),
            Paragraph(f'<b>Live prototype</b><br/><link href="{LIVE_URL}" color="#315F9F">{LIVE_URL}</link>', styles["small"]),
        ]],
        colWidths=[81 * mm, 81 * mm],
    )
    links.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PALE_BLUE),
                ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ]
        )
    )

    return [
        Spacer(1, 27 * mm),
        Paragraph("REPRODUCIBLE RESEARCH AND ENGINEERING STUDY", styles["cover_eyebrow"]),
        Paragraph(inline_markup(title), styles["cover_title"]),
        Paragraph(inline_markup(author_line), styles["cover_meta"]),
        HRFlowable(width="100%", thickness=1.1, color=TEAL, spaceBefore=3, spaceAfter=15),
        Paragraph(
            "The strongest result is not the headline score. It is the failure revealed when one repayment-history proxy is removed.",
            styles["cover_claim"],
        ),
        Spacer(1, 10 * mm),
        metrics,
        Spacer(1, 12 * mm),
        boundary,
        Spacer(1, 12 * mm),
        links,
        Spacer(1, 7 * mm),
        Paragraph(
            "Human-in-the-loop prototype. Synthetic public demo. Not validated for real lending.",
            styles["small"],
        ),
        PageBreak(),
    ]


def toc_story(styles: dict[str, ParagraphStyle]) -> list:
    toc = TableOfContents()
    toc.levelStyles = [styles["toc_0"], styles["toc_1"]]
    return [
        Paragraph("Contents", styles["toc_title"]),
        Paragraph(
            "This paper separates synthetic evidence, public benchmark evidence, product behavior, and blocked real-world claims.",
            styles["body"],
        ),
        Spacer(1, 4 * mm),
        toc,
        PageBreak(),
    ]


def make_table(rows: list[list[str]], styles: dict[str, ParagraphStyle]) -> Table:
    header = rows[0]
    body = rows[2:] if len(rows) > 1 and all(re.fullmatch(r":?-{3,}:?", cell.strip()) for cell in rows[1]) else rows[1:]
    data = [[Paragraph(inline_markup(cell), styles["small"]) for cell in header]]
    data.extend([[Paragraph(inline_markup(cell), styles["small"]) for cell in row] for row in body])
    columns = max(len(row) for row in data)
    for row in data:
        while len(row) < columns:
            row.append(Paragraph("", styles["small"]))
    widths = [162 * mm / columns] * columns
    table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
                ("BACKGROUND", (0, 1), (-1, -1), WHITE),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, PALE]),
                ("GRID", (0, 0), (-1, -1), 0.45, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def make_image(path: Path, caption: str, styles: dict[str, ParagraphStyle]) -> list:
    if not path.exists():
        raise FileNotFoundError(f"Paper figure is missing: {path}")
    image = Image(str(path))
    max_width = 158 * mm
    max_height = 66 * mm
    scale = min(max_width / image.imageWidth, max_height / image.imageHeight)
    image.drawWidth = image.imageWidth * scale
    image.drawHeight = image.imageHeight * scale
    image.hAlign = "CENTER"
    return [
        Spacer(1, 3 * mm),
        image,
        Paragraph(inline_markup(caption), styles["caption"]),
    ]


def parse_markdown(source: Path, styles: dict[str, ParagraphStyle]) -> tuple[str, str, list]:
    lines = source.read_text(encoding="utf-8").splitlines()
    if not lines or not lines[0].startswith("# "):
        raise ValueError("Research paper must start with a level-one title")
    title = lines[0][2:].strip()
    author_line = next((line.strip("* ") for line in lines[1:8] if line.startswith("**")), "Alexandr")
    start = next((index for index, line in enumerate(lines) if line.startswith("## ")), None)
    if start is None:
        raise ValueError("Research paper has no sections")

    story: list = []
    paragraph_lines: list[str] = []
    heading_counter = 0
    index = start

    def flush_paragraph() -> None:
        if not paragraph_lines:
            return
        text = " ".join(item.strip() for item in paragraph_lines)
        story.append(Paragraph(inline_markup(text), styles["body"]))
        paragraph_lines.clear()

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            index += 1
            continue

        if stripped.startswith("```"):
            flush_paragraph()
            code_lines: list[str] = []
            index += 1
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code_lines.append(lines[index])
                index += 1
            story.append(Preformatted("\n".join(code_lines), styles["code"]))
            index += 1
            continue

        image_match = re.fullmatch(r"!\[([^]]+)\]\(([^)]+)\)", stripped)
        if image_match:
            flush_paragraph()
            image_path = (source.parent / image_match.group(2)).resolve()
            story.extend(make_image(image_path, image_match.group(1), styles))
            index += 1
            continue

        if stripped.startswith("|"):
            flush_paragraph()
            table_rows: list[list[str]] = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                table_rows.append([cell.strip() for cell in lines[index].strip().strip("|").split("|")])
                index += 1
            story.extend([make_table(table_rows, styles), Spacer(1, 3 * mm)])
            continue

        if stripped.startswith("## ") or stripped.startswith("### "):
            flush_paragraph()
            level = 1 if stripped.startswith("## ") else 2
            text = stripped[3:].strip() if level == 1 else stripped[4:].strip()
            heading_counter += 1
            heading = Paragraph(inline_markup(text), styles["H1" if level == 1 else "H2"])
            heading._bookmark_name = f"heading-{heading_counter}"
            story.append(heading)
            index += 1
            continue

        bullet_match = re.match(r"^[-*] (.+)$", stripped)
        ordered_match = re.match(r"^(\d+)\. (.+)$", stripped)
        if bullet_match or ordered_match:
            flush_paragraph()
            if bullet_match:
                bullet_text, text = "-", bullet_match.group(1)
            else:
                bullet_text, text = f"{ordered_match.group(1)}.", ordered_match.group(2)
            story.append(Paragraph(inline_markup(text), styles["bullet"], bulletText=bullet_text))
            index += 1
            continue

        paragraph_lines.append(stripped)
        index += 1

    flush_paragraph()
    return title, author_line, story


def build_pdf(output_path: Path = DEFAULT_OUTPUT, source_path: Path = DEFAULT_SOURCE) -> Path:
    styles = make_styles()
    title, author_line, paper_story = parse_markdown(source_path, styles)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = ResearchDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=24 * mm,
        rightMargin=24 * mm,
        topMargin=22 * mm,
        bottomMargin=20 * mm,
        title=title,
        author="Alexandr",
        subject="MicroScore interpretable credit-risk research paper",
        creator="MicroScore reproducible research-paper builder",
    )
    frame = Frame(
        doc.leftMargin,
        doc.bottomMargin,
        doc.width,
        doc.height,
        id="paper",
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )
    doc.addPageTemplates([PageTemplate(id="research-paper", frames=[frame], onPage=page_header_footer)])
    story = cover_story(title, author_line, styles) + toc_story(styles) + paper_story
    doc.multiBuild(story)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the MicroScore research paper PDF.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = build_pdf(args.output.resolve(), args.source.resolve())
    print(output)


if __name__ == "__main__":
    main()
