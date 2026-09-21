from __future__ import annotations

import argparse
import csv
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    Image,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "output" / "pdf" / "MicroScore_Engineering_Case_Study.pdf"
RESEARCH_DIR = ROOT / "reports" / "research-artifacts"
BENCHMARK_DIR = ROOT / "reports" / "benchmark-artifacts" / "uci-default-credit-card-clients"
WEB_ASSETS = ROOT / "apps" / "web" / "assets"
LIVE_REVIEW_URL = "https://alex-tereshkovv.github.io/micro-score/#/review"
REPOSITORY_URL = "https://github.com/alex-tereshkovv/micro-score"


NAVY = colors.HexColor("#10252D")
INK = colors.HexColor("#13242B")
MUTED = colors.HexColor("#64747D")
TEAL = colors.HexColor("#078B84")
TEAL_DARK = colors.HexColor("#05645F")
BLUE = colors.HexColor("#315F9F")
AMBER = colors.HexColor("#C87913")
RED = colors.HexColor("#B53B3B")
GREEN = colors.HexColor("#1F7A4D")
LINE = colors.HexColor("#D9E4E7")
PALE = colors.HexColor("#F3F7F7")
PALE_TEAL = colors.HexColor("#E7F6F2")
PALE_AMBER = colors.HexColor("#FFF4DF")
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


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Required artifact is missing: {path}")
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def select_row(rows: list[dict[str, str]], **criteria: str) -> dict[str, str]:
    for row in rows:
        if all(row.get(key) == value for key, value in criteria.items()):
            return row
    raise ValueError(f"No artifact row matches {criteria}")


def percent(value: str | float, digits: int = 1) -> str:
    return f"{float(value) * 100:.{digits}f}%"


def metric(value: str | float, digits: int = 3) -> str:
    return f"{float(value):.{digits}f}"


def paragraph(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(text, style)


def make_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName=FONT,
            fontSize=9.3,
            leading=14,
            textColor=INK,
            spaceAfter=7,
        ),
        "small": ParagraphStyle(
            "Small",
            parent=base["BodyText"],
            fontName=FONT,
            fontSize=7.7,
            leading=11,
            textColor=MUTED,
        ),
        "tiny": ParagraphStyle(
            "Tiny",
            parent=base["BodyText"],
            fontName=FONT,
            fontSize=6.8,
            leading=9,
            textColor=MUTED,
        ),
        "eyebrow": ParagraphStyle(
            "Eyebrow",
            parent=base["BodyText"],
            fontName=FONT_BOLD,
            fontSize=7.6,
            leading=10,
            textColor=TEAL_DARK,
            spaceAfter=7,
        ),
        "title": ParagraphStyle(
            "Title",
            parent=base["Title"],
            fontName=FONT_BOLD,
            fontSize=31,
            leading=33,
            textColor=NAVY,
            alignment=TA_LEFT,
            spaceAfter=13,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle",
            parent=base["BodyText"],
            fontName=FONT,
            fontSize=12,
            leading=18,
            textColor=MUTED,
            spaceAfter=14,
        ),
        "h1": ParagraphStyle(
            "H1",
            parent=base["Heading1"],
            fontName=FONT_BOLD,
            fontSize=22,
            leading=25,
            textColor=NAVY,
            spaceAfter=14,
        ),
        "h2": ParagraphStyle(
            "H2",
            parent=base["Heading2"],
            fontName=FONT_BOLD,
            fontSize=13,
            leading=16,
            textColor=INK,
            spaceBefore=7,
            spaceAfter=7,
        ),
        "card_title": ParagraphStyle(
            "CardTitle",
            parent=base["BodyText"],
            fontName=FONT_BOLD,
            fontSize=10,
            leading=13,
            textColor=INK,
            spaceAfter=5,
        ),
        "metric": ParagraphStyle(
            "Metric",
            parent=base["BodyText"],
            fontName=FONT_BOLD,
            fontSize=20,
            leading=22,
            textColor=NAVY,
        ),
        "metric_light": ParagraphStyle(
            "MetricLight",
            parent=base["BodyText"],
            fontName=FONT_BOLD,
            fontSize=20,
            leading=22,
            textColor=WHITE,
        ),
        "white": ParagraphStyle(
            "White",
            parent=base["BodyText"],
            fontName=FONT,
            fontSize=9,
            leading=14,
            textColor=colors.HexColor("#DDEBED"),
        ),
        "white_bold": ParagraphStyle(
            "WhiteBold",
            parent=base["BodyText"],
            fontName=FONT_BOLD,
            fontSize=10,
            leading=14,
            textColor=WHITE,
        ),
        "table_head": ParagraphStyle(
            "TableHead",
            parent=base["BodyText"],
            fontName=FONT_BOLD,
            fontSize=7.1,
            leading=9,
            textColor=WHITE,
        ),
        "table_cell": ParagraphStyle(
            "TableCell",
            parent=base["BodyText"],
            fontName=FONT,
            fontSize=7.2,
            leading=9.5,
            textColor=INK,
        ),
        "table_cell_bold": ParagraphStyle(
            "TableCellBold",
            parent=base["BodyText"],
            fontName=FONT_BOLD,
            fontSize=7.2,
            leading=9.5,
            textColor=INK,
        ),
        "quote": ParagraphStyle(
            "Quote",
            parent=base["BodyText"],
            fontName=FONT_BOLD,
            fontSize=13,
            leading=19,
            textColor=NAVY,
        ),
        "center": ParagraphStyle(
            "Center",
            parent=base["BodyText"],
            fontName=FONT,
            fontSize=8,
            leading=11,
            alignment=TA_CENTER,
            textColor=MUTED,
        ),
    }


def page_header_footer(canvas, doc) -> None:
    canvas.saveState()
    width, height = A4
    if doc.page > 1:
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.5)
        canvas.line(doc.leftMargin, height - 24 * mm, width - doc.rightMargin, height - 24 * mm)
        canvas.setFont(FONT_BOLD, 7)
        canvas.setFillColor(TEAL_DARK)
        canvas.drawString(doc.leftMargin, height - 19.5 * mm, "MICROSCORE ENGINEERING CASE STUDY")
        canvas.setFont(FONT, 7)
        canvas.setFillColor(MUTED)
        canvas.drawRightString(width - doc.rightMargin, height - 19.5 * mm, "ADMISSIONS EVIDENCE PACKAGE")
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.5)
    canvas.line(doc.leftMargin, 18 * mm, width - doc.rightMargin, 18 * mm)
    canvas.setFont(FONT, 7)
    canvas.setFillColor(MUTED)
    canvas.drawString(doc.leftMargin, 12.5 * mm, "Synthetic research prototype - not validated for lending")
    canvas.drawRightString(width - doc.rightMargin, 12.5 * mm, f"{doc.page:02d}")
    canvas.restoreState()


def section_heading(number: str, label: str, title: str, styles: dict[str, ParagraphStyle]):
    badge = Table(
        [[paragraph(number, styles["white_bold"])]],
        colWidths=[12 * mm],
        rowHeights=[12 * mm],
    )
    badge.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), NAVY),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOX", (0, 0), (-1, -1), 0, NAVY),
            ]
        )
    )
    heading = [
        paragraph(label.upper(), styles["eyebrow"]),
        paragraph(title, styles["h1"]),
    ]
    block = Table([[badge, heading]], colWidths=[16 * mm, 150 * mm])
    block.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    return block


def card(title: str, body: str, styles: dict[str, ParagraphStyle], *, tone: str = "neutral") -> Table:
    palette = {
        "neutral": (WHITE, LINE),
        "teal": (PALE_TEAL, colors.HexColor("#B9DDD7")),
        "amber": (PALE_AMBER, colors.HexColor("#EBCB92")),
    }
    background, border = palette[tone]
    content = [[paragraph(title, styles["card_title"]), paragraph(body, styles["small"])]]
    table = Table(content, colWidths=[42 * mm, 118 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), background),
                ("BOX", (0, 0), (-1, -1), 0.7, border),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    return table


def bullet_lines(items: list[str], styles: dict[str, ParagraphStyle]) -> list[Paragraph]:
    return [paragraph(f"- {escape(item)}", styles["body"]) for item in items]


def metric_cards(items: list[tuple[str, str]], styles: dict[str, ParagraphStyle]) -> Table:
    cells = []
    for value, label in items:
        cells.append([paragraph(value, styles["metric"]), Spacer(1, 5), paragraph(label, styles["small"])])
    table = Table([cells], colWidths=[41 * mm] * len(cells))
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), WHITE),
                ("BOX", (0, 0), (-1, -1), 0.7, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )
    return table


def qr_drawing(value: str, size: float = 34 * mm) -> Drawing:
    widget = qr.QrCodeWidget(value)
    bounds = widget.getBounds()
    drawing = Drawing(size, size, transform=[size / (bounds[2] - bounds[0]), 0, 0, size / (bounds[3] - bounds[1]), 0, 0])
    drawing.add(widget)
    return drawing


def scaled_image(path: Path, width: float, height: float) -> Image:
    if not path.exists():
        raise FileNotFoundError(f"Required chart is missing: {path}")
    image = Image(str(path), width=width, height=height, kind="proportional")
    image.hAlign = "CENTER"
    return image


def evidence_table(rows: list[list[str]], widths: list[float], styles: dict[str, ParagraphStyle]) -> Table:
    rendered = []
    for row_index, row in enumerate(rows):
        cell_style = styles["table_head"] if row_index == 0 else styles["table_cell"]
        rendered.append([paragraph(escape(str(value)), cell_style) for value in row])
    table = Table(rendered, colWidths=widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, PALE]),
                ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, LINE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return table


def build_story(styles: dict[str, ParagraphStyle]) -> list:
    model_rows = read_csv(RESEARCH_DIR / "model_metrics.csv")
    ablation_rows = read_csv(RESEARCH_DIR / "ablation_study.csv")
    benchmark_rows = read_csv(BENCHMARK_DIR / "model_metrics.csv")
    policy_rows = read_csv(RESEARCH_DIR / "policy_analysis.csv")
    proxy_rows = read_csv(RESEARCH_DIR / "proxy_monitoring.csv")

    synthetic_lr = select_row(model_rows, model="Logistic Regression")
    synthetic_rf = select_row(model_rows, model="Random Forest")
    thin_rf = select_row(ablation_rows, scenario="no_late_payment_count", model="Random Forest")
    behavioral_rf = select_row(ablation_rows, scenario="behavioral_only", model="Random Forest")
    regional_rf = select_row(ablation_rows, scenario="regional_only", model="Random Forest")
    benchmark_lr = select_row(benchmark_rows, model="Logistic Regression")
    benchmark_rf = select_row(benchmark_rows, model="Random Forest")
    proxy = select_row(proxy_rows, feature="late_payment_count")

    story: list = []

    # Cover
    logo_path = WEB_ASSETS / "micro-score-lockup.png"
    if logo_path.exists():
        logo = Image(str(logo_path), width=57 * mm, height=26 * mm, kind="proportional")
        logo.hAlign = "LEFT"
        story.append(logo)
    story.extend(
        [
            Spacer(1, 8 * mm),
            paragraph("COMPUTER ENGINEERING ADMISSIONS CASE STUDY", styles["eyebrow"]),
            paragraph("Engineering a responsible credit-risk system for thin-file borrowers", styles["title"]),
            paragraph(
                "MicroScore combines interpretable machine learning, a role-based FastAPI product, "
                "tenant-aware data infrastructure, and reproducible Monte Carlo stress testing around "
                "a financial-inclusion problem in Pavlodar, Kazakhstan.",
                styles["subtitle"],
            ),
            HRFlowable(width="100%", thickness=3, color=TEAL, spaceBefore=5, spaceAfter=16),
            metric_cards(
                [
                    (metric(benchmark_rf["test_roc_auc"]), "UCI benchmark RF ROC-AUC"),
                    ("126", "automated release-gate tests"),
                    ("52 / 52", "PostgreSQL adapter methods"),
                    ("3", "connected engineering layers"),
                ],
                styles,
            ),
            Spacer(1, 9 * mm),
        ]
    )
    cover_summary = Table(
        [
            [
                [
                    paragraph("THE CORE QUESTION", styles["eyebrow"]),
                    paragraph(
                        "Can behavioral financial signals help a human loan officer review borrowers who have little formal credit history - without hiding uncertainty, proxy risk, or operational constraints?",
                        styles["quote"],
                    ),
                    Spacer(1, 6),
                    paragraph(
                        "The project answers with a working research-and-product system, then documents where the evidence fails. Its most important finding is that the synthetic model is too dependent on repayment-history proxy information for real thin-file claims.",
                        styles["body"],
                    ),
                ],
                [
                    qr_drawing(LIVE_REVIEW_URL),
                    paragraph("SCAN FOR LIVE REVIEW MODE", styles["center"]),
                    paragraph(LIVE_REVIEW_URL, styles["tiny"]),
                ],
            ]
        ],
        colWidths=[122 * mm, 42 * mm],
    )
    cover_summary.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, 0), PALE),
                ("BACKGROUND", (1, 0), (1, 0), PALE_TEAL),
                ("BOX", (0, 0), (-1, -1), 0.7, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 14),
                ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                ("TOPPADDING", (0, 0), (-1, -1), 14),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
            ]
        )
    )
    story.extend(
        [
            cover_summary,
            Spacer(1, 9 * mm),
            paragraph("Alexandr | Pavlodar, Kazakhstan | September 2026", styles["small"]),
            PageBreak(),
        ]
    )

    # Problem and principles
    story.extend(
        [
            section_heading("01", "Problem framing", "A local problem, treated as a systems problem", styles),
            paragraph(
                "Thin-file borrowers can be rejected because the financial system cannot observe them well, not necessarily because they are unreliable. Alternative data may improve visibility, but it can also encode wealth, digital access, geography, and past access to formal credit. That makes this both an engineering and governance problem.",
                styles["body"],
            ),
            Spacer(1, 4),
            card("Product goal", "Support a trained MFI analyst with probability, risk band, explanations, lifecycle evidence, policy trade-offs, and portfolio uncertainty.", styles, tone="teal"),
            Spacer(1, 6),
            card("Safety boundary", "The first version does not approve or reject loans automatically. The public demo uses synthetic data and does not collect real borrower identity or banking records.", styles, tone="amber"),
            Spacer(1, 6 * mm),
            paragraph("Four design principles", styles["h2"]),
        ]
    )
    principle_cells = []
    principles = [
        ("Interpretability", "A score must expose local positive and protective factors."),
        ("Traceability", "Every decision remains linked to model version, application state, and audit evidence."),
        ("Uncertainty", "Policy choices are stress-tested as ranges, not presented as guaranteed forecasts."),
        ("Claim discipline", "Synthetic, public benchmark, and future local evidence are kept separate."),
    ]
    for title, body in principles:
        principle_cells.append([paragraph(title, styles["card_title"]), paragraph(body, styles["small"])])
    principle_table = Table([principle_cells[:2], principle_cells[2:]], colWidths=[82 * mm, 82 * mm])
    principle_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), WHITE),
                ("BOX", (0, 0), (-1, -1), 0.7, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )
    story.extend(
        [
            principle_table,
            Spacer(1, 7 * mm),
            paragraph("Why Pavlodar", styles["h2"]),
            paragraph(
                "The regional scaffold represents urban, industrial-city, peri-urban, and rural contexts. It is useful for testing workflow and monitoring design, but it is explicitly labeled as simulated context until replaced by measured local evidence.",
                styles["body"],
            ),
            PageBreak(),
        ]
    )

    # Architecture
    story.extend(
        [
            section_heading("02", "System architecture", "One traceable path from consent to portfolio evidence", styles),
            paragraph(
                "The prototype is deliberately broader than a notebook. It joins a reproducible ML layer to operational API contracts and a reviewer-ready browser experience.",
                styles["body"],
            ),
            Spacer(1, 4 * mm),
        ]
    )
    architecture = [
        ("01", "Borrower intake", "Typed signals, explicit consent, validation, privacy-safe application history."),
        ("02", "Scoring service", "Versioned probability, risk band, warnings, and additive explanation factors."),
        ("03", "Human review", "Analyst packet, affordability context, governance flags, decision history."),
        ("04", "Policy stress test", "Seeded Monte Carlo, paired scenarios, risk appetite, evidence dossier."),
    ]
    architecture_cells = []
    for number, title, body in architecture:
        architecture_cells.append(
            [
                paragraph(number, styles["eyebrow"]),
                paragraph(title, styles["card_title"]),
                paragraph(body, styles["small"]),
            ]
        )
    architecture_table = Table([architecture_cells], colWidths=[41 * mm] * 4, rowHeights=[56 * mm])
    architecture_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PALE),
                ("BOX", (0, 0), (-1, -1), 0.7, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 11),
                ("RIGHTPADDING", (0, 0), (-1, -1), 11),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )
    story.extend(
        [
            architecture_table,
            Spacer(1, 8 * mm),
            paragraph("Implementation map", styles["h2"]),
            evidence_table(
                [
                    ["Layer", "Implementation", "Engineering evidence"],
                    ["Research", "Python, pandas, scikit-learn", "Leakage checks, ablation, calibration, error and segment analysis"],
                    ["Product API", "FastAPI, typed schemas, repository boundary", "Role access, tenant scoping, immutable score provenance, audit events"],
                    ["Persistence", "SQLite prototype + PostgreSQL adapter", "52/52 adapter methods and reviewed migration contract"],
                    ["Public demo", "Static HTML/CSS/JavaScript", "Browser-local synthetic API and GitHub Pages deployment"],
                    ["Verification", "unittest + Node smoke workflows", "126 tests plus live API, security, research, and frontend gates"],
                ],
                [27 * mm, 52 * mm, 85 * mm],
                styles,
            ),
            Spacer(1, 7 * mm),
            card(
                "Key boundary",
                "The static demo proves the user journey without receiving personal data. The local FastAPI system proves the product contracts. Neither is presented as a production lending deployment.",
                styles,
                tone="amber",
            ),
            PageBreak(),
        ]
    )

    # Research design
    story.extend(
        [
            section_heading("03", "Research design", "Two experiments, one explicit claim boundary", styles),
            paragraph(
                "Experiment A tests a Pavlodar-oriented product and research workflow on synthetic borrower-level data. Experiment B runs the same evaluation discipline on a real public credit-risk benchmark. They answer different questions and are not blended into one claim.",
                styles["body"],
            ),
            Spacer(1, 4 * mm),
        ]
    )
    experiment_table = Table(
        [
            [paragraph("EXPERIMENT A", styles["eyebrow"]), paragraph("EXPERIMENT B", styles["eyebrow"])],
            [paragraph("Synthetic Pavlodar scaffold", styles["h2"]), paragraph("UCI Default of Credit Card Clients", styles["h2"])],
            [paragraph("5,000 synthetic rows for feature stress tests, product behavior, regional segmentation, and decision-policy research.", styles["body"]), paragraph("30,000 public Taiwan credit-card rows for an external benchmark of ranking, calibration, and error-analysis machinery.", styles["body"])],
            [paragraph("Claim: the system can expose a fragile thin-file signal and support reviewer workflow design.", styles["small"]), paragraph("Claim: the research pipeline operates on a real public dataset. It does not validate Kazakhstan deployment.", styles["small"])],
        ],
        colWidths=[82 * mm, 82 * mm],
    )
    experiment_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), PALE_TEAL),
                ("BACKGROUND", (1, 0), (1, -1), colors.HexColor("#EEF2FA")),
                ("BOX", (0, 0), (-1, -1), 0.7, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 13),
                ("RIGHTPADDING", (0, 0), (-1, -1), 13),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    story.extend(
        [
            experiment_table,
            Spacer(1, 7 * mm),
            paragraph("Evaluation pipeline", styles["h2"]),
        ]
    )
    story.extend(
        bullet_lines(
            [
                "Leakage-like identifiers and target-adjacent fields removed before the primary baseline.",
                "Stratified train/test split plus five-fold cross-validation with fixed random state 42.",
                "Logistic Regression and Random Forest baselines with ROC-AUC, Brier score, F1, precision, and recall.",
                "Feature-group ablation, single-feature proxy audit, calibration curves, and false-positive / false-negative analysis.",
                "Three-zone approve / review / decline policy analysis with segment-level outcomes.",
                "Seeded Monte Carlo portfolio scenarios separated from borrower-level scoring.",
            ],
            styles,
        )
    )
    story.extend(
        [
            Spacer(1, 4 * mm),
            card(
                "Reproducibility contract",
                "Generated artifacts store data label, row count, random state, test size, metric tables, calibration bins, error examples, and chart outputs. The same repository release gate rebuilds and validates the pipeline.",
                styles,
                tone="teal",
            ),
            PageBreak(),
        ]
    )

    # Quantitative evidence
    story.extend(
        [
            section_heading("04", "Quantitative evidence", "Performance is useful; failure analysis is decisive", styles),
            paragraph(
                "The public benchmark shows that the pipeline can rank risk on real public data. The synthetic experiment shows why a strong headline metric must still be challenged by ablation and calibration analysis.",
                styles["body"],
            ),
            Spacer(1, 3 * mm),
            paragraph("Model comparison", styles["h2"]),
            evidence_table(
                [
                    ["Dataset", "Model", "ROC-AUC", "Brier", "F1", "Interpretation"],
                    ["Synthetic", "Logistic Regression", metric(synthetic_lr["test_roc_auc"]), metric(synthetic_lr["test_brier_score"]), metric(synthetic_lr["test_f1"]), "Interpretable API baseline"],
                    ["Synthetic", "Random Forest", metric(synthetic_rf["test_roc_auc"]), metric(synthetic_rf["test_brier_score"]), metric(synthetic_rf["test_f1"]), "Highest synthetic ranking"],
                    ["UCI public", "Logistic Regression", metric(benchmark_lr["test_roc_auc"]), metric(benchmark_lr["test_brier_score"]), metric(benchmark_lr["test_f1"]), "Real public benchmark"],
                    ["UCI public", "Random Forest", metric(benchmark_rf["test_roc_auc"]), metric(benchmark_rf["test_brier_score"]), metric(benchmark_rf["test_f1"]), "Best benchmark result"],
                ],
                [25 * mm, 34 * mm, 19 * mm, 18 * mm, 16 * mm, 52 * mm],
                styles,
            ),
            Spacer(1, 6 * mm),
            paragraph("Calibration views", styles["h2"]),
        ]
    )
    chart_table = Table(
        [
            [
                scaled_image(RESEARCH_DIR / "calibration_curve.png", 78 * mm, 55 * mm),
                scaled_image(BENCHMARK_DIR / "calibration_curve.png", 78 * mm, 55 * mm),
            ],
            [
                paragraph("Synthetic experiment calibration", styles["center"]),
                paragraph("UCI public benchmark calibration", styles["center"]),
            ],
        ],
        colWidths=[82 * mm, 82 * mm],
    )
    chart_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOX", (0, 0), (-1, -1), 0.5, LINE), ("INNERGRID", (0, 0), (-1, -1), 0.5, LINE), ("BACKGROUND", (0, 0), (-1, -1), WHITE), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    story.extend(
        [
            chart_table,
            Spacer(1, 5 * mm),
            paragraph(
                "ROC-AUC measures ranking, while the Brier score and calibration curve test whether probabilities behave like probabilities. Both matter because portfolio simulations consume probability estimates, not only rank order.",
                styles["small"],
            ),
            PageBreak(),
        ]
    )

    # Ablation finding
    story.extend(
        [
            section_heading("05", "Critical finding", "Remove one proxy and the thin-file claim collapses", styles),
            paragraph(
                f"The synthetic Random Forest reaches ROC-AUC {metric(synthetic_rf['test_roc_auc'])}, but falls to {metric(thin_rf['test_roc_auc'])} when late_payment_count is removed. The single feature alone has directional ROC-AUC {metric(proxy['directional_roc_auc'])}. This is the central research result.",
                styles["body"],
            ),
            Spacer(1, 3 * mm),
            scaled_image(RESEARCH_DIR / "ablation_roc_auc.png", 162 * mm, 92 * mm),
            Spacer(1, 5 * mm),
            metric_cards(
                [
                    (metric(synthetic_rf["test_roc_auc"]), "full leakage-safe synthetic RF"),
                    (metric(thin_rf["test_roc_auc"]), "RF without late-payment proxy"),
                    (metric(behavioral_rf["test_roc_auc"]), "behavioral-only RF"),
                    (metric(regional_rf["test_roc_auc"]), "regional-only RF"),
                ],
                styles,
            ),
            Spacer(1, 7 * mm),
            card(
                "Engineering interpretation",
                "The product must not market alternative behavioral data as proven predictive signal. The correct response is to narrow the claim, preserve human review, monitor the proxy, and design a consented local validation plan.",
                styles,
                tone="amber",
            ),
            Spacer(1, 5 * mm),
            paragraph("Why this matters", styles["h2"]),
        ]
    )
    story.extend(
        bullet_lines(
            [
                "A high aggregate metric can be produced by a field that contradicts the intended thin-file use case.",
                "Digital and monetary variables may measure infrastructure and wealth access instead of repayment reliability.",
                "Honest negative results make the next data requirement concrete and prevent unsafe deployment claims.",
            ],
            styles,
        )
    )
    story.append(PageBreak())

    # Decision system + MC
    story.extend(
        [
            section_heading("06", "Decision engineering", "From a score to policy trade-offs and uncertainty", styles),
            paragraph(
                "MicroScore avoids a single binary threshold. A three-zone policy separates auto-approve, manual review, and auto-decline regions, then exposes how each policy changes access and risk. Monte Carlo sits above that policy layer and never changes borrower scores.",
                styles["body"],
            ),
            Spacer(1, 3 * mm),
            paragraph("Deterministic policy comparison", styles["h2"]),
        ]
    )
    policy_data = [["Policy", "Approve", "Review", "Decline", "High-risk approval"]]
    for policy_name in ["lender_protective", "balanced_review", "inclusion_first", "starter_loan_review"]:
        row = select_row(policy_rows, policy=policy_name)
        policy_data.append(
            [
                policy_name.replace("_", " ").title(),
                percent(row["auto_approval_rate"]),
                percent(row["manual_review_rate"]),
                percent(row["auto_decline_rate"]),
                percent(row["high_risk_approval_rate"]),
            ]
        )
    story.extend(
        [
            evidence_table(policy_data, [48 * mm, 26 * mm, 26 * mm, 26 * mm, 38 * mm], styles),
            Spacer(1, 7 * mm),
            paragraph("Monte Carlo uncertainty layer", styles["h2"]),
        ]
    )
    monte_carlo = Table(
        [
            [paragraph("INPUTS", styles["eyebrow"]), paragraph("SIMULATION", styles["eyebrow"]), paragraph("OUTPUTS", styles["eyebrow"])],
            [paragraph("Scored portfolio<br/>Policy thresholds<br/>Interest margin<br/>Loss given default<br/>Operating cost", styles["body"]), paragraph("Seeded paired draws<br/>Shared macro shock<br/>Borrower-level calibration shock<br/>Baseline / adverse / severe<br/>Standard-error diagnostics", styles["body"]), paragraph("Approvals and exposure<br/>Defaults<br/>One-period result distribution<br/>Downside and capital buffer<br/>Risk appetite gate", styles["body"])],
        ],
        colWidths=[54.7 * mm] * 3,
    )
    monte_carlo.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("BACKGROUND", (0, 1), (-1, 1), PALE),
                ("BOX", (0, 0), (-1, -1), 0.7, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 11),
                ("RIGHTPADDING", (0, 0), (-1, -1), 11),
                ("TOPPADDING", (0, 0), (-1, -1), 11),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 11),
            ]
        )
    )
    story.extend(
        [
            monte_carlo,
            Spacer(1, 7 * mm),
            card(
                "Interpretation boundary",
                "These distributions demonstrate a reproducible uncertainty method. They are not forecasts because the borrower probabilities and financial assumptions are not calibrated on local MFI outcomes or verified KZT economics.",
                styles,
                tone="amber",
            ),
            Spacer(1, 5 * mm),
            paragraph("Operational outputs", styles["h2"]),
        ]
    )
    story.extend(
        bullet_lines(
            [
                "Scenario cockpit and policy sweep for paired comparisons under the same seed.",
                "Assumption sensitivity ranking to identify which inputs move downside the most.",
                "Committee brief, pilot risk appetite gate, monitoring plan, and evidence dossier.",
                "Device-local dossier vault for reproducible reviewer packets in the public demo.",
            ],
            styles,
        )
    )
    story.append(PageBreak())

    # Product engineering
    story.extend(
        [
            section_heading("07", "Product engineering", "Three roles connected by one auditable lifecycle", styles),
            paragraph(
                "The product prototype turns research outputs into explicit user responsibilities. Borrowers control submissions, analysts own human review, and administrators inspect governance evidence without exposing raw secrets.",
                styles["body"],
            ),
            Spacer(1, 4 * mm),
        ]
    )
    role_rows = [
        ["Role", "Primary workflow", "Safety and evidence"],
        ["Borrower", "Register, consent, submit, view owned status timeline", "Borrower-safe response projection; no internal score or analyst note leakage"],
        ["MFI analyst", "Triage queue, inspect explanation, review packet, decide", "Lifecycle guards, decision history, model-use notice, tenant-scoped portfolio"],
        ["Administrator", "Manage staff, sessions, model registry, audit and readiness", "MFA prototype, invite hygiene, security evidence room, pre-pilot gate"],
    ]
    story.extend(
        [
            evidence_table(role_rows, [28 * mm, 64 * mm, 72 * mm], styles),
            Spacer(1, 7 * mm),
            paragraph("Security and infrastructure evidence", styles["h2"]),
        ]
    )
    engineering_cards = [
        ("Tenant isolation", "Organization-scoped queue, analytics, exports, simulation registry, and analyst lifecycle."),
        ("Model governance", "Candidate registration, atomic activation, immutable provenance, and stale-score warnings."),
        ("Identity controls", "Expiring invites, one-time token handling, session inventory and revocation, prototype MFA."),
        ("Storage migration", "Reviewed PostgreSQL schema and 52/52 repository adapter methods, while production readiness stays blocked."),
    ]
    engineering_cells = []
    for title, body in engineering_cards:
        engineering_cells.append([paragraph(title, styles["card_title"]), paragraph(body, styles["small"])])
    engineering_table = Table([engineering_cells[:2], engineering_cells[2:]], colWidths=[82 * mm, 82 * mm])
    engineering_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), WHITE),
                ("BOX", (0, 0), (-1, -1), 0.7, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )
    story.extend(
        [
            engineering_table,
            Spacer(1, 7 * mm),
            card(
                "Readiness is a computed state",
                "The admin pre-pilot gate aggregates security, identity, delivery, storage, model, review-flow, privacy, tenant-isolation, and Monte Carlo evidence. It deliberately keeps production_data_allowed=false while blockers remain.",
                styles,
                tone="teal",
            ),
            PageBreak(),
        ]
    )

    # Verification
    story.extend(
        [
            section_heading("08", "Verification", "The release gate is part of the product", styles),
            paragraph(
                "The repository uses a single local and CI release gate. It checks research behavior, API contracts, privacy boundaries, frontend workflows, static-demo parity, storage migration contracts, and live security flows.",
                styles["body"],
            ),
            Spacer(1, 4 * mm),
            metric_cards(
                [
                    ("126", "Python unit and integration tests"),
                    ("7", "major smoke and syntax gates"),
                    ("52 / 52", "PostgreSQL adapter methods"),
                    ("1", "repeatable release command"),
                ],
                styles,
            ),
            Spacer(1, 7 * mm),
            paragraph("Release gate coverage", styles["h2"]),
            evidence_table(
                [
                    ["Gate", "What it proves"],
                    ["Research smoke", "Model training, leakage-safe features, regional analysis, and threshold outputs execute reproducibly"],
                    ["Static demo smoke", "Role flows, privacy guards, model registry, Monte Carlo, tenant isolation, and readiness controls remain aligned"],
                    ["Frontend workflow smoke", "Borrower history, review checklist, decision mutation guards, and terminal lifecycle behavior"],
                    ["PostgreSQL migration smoke", "Schema inventory, JSON mapping, tenant indexes, and repository contract completeness"],
                    ["Live API smoke", "Temporary SQLite end-to-end application scoring and decision history"],
                    ["Live security smoke", "Invite lifecycle, MFA monitoring, sessions, webhook replay protection, and pre-pilot blockers"],
                ],
                [48 * mm, 116 * mm],
                styles,
            ),
            Spacer(1, 7 * mm),
            card(
                "Verified release snapshot",
                "The admissions review release passed all 126 tests plus research, frontend, static-demo, PostgreSQL migration, live API, and live security smoke checks before publication.",
                styles,
                tone="teal",
            ),
            Spacer(1, 6 * mm),
            paragraph("Reproduce locally", styles["h2"]),
            paragraph("powershell -ExecutionPolicy Bypass -File scripts\\check.ps1", styles["quote"]),
            PageBreak(),
        ]
    )

    # Limits and next step
    story.extend(
        [
            section_heading("09", "Conclusion", "What is proven, what is not, and what comes next", styles),
            paragraph(
                "MicroScore demonstrates the engineering of a responsible decision-support system: reproducible research, explicit failure analysis, a typed product API, auditable human review, tenant-aware infrastructure, and uncertainty tooling. It does not demonstrate that the current model is ready to make lending decisions in Kazakhstan.",
                styles["body"],
            ),
            Spacer(1, 4 * mm),
        ]
    )
    conclusion_table = Table(
        [
            [paragraph("PROVEN IN THE PROTOTYPE", styles["eyebrow"]), paragraph("STILL BLOCKED", styles["eyebrow"])],
            [
                bullet_lines(
                    [
                        "End-to-end role workflows",
                        "Reproducible model evaluation",
                        "Public benchmark execution",
                        "Proxy and ablation failure analysis",
                        "Seeded portfolio stress methodology",
                        "Audit and readiness evidence",
                    ],
                    styles,
                ),
                bullet_lines(
                    [
                        "Real Pavlodar predictive validation",
                        "Verified KZT financial assumptions",
                        "Production identity provider and MFA",
                        "External transactional delivery",
                        "Managed PostgreSQL deployment",
                        "Security and privacy review for real data",
                    ],
                    styles,
                ),
            ],
        ],
        colWidths=[82 * mm, 82 * mm],
    )
    conclusion_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), PALE_TEAL),
                ("BACKGROUND", (1, 0), (1, -1), PALE_AMBER),
                ("BOX", (0, 0), (-1, -1), 0.7, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 13),
                ("RIGHTPADDING", (0, 0), (-1, -1), 13),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )
    story.extend(
        [
            conclusion_table,
            Spacer(1, 8 * mm),
            paragraph("Next engineering milestone", styles["h2"]),
            paragraph(
                "Run a consented, privacy-reviewed pilot validation with measured local definitions, recalibrate monetary assumptions in KZT, and compare model and reviewer outcomes over time. Until then, preserve the human-in-the-loop boundary.",
                styles["quote"],
            ),
            Spacer(1, 8 * mm),
        ]
    )
    final_links = Table(
        [
            [
                qr_drawing(LIVE_REVIEW_URL, 30 * mm),
                [
                    paragraph("EXPLORE THE PROJECT", styles["eyebrow"]),
                    paragraph("Live admissions review", styles["card_title"]),
                    paragraph(LIVE_REVIEW_URL, styles["small"]),
                    Spacer(1, 5),
                    paragraph("Source and reproducibility", styles["card_title"]),
                    paragraph(REPOSITORY_URL, styles["small"]),
                ],
            ]
        ],
        colWidths=[40 * mm, 124 * mm],
    )
    final_links.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PALE),
                ("BOX", (0, 0), (-1, -1), 0.7, LINE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 14),
                ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                ("TOPPADDING", (0, 0), (-1, -1), 14),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
            ]
        )
    )
    story.extend(
        [
            final_links,
            Spacer(1, 7 * mm),
            paragraph(
                "Primary evidence sources: generated CSV and PNG artifacts under reports/research-artifacts and reports/benchmark-artifacts; implementation and contracts in the linked repository. UCI source: archive.ics.uci.edu/dataset/350/default+of+credit+card+clients.",
                styles["tiny"],
            ),
        ]
    )
    return story


def build_pdf(output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    styles = make_styles()
    doc = BaseDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=23 * mm,
        rightMargin=23 * mm,
        topMargin=30 * mm,
        bottomMargin=23 * mm,
        title="MicroScore Engineering Case Study",
        author="Alexandr",
        subject="Computer Engineering admissions evidence package",
        creator="MicroScore reproducible report builder",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="case-study", frames=[frame], onPage=page_header_footer)])
    doc.build(build_story(styles))
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the MicroScore admissions engineering case study PDF.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = build_pdf(args.output.resolve())
    print(output)


if __name__ == "__main__":
    main()
