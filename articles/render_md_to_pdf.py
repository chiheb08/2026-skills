import os
import re
from dataclasses import dataclass
from typing import List, Optional

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

# Basic markdown patterns we support (enough for the docs in this repo)
IMAGE_RE = re.compile(r"^!\[(?P<alt>.*)\]\((?P<path>.+)\)\s*$")
HR_RE = re.compile(r"^\s*---\s*$")
H1_RE = re.compile(r"^#\s+(.+)\s*$")
H2_RE = re.compile(r"^##\s+(.+)\s*$")
H3_RE = re.compile(r"^###\s+(.+)\s*$")
QUOTE_RE = re.compile(r"^>\s+(.+)\s*$")
BULLET_RE = re.compile(r"^-\s+(.+)\s*$")
NUM_RE = re.compile(r"^(\d+)\.\s+(.+)\s*$")
TOC_RE = re.compile(r"^\[\[TOC\]\]\s*$")


def _md_inline_to_html(text: str) -> str:
    """
    Convert a small subset of markdown inline syntax to ReportLab Paragraph HTML.
    - **bold** -> <b>
    - `code` -> <font face="Courier">
    - strip simple LaTeX inline wrappers \( \)
    """
    # strip \( ... \) wrappers used in one place in the article
    text = text.replace("\\(", "").replace("\\)", "")

    # code spans
    def repl_code(m):
        inner = m.group(1)
        inner = inner.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return f'<font face="Courier">{inner}</font>'

    text = re.sub(r"`([^`]+)`", repl_code, text)

    # bold
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    return text


@dataclass
class Block:
    kind: str
    text: Optional[str] = None
    alt: Optional[str] = None
    path: Optional[str] = None
    items: Optional[List[str]] = None
    level: Optional[int] = None


def _parse_blocks(lines: List[str]) -> List[Block]:
    """
    Parse markdown into blocks so we can render real paragraphs (not line-by-line),
    plus consistent lists/quotes/images.
    """
    blocks: List[Block] = []
    i = 0
    n = len(lines)

    def line_at(idx: int) -> str:
        return lines[idx].rstrip("\n").rstrip("\r")

    while i < n:
        line = line_at(i)

        if not line.strip():
            i += 1
            continue

        if HR_RE.match(line):
            blocks.append(Block(kind="hr"))
            i += 1
            continue

        if TOC_RE.match(line.strip()):
            blocks.append(Block(kind="toc"))
            i += 1
            continue

        m = IMAGE_RE.match(line.strip())
        if m:
            blocks.append(Block(kind="image", alt=m.group("alt").strip(), path=m.group("path").strip()))
            i += 1
            continue

        m = H1_RE.match(line)
        if m:
            blocks.append(Block(kind="h1", text=m.group(1).strip()))
            i += 1
            continue

        m = H2_RE.match(line)
        if m:
            blocks.append(Block(kind="h2", text=m.group(1).strip()))
            i += 1
            continue

        m = H3_RE.match(line)
        if m:
            blocks.append(Block(kind="h3", text=m.group(1).strip()))
            i += 1
            continue

        # blockquote: merge consecutive quote lines
        m = QUOTE_RE.match(line)
        if m:
            qlines = [m.group(1).strip()]
            i += 1
            while i < n:
                m2 = QUOTE_RE.match(line_at(i))
                if not m2:
                    break
                qlines.append(m2.group(1).strip())
                i += 1
            blocks.append(Block(kind="quote", text=" ".join(qlines)))
            continue

        # bullets: merge consecutive bullet lines
        m = BULLET_RE.match(line)
        if m:
            items = [m.group(1).strip()]
            i += 1
            while i < n:
                m2 = BULLET_RE.match(line_at(i))
                if not m2:
                    break
                items.append(m2.group(1).strip())
                i += 1
            blocks.append(Block(kind="bullets", items=items))
            continue

        # numbered: merge consecutive numbered lines
        m = NUM_RE.match(line)
        if m:
            items = [f"{m.group(1)}. {m.group(2).strip()}"]
            i += 1
            while i < n:
                m2 = NUM_RE.match(line_at(i))
                if not m2:
                    break
                items.append(f"{m2.group(1)}. {m2.group(2).strip()}")
                i += 1
            blocks.append(Block(kind="numbered", items=items))
            continue

        # paragraph: merge consecutive plain lines into one paragraph
        plines = [line.strip()]
        i += 1
        while i < n:
            nxt = line_at(i)
            if not nxt.strip():
                break
            if any(
                r.match(nxt.strip())
                for r in [HR_RE, IMAGE_RE, H1_RE, H2_RE, H3_RE, QUOTE_RE, BULLET_RE, NUM_RE]
            ):
                break
            plines.append(nxt.strip())
            i += 1
        blocks.append(Block(kind="p", text=" ".join(plines)))

    return blocks


def render(md_path: str, pdf_path: str):
    with open(md_path, "r", encoding="utf-8") as f:
        lines = [ln.rstrip("\n") for ln in f]

    blocks = _parse_blocks(lines)
    base_dir = os.path.dirname(md_path)
    toc_titles = [b.text for b in blocks if b.kind == "h2" and (b.text or "").strip().lower() != "table of contents"]

    class DocWithToc(SimpleDocTemplate):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._heading_count = 0

        def beforeDocument(self):
            # multiBuild renders multiple passes; reset so bookmark ids stay stable.
            self._heading_count = 0

        def afterFlowable(self, flowable):
            # Register headings for TOC + PDF outline/bookmarks
            if isinstance(flowable, Paragraph) and flowable.style.name in {"H1", "H2", "H3"}:
                level_map = {"H1": 0, "H2": 1, "H3": 2}
                level = level_map[flowable.style.name]
                text = flowable.getPlainText()

                self._heading_count += 1
                key = f"h{level+1}-{self._heading_count}"

                # clickable destination + outline
                self.canv.bookmarkPage(key)
                self.canv.addOutlineEntry(text, key, level=level, closed=False)

                # TOC entry (level, text, pageNum, key)
                # We rely on the PDF outline for navigation; the in-document TOC is rendered as plain titles (no page numbers).
                pass

    doc = DocWithToc(
        pdf_path,
        pagesize=letter,
        leftMargin=0.85 * inch,
        rightMargin=0.85 * inch,
        topMargin=0.85 * inch,
        bottomMargin=0.85 * inch,
        title=os.path.basename(md_path),
    )

    styles = getSampleStyleSheet()

    body = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=11,
        leading=15,
        spaceAfter=10,
    )
    h1 = ParagraphStyle(
        "H1",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        spaceBefore=4,
        spaceAfter=14,
    )
    h2 = ParagraphStyle(
        "H2",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=19,
        spaceBefore=12,
        spaceAfter=8,
    )
    h3 = ParagraphStyle(
        "H3",
        parent=styles["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=12.5,
        leading=16,
        spaceBefore=10,
        spaceAfter=6,
    )
    quote = ParagraphStyle(
        "Quote",
        parent=body,
        leftIndent=14,
        borderPadding=8,
        spaceBefore=2,
        spaceAfter=12,
        textColor="#333333",
        backColor="#F2F2F2",
    )
    caption = ParagraphStyle(
        "Caption",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=9.5,
        leading=12,
        textColor="#333333",
        spaceBefore=4,
        spaceAfter=10,
        alignment=1,  # center
    )

    story = []

    for b in blocks:
        if b.kind == "hr":
            story.append(Spacer(1, 6))
            story.append(
                Paragraph('<font color="#BBBBBB">________________________________________</font>', styles["Normal"])
            )
            story.append(Spacer(1, 10))
            continue

        if b.kind == "h1":
            story.append(Paragraph(_md_inline_to_html(b.text or ""), h1))
            continue
        if b.kind == "h2":
            story.append(Paragraph(_md_inline_to_html(b.text or ""), h2))
            continue
        if b.kind == "h3":
            story.append(Paragraph(_md_inline_to_html(b.text or ""), h3))
            continue

        if b.kind == "toc":
            story.append(Spacer(1, 6))
            items = [ListItem(Paragraph(_md_inline_to_html(t), body), leftIndent=10) for t in toc_titles]
            story.append(ListFlowable(items, bulletType="bullet", leftIndent=18, bulletFontName="Helvetica"))
            story.append(Spacer(1, 10))
            continue

        if b.kind == "p":
            story.append(Paragraph(_md_inline_to_html(b.text or ""), body))
            continue

        if b.kind == "quote":
            story.append(Paragraph(_md_inline_to_html(b.text or ""), quote))
            continue

        if b.kind == "bullets":
            items = [ListItem(Paragraph(_md_inline_to_html(it), body), leftIndent=10) for it in (b.items or [])]
            story.append(ListFlowable(items, bulletType="bullet", leftIndent=18, bulletFontName="Helvetica"))
            story.append(Spacer(1, 8))
            continue

        if b.kind == "numbered":
            items = [ListItem(Paragraph(_md_inline_to_html(it), body), leftIndent=10) for it in (b.items or [])]
            story.append(ListFlowable(items, bulletType="1", leftIndent=18))
            story.append(Spacer(1, 8))
            continue

        if b.kind == "image":
            rel = (b.path or "").strip()
            img_path = rel if os.path.isabs(rel) else os.path.join(base_dir, rel)
            img_path = os.path.normpath(img_path)

            if not os.path.exists(img_path):
                story.append(Paragraph(_md_inline_to_html(f"[Missing image: {rel}]"), body))
                continue

            img = Image(img_path)
            avail_w = doc.width
            if img.imageWidth > 0:
                scale = avail_w / float(img.imageWidth)
                img.drawWidth = avail_w
                img.drawHeight = img.imageHeight * scale
            img.hAlign = "CENTER"

            story.append(Spacer(1, 6))
            story.append(img)
            if b.alt:
                story.append(Paragraph(_md_inline_to_html(b.alt), caption))
            else:
                story.append(Spacer(1, 10))
            continue

    def on_page(canv, doc_):
        canv.saveState()
        canv.setFont("Helvetica", 9)
        canv.setFillColorRGB(0.4, 0.4, 0.4)
        canv.drawRightString(doc_.pagesize[0] - doc_.rightMargin, 0.55 * inch, f"Page {canv.getPageNumber()}")
        canv.restoreState()

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)


if __name__ == "__main__":
    md_path = "/Users/chihebmhamdi/Desktop/2026/articles/stats-for-data-engineers.md"
    pdf_path = "/Users/chihebmhamdi/Desktop/2026/articles/stats-for-data-engineers.pdf"
    render(md_path, pdf_path)
    print(f"Rendered PDF -> {pdf_path} ({os.path.getsize(pdf_path)} bytes)")

