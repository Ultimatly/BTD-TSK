from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\simsun.ttc",
]


def get_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def parse_style(style: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in style.split(";"):
        if "=" in item:
            k, v = item.split("=", 1)
            out[k] = v
        elif item:
            out[item] = "1"
    return out


def text_size(draw: ImageDraw.ImageDraw, text: str, font) -> tuple[int, int]:
    bbox = draw.multiline_textbbox((0, 0), text, font=font, align="center", spacing=4)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> str:
    if not text:
        return ""
    if "\n" in text:
        return "\n".join(wrap_text(draw, line, font, max_width).split("\n") for line in text.split("\n"))
    chars = list(text)
    lines: list[str] = []
    cur = ""
    for ch in chars:
        test = cur + ch
        w, _ = text_size(draw, test, font)
        if cur and w > max_width:
            lines.append(cur)
            cur = ch
        else:
            cur = test
    if cur:
        lines.append(cur)
    return "\n".join(lines)


def center(rect):
    x, y, w, h = rect
    return x + w / 2, y + h / 2


def border_point(rect, shape: str, target: tuple[float, float]) -> tuple[float, float]:
    x, y, w, h = rect
    cx, cy = center(rect)
    tx, ty = target
    dx, dy = tx - cx, ty - cy
    if dx == 0 and dy == 0:
        return cx, cy

    if shape == "ellipse":
        a = w / 2
        b = h / 2
        scale = 1 / math.sqrt((dx * dx) / (a * a) + (dy * dy) / (b * b))
        return cx + dx * scale, cy + dy * scale

    if shape == "rhombus":
        a = w / 2
        b = h / 2
        scale = 1 / (abs(dx) / a + abs(dy) / b)
        return cx + dx * scale, cy + dy * scale

    # rectangle
    if abs(dx) * h > abs(dy) * w:
        px = cx + (w / 2 if dx > 0 else -w / 2)
        py = cy + dy * (abs(px - cx) / abs(dx))
    else:
        py = cy + (h / 2 if dy > 0 else -h / 2)
        px = cx + dx * (abs(py - cy) / abs(dy))
    return px, py


def draw_arrow_head(draw: ImageDraw.ImageDraw, p1, p2, color, width=4):
    angle = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
    size = 14
    left = (p2[0] - size * math.cos(angle) + size * 0.45 * math.sin(angle),
            p2[1] - size * math.sin(angle) - size * 0.45 * math.cos(angle))
    right = (p2[0] - size * math.cos(angle) - size * 0.45 * math.sin(angle),
             p2[1] - size * math.sin(angle) + size * 0.45 * math.cos(angle))
    draw.polygon([p2, left, right], fill=color)


X_SCALE = 2.0
Y_SCALE = 1.38
MARGIN_X = 70
MARGIN_Y = 50


def sx(x: float) -> float:
    return x * X_SCALE + MARGIN_X


def sy(y: float) -> float:
    return y * Y_SCALE + MARGIN_Y


def render_drawio(drawio_path: Path, png_path: Path):
    root = ET.fromstring(drawio_path.read_text(encoding="utf-8"))
    mx_root = root.find(".//root")
    if mx_root is None:
        raise ValueError("Invalid drawio file")

    cells = {}
    for cell in mx_root.findall("mxCell"):
        cid = cell.attrib.get("id")
        if cid:
            cells[cid] = cell

    vertices = {}
    edges = []
    max_x = max_y = 0

    for cid, cell in cells.items():
        geo = cell.find("mxGeometry")
        if cell.attrib.get("vertex") == "1" and geo is not None:
            x = float(geo.attrib.get("x", 0))
            y = float(geo.attrib.get("y", 0))
            w = float(geo.attrib.get("width", 0))
            h = float(geo.attrib.get("height", 0))
            style = parse_style(cell.attrib.get("style", ""))
            value = cell.attrib.get("value", "").replace("&#xa;", "\n")
            shape = "rect"
            if "ellipse" in style:
                shape = "ellipse"
            elif "rhombus" in style:
                shape = "rhombus"
            vertices[cid] = {
                "rect": (x, y, w, h),
                "style": style,
                "value": value,
                "shape": shape,
            }
            max_x = max(max_x, x + w)
            max_y = max(max_y, y + h)
        elif cell.attrib.get("edge") == "1":
            edges.append(cell)

    canvas_w = int(sx(max_x) + MARGIN_X)
    canvas_h = int(sy(max_y) + MARGIN_Y)
    image = Image.new("RGB", (canvas_w, canvas_h), "white")
    draw = ImageDraw.Draw(image)
    font = get_font(24)
    small_font = get_font(18)

    # edges first
    for edge in edges:
        source = vertices.get(edge.attrib.get("source", ""))
        target = vertices.get(edge.attrib.get("target", ""))
        if not source or not target:
            continue
        style = parse_style(edge.attrib.get("style", ""))
        color = style.get("strokeColor", "#222222")
        geo = edge.find("mxGeometry")
        waypoints = []
        if geo is not None:
            arr = geo.find("Array")
            if arr is not None:
                for pt in arr.findall("mxPoint"):
                    waypoints.append((float(pt.attrib["x"]), float(pt.attrib["y"])))
        points = []
        first_ref = waypoints[0] if waypoints else center(target["rect"])
        start = border_point(source["rect"], source["shape"], first_ref)
        points.append(start)
        points.extend(waypoints)
        last_ref = waypoints[-1] if waypoints else center(source["rect"])
        end = border_point(target["rect"], target["shape"], last_ref)
        points.append(end)
        points_scaled = [(sx(p[0]), sy(p[1])) for p in points]
        draw.line(points_scaled, fill=color, width=3)
        draw_arrow_head(draw, points_scaled[-2], points_scaled[-1], color)
        label = edge.attrib.get("value", "")
        if label:
            mx = sum(p[0] for p in points_scaled) / len(points_scaled)
            my = sum(p[1] for p in points_scaled) / len(points_scaled) - 20
            draw.text((mx, my), label, fill=color, font=small_font, anchor="mm")

    # vertices second
    for item in vertices.values():
        rx, ry, rw, rh = item["rect"]
        x, y, w, h = sx(rx), sy(ry), rw * X_SCALE, rh * Y_SCALE
        style = item["style"]
        fc = style.get("fillColor", "#ffffff")
        ec = style.get("strokeColor", "#222222")
        if item["shape"] == "ellipse":
            draw.ellipse((x, y, x + w, y + h), outline=ec, fill=fc, width=3)
        elif item["shape"] == "rhombus":
            pts = [(x + w / 2, y), (x + w, y + h / 2), (x + w / 2, y + h), (x, y + h / 2)]
            draw.polygon(pts, outline=ec, fill=fc)
            draw.line(pts + [pts[0]], fill=ec, width=3)
        else:
            draw.rectangle((x, y, x + w, y + h), outline=ec, fill=fc, width=3)

        text = item["value"]
        if text:
            wrapped = wrap_text(draw, text, font, int(w - 28))
            draw.multiline_text((x + w / 2, y + h / 2), wrapped, fill="#111111", font=font, anchor="mm", align="center", spacing=6)

    image.save(png_path)


def main():
    root = Path(r"F:/sleep/outputs")
    flow1_drawio = root / "图5-3_系统诊断业务流程图.drawio"
    flow1_png = root / "图5-3_系统诊断业务流程图.png"
    flow2_drawio = root / "图5-4_后端文字诊断结果生成流程图.drawio"
    flow2_png = root / "图5-4_后端文字诊断结果生成流程图.png"
    render_drawio(flow1_drawio, flow1_png)
    render_drawio(flow2_drawio, flow2_png)

if __name__ == "__main__":
    main()
