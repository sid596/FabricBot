"""Render the existing deterministic quotation output without recalculating money."""
from datetime import datetime
from io import BytesIO
from pathlib import Path
import threading
from uuid import uuid4
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable

_font_lock = threading.Lock()


class QuotationReply(str):
    """Completed quotation, distinct from clarification/error text."""


def render_quotation_pdf(quotation, *, reference=None, created_at=None):
    if not isinstance(quotation, QuotationReply):
        raise ValueError("Only completed quotations can be rendered")
    with _font_lock:
        if "NotoSans" not in pdfmetrics.getRegisteredFontNames():
            fonts = Path(__file__).parent / "assets" / "fonts"
            pdfmetrics.registerFont(TTFont("NotoSans", str(fonts / "NotoSans-Regular.ttf")))
            pdfmetrics.registerFont(TTFont("NotoSans-Bold", str(fonts / "NotoSans-Bold.ttf")))
    reference = reference or uuid4().hex[:10].upper()
    created_at = created_at or datetime.now().astimezone()
    ink, accent = colors.HexColor("#223D3A"), colors.HexColor("#D9E6E1")
    body = ParagraphStyle("Body", fontName="NotoSans", fontSize=9, leading=14, textColor=ink)
    heading = ParagraphStyle("Heading", parent=body, fontName="NotoSans-Bold", fontSize=11, leading=16, spaceBefore=14, spaceAfter=6, keepWithNext=True)
    title = ParagraphStyle("Title", parent=heading, fontSize=26, leading=32)
    value_style = ParagraphStyle("Value", parent=body, alignment=TA_RIGHT)
    note_style = ParagraphStyle("Note", parent=body, fontSize=8, leading=12, textColor=colors.HexColor("#526762"))
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=42, leftMargin=42,
                            topMargin=38, bottomMargin=45, title=f"Angie quotation {reference}", author="Angie")
    story = [Paragraph("ANGIE", heading), Paragraph("Your quotation", title),
             Paragraph(escape(f"Reference {reference}  |  {created_at:%d %b %Y}"), note_style),
             Spacer(1, 12), HRFlowable(width="100%", thickness=1, color=accent), Spacer(1, 8)]
    rows = []

    def flush():
        if not rows:
            return
        table = Table(rows[:], colWidths=[doc.width * .43, doc.width * .57], hAlign="LEFT")
        table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 9),
            ("RIGHTPADDING", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.HexColor("#F3F7F5"), colors.white]),
        ]))
        story.append(table)
        rows.clear()

    for raw in str(quotation).splitlines():
        line = raw.strip()
        if not line or line == "*QUOTATION*" or set(line) <= {"━"}:
            continue
        bold = line.startswith("*") and line.endswith("*")
        line = line.strip("*")
        if bold:
            flush()
            story.append(Paragraph(escape(line), heading))
        elif line.startswith("Assumed "):
            flush()
            story.extend([Spacer(1, 8), Paragraph(escape(line), note_style)])
        elif ":" in line:
            label, value = line.split(":", 1)
            rows.append([Paragraph(escape(label), body), Paragraph(escape(value.strip()), value_style)])
        else:
            flush()
            story.append(Paragraph(escape(line), body))
    flush()

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont("NotoSans", 8)
        canvas.setFillColor(ink)
        canvas.drawString(42, 24, f"Angie | {reference}")
        canvas.drawRightString(A4[0] - 42, 24, f"Page {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()
