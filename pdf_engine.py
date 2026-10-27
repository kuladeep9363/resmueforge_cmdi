"""ResumeForge's portable HTML-to-PDF renderer.

The command boundary in app.py is intentionally vulnerable for the local CTF.
This module creates a designed, vector-based resume PDF from structured fields
embedded in the rendered HTML template.
"""
from __future__ import annotations

import json
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase.pdfmetrics import stringWidth
    from reportlab.pdfgen import canvas
except ImportError as exc:  # clear diagnostic shown in the app's STDERR section
    raise SystemExit(
        "PDF_ENGINE_ERROR: ReportLab is required. Run: python -m pip install -r requirements.txt"
    ) from exc


class ResumeMetadataParser(HTMLParser):
    """Read the data-pdf-* attributes emitted by templates/resume.html."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.metadata: dict[str, Any] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value for key, value in attrs if value is not None}
        for key, value in values.items():
            if key.startswith("data-pdf-"):
                self.metadata[key.removeprefix("data-pdf-")] = value


def extract_metadata(html: str) -> dict[str, Any]:
    parser = ResumeMetadataParser()
    parser.feed(html)
    data = parser.metadata
    for field in ("skills", "projects"):
        try:
            data[field] = json.loads(data.get(field, "[]"))
        except (TypeError, json.JSONDecodeError):
            data[field] = []
    return data


def clean(value: Any) -> str:
    """Normalize to printable Latin text supported by standard PDF fonts."""
    return str(value or "").replace("\u2014", "-").replace("\u2013", "-").replace("\u2022", "- ").encode("cp1252", "replace").decode("cp1252")


def wrap_text(text: str, font: str, size: float, max_width: float) -> list[str]:
    text = " ".join(clean(text).split())
    if not text:
        return []
    words = text.split(" ")
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if stringWidth(candidate, font, size) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def draw_wrapped(c: canvas.Canvas, text: str, x: float, y: float, width: float,
                 font: str = "Helvetica", size: float = 9, leading: float | None = None,
                 color: colors.Color = colors.HexColor("#45566d"), max_lines: int | None = None) -> float:
    leading = leading or size * 1.45
    lines = wrap_text(text, font, size, width)
    if max_lines is not None and len(lines) > max_lines:
        lines = lines[:max_lines]
        if lines:
            last = lines[-1]
            while last and stringWidth(last + "...", font, size) > width:
                last = last[:-1]
            lines[-1] = last.rstrip() + "..."
    c.setFillColor(color)
    c.setFont(font, size)
    for line in lines:
        c.drawString(x, y, line)
        y -= leading
    return y


def section_heading(c: canvas.Canvas, label: str, x: float, y: float, width: float) -> float:
    navy = colors.HexColor("#153454")
    teal = colors.HexColor("#19b8a7")
    c.setFillColor(navy)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(x, y, clean(label).upper())
    c.setFillColor(teal)
    c.roundRect(x, y - 8, 22, 2.5, 1.2, fill=1, stroke=0)
    c.setStrokeColor(colors.HexColor("#dce5ee"))
    c.setLineWidth(0.7)
    c.line(x + 30, y - 6.5, x + width, y - 6.5)
    return y - 25


def create_resume_pdf(data: dict[str, Any], output_path: Path) -> None:
    page_w, page_h = A4
    navy = colors.HexColor("#10243b")
    navy_mid = colors.HexColor("#173e65")
    teal = colors.HexColor("#42d6c3")
    ink = colors.HexColor("#26384c")
    muted = colors.HexColor("#687b90")
    pale = colors.HexColor("#f2f6fa")
    line = colors.HexColor("#dce5ee")
    white = colors.white

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(output_path), pagesize=A4, pageCompression=1)
    pdf.setTitle(f"{clean(data.get('name', 'Student'))} - ResumeForge")
    pdf.setAuthor("ResumeForge - Campus Placement Office")

    # Header band and subtle accent stripe.
    header_h = 172
    pdf.setFillColor(navy)
    pdf.rect(0, page_h - header_h, page_w, header_h, fill=1, stroke=0)
    pdf.setFillColor(navy_mid)
    pdf.circle(page_w + 2, page_h - 16, 122, fill=1, stroke=0)
    pdf.setStrokeColor(colors.Color(1, 1, 1, alpha=0.11))
    pdf.setLineWidth(1)
    pdf.circle(page_w + 2, page_h - 16, 88, fill=0, stroke=1)
    pdf.circle(page_w + 2, page_h - 16, 61, fill=0, stroke=1)
    pdf.setFillColor(teal)
    pdf.rect(0, page_h - header_h - 3, page_w, 3, fill=1, stroke=0)

    left = 39
    name = clean(data.get("name", "Student Name"))
    pdf.setFillColor(teal)
    pdf.setFont("Helvetica-Bold", 7.6)
    pdf.drawString(left, page_h - 34, "RESUMEFORGE  /  STUDENT PORTFOLIO")
    name_lines = wrap_text(name, "Helvetica-Bold", 25, 420)
    name_y = page_h - 68
    pdf.setFillColor(white)
    pdf.setFont("Helvetica-Bold", 25)
    for line_text in name_lines[:2]:
        pdf.drawString(left, name_y, line_text)
        name_y -= 29

    branch = clean(data.get("branch", ""))
    roll = clean(data.get("roll", ""))
    pdf.setFillColor(colors.HexColor("#c7d8e8"))
    pdf.setFont("Helvetica", 9.4)
    pdf.drawString(left, name_y - 1, f"{branch}  |  Roll No. {roll}")

    contact_y = name_y - 21
    pdf.setFillColor(colors.HexColor("#e4edf6"))
    pdf.setFont("Helvetica", 8.1)
    contact = f"{clean(data.get('email', ''))}     |     {clean(data.get('phone', ''))}"
    pdf.drawString(left, contact_y, contact[:115])

    # Prepared-for panel within the header.
    panel_y = page_h - header_h + 17
    pdf.setFillColor(colors.Color(1, 1, 1, alpha=0.07))
    pdf.roundRect(left, panel_y, page_w - 2 * left, 35, 5, fill=1, stroke=0)
    pdf.setFillColor(teal)
    pdf.roundRect(left, panel_y, 3, 35, 1.3, fill=1, stroke=0)
    pdf.setFillColor(colors.HexColor("#a9bfd5"))
    pdf.setFont("Helvetica-Bold", 6.7)
    pdf.drawString(left + 13, panel_y + 22, "PREPARED FOR")
    company = clean(data.get("company", "Target Company"))
    pdf.setFillColor(white)
    pdf.setFont("Helvetica-Bold", 10.5)
    company_lines = wrap_text(company, "Helvetica-Bold", 10.5, page_w - 2 * left - 26)
    pdf.drawString(left + 13, panel_y + 8, company_lines[0][:100] if company_lines else "Target Company")

    # Content columns.
    content_top = page_h - header_h - 24
    footer_y = 34
    sidebar_x, sidebar_w = 35, 150
    sidebar_bottom = footer_y + 17
    sidebar_h = content_top - sidebar_bottom
    pdf.setFillColor(pale)
    pdf.roundRect(sidebar_x, sidebar_bottom, sidebar_w, sidebar_h, 7, fill=1, stroke=0)
    main_x = 208
    main_w = page_w - main_x - 38

    sy = content_top - 24
    pad_x = sidebar_x + 13
    inner_w = sidebar_w - 26
    sy = section_heading(pdf, "Contact", pad_x, sy, inner_w)
    for label, value in (("EMAIL", data.get("email", "")), ("PHONE", data.get("phone", "")), ("STUDENT ID", roll)):
        pdf.setFillColor(muted)
        pdf.setFont("Helvetica-Bold", 6.5)
        pdf.drawString(pad_x, sy, label)
        sy -= 11
        sy = draw_wrapped(pdf, str(value), pad_x, sy, inner_w, font="Helvetica", size=7.6,
                          leading=10, color=ink, max_lines=3) - 8

    sy = section_heading(pdf, "Technical Skills", pad_x, sy, inner_w)
    skills = data.get("skills", [])
    if not isinstance(skills, list):
        skills = []
    chip_x = pad_x
    chip_y = sy - 1
    chip_h = 19
    for skill in skills[:12]:
        label = clean(skill)
        label_w = min(stringWidth(label, "Helvetica-Bold", 7.1) + 15, inner_w)
        if chip_x + label_w > pad_x + inner_w:
            chip_x = pad_x
            chip_y -= chip_h + 5
        pdf.setFillColor(white)
        pdf.setStrokeColor(colors.HexColor("#d9e4ef"))
        pdf.roundRect(chip_x, chip_y - 4, label_w, chip_h, 4, fill=1, stroke=1)
        pdf.setFillColor(colors.HexColor("#2a537c"))
        pdf.setFont("Helvetica-Bold", 7.1)
        pdf.drawString(chip_x + 7, chip_y + 3, label[:22])
        chip_x += label_w + 5
    sy = chip_y - chip_h - 14 if skills else sy - 5

    sy = section_heading(pdf, "Education", pad_x, sy, inner_w)
    sy = draw_wrapped(pdf, branch, pad_x, sy, inner_w, font="Helvetica-Bold", size=8.1,
                      leading=11, color=ink, max_lines=4)
    sy -= 2
    sy = draw_wrapped(pdf, "Undergraduate Student", pad_x, sy, inner_w, size=7.1,
                      leading=10, color=muted) - 5
    cgpa = clean(data.get("cgpa", ""))
    badge_text = f"CGPA  {cgpa} / 10"
    badge_w = min(stringWidth(badge_text, "Helvetica-Bold", 7.6) + 16, inner_w)
    pdf.setFillColor(colors.HexColor("#dff8f3"))
    pdf.roundRect(pad_x, sy - 12, badge_w, 20, 4, fill=1, stroke=0)
    pdf.setFillColor(colors.HexColor("#11665d"))
    pdf.setFont("Helvetica-Bold", 7.6)
    pdf.drawString(pad_x + 8, sy - 5, badge_text)

    # Main column: profile and project descriptions.
    my = content_top - 8
    my = section_heading(pdf, "Professional Profile", main_x, my, main_w)
    my = draw_wrapped(pdf, str(data.get("summary", "")), main_x, my, main_w,
                      font="Helvetica", size=9, leading=13.2, color=muted, max_lines=6)
    my -= 16
    my = section_heading(pdf, "Selected Projects", main_x, my, main_w)

    projects = data.get("projects", [])
    if not isinstance(projects, list):
        projects = []
    for index, project in enumerate(projects[:4]):
        if not isinstance(project, dict):
            continue
        title = clean(project.get("project_title", "Project"))
        summary = clean(project.get("project_summary", ""))
        # A numbered accent marker keeps the project list easy to scan.
        pdf.setFillColor(colors.HexColor("#e0f7f2"))
        pdf.circle(main_x + 4, my + 1, 6, fill=1, stroke=0)
        pdf.setFillColor(colors.HexColor("#16877c"))
        pdf.setFont("Helvetica-Bold", 6.2)
        pdf.drawCentredString(main_x + 4, my - 1.2, str(index + 1))
        tx = main_x + 16
        tw = main_w - 12
        pdf.setFillColor(colors.HexColor("#1d3d5c"))
        pdf.setFont("Helvetica-Bold", 9.3)
        title_lines = wrap_text(title, "Helvetica-Bold", 9.3, tw)
        for title_line in title_lines[:2]:
            pdf.drawString(tx, my, title_line)
            my -= 12
        my = draw_wrapped(pdf, summary, tx, my - 1, tw, font="Helvetica", size=8.3,
                          leading=11.5, color=muted, max_lines=4)
        my -= 15

    # Footer kept consistent and deliberately low-profile.
    pdf.setStrokeColor(line)
    pdf.setLineWidth(0.7)
    pdf.line(38, footer_y + 7, page_w - 38, footer_y + 7)
    pdf.setFillColor(colors.HexColor("#7f8da0"))
    pdf.setFont("Helvetica-Bold", 6.3)
    pdf.drawString(39, footer_y - 5, "RESUMEFORGE  |  CAMPUS PLACEMENT OFFICE")
    pdf.setFont("Helvetica", 6.3)
    footer_company = company[:42]
    pdf.drawRightString(page_w - 39, footer_y - 5, f"Prepared for {footer_company}")

    pdf.showPage()
    pdf.save()


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: pdf_engine.py INPUT.html OUTPUT.pdf", file=sys.stderr)
        return 2

    html_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    if not html_path.is_file():
        print(f"PDF_ENGINE_ERROR: input file not found: {html_path}", file=sys.stderr)
        return 1

    try:
        metadata = extract_metadata(html_path.read_text(encoding="utf-8"))
        if not metadata.get("name"):
            print("PDF_ENGINE_ERROR: resume fields were not found in the HTML template", file=sys.stderr)
            return 1
        create_resume_pdf(metadata, output_path)
        print(f"PDF_ENGINE: converted {html_path.name} -> {output_path.name}")
        print(f"PDF_ENGINE: wrote {output_path.stat().st_size} bytes")
        print("PDF_ENGINE: rendered styled A4 resume with header, sections, sidebar, and footer")
        return 0
    except Exception as exc:
        print(f"PDF_ENGINE_ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
