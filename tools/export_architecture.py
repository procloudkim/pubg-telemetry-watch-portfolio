"""Export the project's simple draw.io cells to SVG and a paged HTML print source."""

from html import escape
from pathlib import Path
import re
from urllib.parse import unquote
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def check_image(uri):
    # Exports are opened as HTML; an icon must not execute code or fetch remote content.
    if not uri.startswith("data:image/svg+xml,"):
        raise ValueError("Only embedded SVG icons are supported")
    body = unquote(uri.split(",", 1)[1])
    if any(marker in body.lower() for marker in ("<!doctype", "<!entity", "<?xml-stylesheet")):
        raise ValueError("Active SVG content is forbidden")
    allowed = {
        "svg",
        "g",
        "path",
        "circle",
        "rect",
        "defs",
        "clipPath",
        "polygon",
        "polyline",
        "line",
        "ellipse",
        "linearGradient",
        "radialGradient",
        "stop",
        "use",
        "title",
        "desc",
        "mask",
        "style",
    }
    for element in ET.fromstring(body).iter():
        if element.tag.split("}")[-1] not in allowed:
            raise ValueError("Active SVG content is forbidden")
        if element.tag.split("}")[-1] == "style":
            # The supplied Google SVG uses class colors; allow only this non-fetching CSS grammar.
            colors = (
                r"(?:\s*\.[A-Za-z_][\w-]*\s*\{\s*fill\s*:\s*(?:none|#[0-9a-fA-F]{6})\s*;\s*\}\s*)+"
            )
            if len(element) or not re.fullmatch(colors, element.text or ""):
                raise ValueError("Only static SVG class colors are supported")
        for key, value in element.attrib.items():
            name = key.split("}")[-1].lower()
            if name.startswith("on") or name in {"style", "base"} or "\\" in value:
                raise ValueError("Active SVG attributes are forbidden")
            if name == "href" and not value.startswith("#"):
                raise ValueError("Active SVG attributes are forbidden")
            if "url(" in value.lower() and not re.fullmatch(r"url\(#[\w.-]+\)", value):
                raise ValueError("External SVG reference is forbidden")


def export(source=ROOT / "docs/architecture/operations.drawio"):
    source = Path(source)
    pages = []
    identifiers = set()
    for diagram in ET.parse(source).getroot().findall("diagram"):
        identifier = diagram.get("id", "")
        # Editable document IDs become filenames, so reject paths and duplicate output names.
        if not re.fullmatch(r"D[0-9]{2}", identifier) or identifier in identifiers:
            raise ValueError("Invalid or duplicate diagram ID")
        identifiers.add(identifier)
        cells = diagram.findall("./mxGraphModel/root/mxCell")
        vertices = {c.attrib["id"]: c for c in cells if c.get("vertex") == "1"}
        out = [
            '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="740" viewBox="0 0 1200 740">',
            '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0L8 4L0 8" fill="#64748b"/></marker></defs>',
            '<rect width="1200" height="740" fill="#f8fafc"/>',
            '<style>text {font-family:"Noto Sans CJK KR",UnDotum,sans-serif;fill:#162b44} .small {font-size:14px}</style>',
        ]
        for cell in cells:
            if cell.get("edge") != "1":
                continue
            a, b = vertices[cell.get("source")], vertices[cell.get("target")]
            ga, gb = a.find("mxGeometry"), b.find("mxGeometry")
            ax, ay, aw, ah = [float(ga.get(k)) for k in ("x", "y", "width", "height")]
            bx, by, bw, bh = [float(gb.get(k)) for k in ("x", "y", "width", "height")]
            if ay == by:
                start, end = (ax + aw, ay + ah / 2), (bx, by + bh / 2)
            elif ay < by:
                start, end = (ax + aw / 2, ay + ah), (bx + bw / 2, by)
            else:
                start, end = (ax + aw / 2, ay), (bx + bw / 2, by + bh)
            dashed = ' stroke-dasharray="6 4"' if "dashed=1" in cell.get("style", "") else ""
            out.append(
                f'<path d="M{start[0]} {start[1]} L{end[0]} {end[1]}" fill="none" stroke="#64748b" stroke-width="2" marker-end="url(#arrow)"{dashed}/>'
            )
            if cell.get("value"):
                out.append(
                    f'<text class="small" text-anchor="middle" x="{(start[0] + end[0]) / 2}" y="{(start[1] + end[1]) / 2 - 8}">{escape(cell.get("value"))}</text>'
                )
        for cell in vertices.values():
            g = cell.find("mxGeometry")
            x, y, w, h = [float(g.get(k)) for k in ("x", "y", "width", "height")]
            if not (0 <= x < x + w <= 1200 and 0 <= y < y + h <= 740):
                raise ValueError("Cell outside page bounds")
            style = dict(
                piece.split("=", 1) for piece in cell.get("style", "").split(";") if "=" in piece
            )
            color = style.get("fillColor", "#ffffff")
            dashed = ' stroke-dasharray="6 4"' if style.get("dashed") == "1" else ""
            icon = style.get("image")
            if icon:
                check_image(icon)
                out.append(
                    f'<image href="{escape(icon, quote=True)}" x="{x}" y="{y}" width="{w}" height="{h}"/>'
                )
                continue
            is_text = cell.get("style", "").startswith("text;")
            if not is_text:
                if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
                    raise ValueError("Only hex fill colors are supported")
                out.append(
                    f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{color}" stroke="#8095ab"{dashed}/>'
                )
            lines = cell.get("value", "").split("\n")
            font = int(style.get("fontSize", 17))
            if font < 1 or len(lines) * (font + 8) + (0 if is_text else 24) > h:
                raise ValueError("Text exceeds cell height")
            for i, line in enumerate(lines):
                left = int(style.get("spacingLeft", 0 if is_text else 16))
                weight = "700" if style.get("fontStyle") == "1" else "400"
                out.append(
                    f'<text font-size="{font}" font-weight="{weight}" x="{x + left}" y="{y + font + (5 if is_text else 15) + i * (font + 8)}">{escape(line)}</text>'
                )
        out.append("</svg>")
        svg = "\n".join(out)
        name = identifier + ".svg"
        (source.parent / name).write_text(svg, encoding="utf-8")
        pages.append(f"<section>{svg}</section>")
    html = (
        '<!doctype html><meta charset="utf-8"><title>Operations architecture</title><style>@page{size:1200px 740px;margin:0}body{margin:0}section{width:1200px;height:740px;break-after:page}svg{display:block}</style>'
        + "".join(pages)
    )
    (source.parent / "operations-print.html").write_text(html, encoding="utf-8")
    print(f"Exported {len(pages)} pages from {source.name}")


if __name__ == "__main__":
    export()
