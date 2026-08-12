"""扫描件 PDF 的 OCR 识别。

策略：
1. 用 pymupdf 打开 PDF，统计每页文字字符数，判断是否为扫描件；
2. 扫描件逐页渲染为图片（默认 200 DPI）；
3. 用 RapidOCR（ONNXRuntime 后端，内置中文+英文模型）识别；
4. 按文字框坐标聚合成"行 → 段落"，输出 Markdown。

首次运行时 RapidOCR 会自动下载模型文件（约 10+ MB）到用户目录，需要网络。
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import fitz  # pymupdf
import numpy as np
from PIL import Image

ProgressCb = Callable[[int, int, str], None]
"""进度回调：(current_page, total_pages, message) -> None"""

SCANNED_TEXT_THRESHOLD = 100
"""整份 PDF 文字字符数低于此值即判定为扫描件。"""

DEFAULT_DPI = 200


def is_scanned_pdf(path: str | Path) -> bool:
    """检测 PDF 是否为扫描件（无文字层或文字层极少）。"""
    doc = fitz.open(str(path))
    try:
        total_chars = 0
        for page in doc:
            total_chars += len(page.get_text("text").strip())
            if total_chars >= SCANNED_TEXT_THRESHOLD:
                return False
        return total_chars < SCANNED_TEXT_THRESHOLD
    finally:
        doc.close()


@dataclass
class _Box:
    left: float
    top: float
    right: float
    bottom: float
    text: str

    @property
    def cy(self) -> float:
        return (self.top + self.bottom) / 2

    @property
    def height(self) -> float:
        return self.bottom - self.top


def _parse_boxes(result) -> list[_Box]:
    """把 RapidOCR 返回的 [[box, text, score], ...] 转成 _Box 列表。"""
    boxes: list[_Box] = []
    if not result:
        return boxes
    for item in result:
        if len(item) < 2:
            continue
        pts, text = item[0], item[1]
        if not text or not text.strip():
            continue
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        boxes.append(_Box(
            left=min(xs), top=min(ys),
            right=max(xs), bottom=max(ys),
            text=text.strip(),
        ))
    return boxes


def _group_into_lines(boxes: list[_Box]) -> list[list[_Box]]:
    """把文字框按 y 坐标聚合成行，行内按 x 排序。"""
    if not boxes:
        return []
    boxes = sorted(boxes, key=lambda b: b.cy)
    lines: list[list[_Box]] = []
    current: list[_Box] = [boxes[0]]
    current_cy = boxes[0].cy
    current_h = boxes[0].height

    for b in boxes[1:]:
        # 与当前行中心偏差小于行高的一半视为同一行
        if abs(b.cy - current_cy) < max(current_h, b.height) * 0.5:
            current.append(b)
            n = len(current)
            current_cy = ((n - 1) * current_cy + b.cy) / n
            current_h = ((n - 1) * current_h + b.height) / n
        else:
            lines.append(current)
            current = [b]
            current_cy = b.cy
            current_h = b.height
    lines.append(current)

    for line in lines:
        line.sort(key=lambda b: b.left)
    return lines


def _lines_to_paragraphs(lines: list[list[_Box]]) -> list[str]:
    """把行聚合成段落：行间距大于约 1 倍行高视为新段落。"""
    if not lines:
        return []

    line_texts = [" ".join(b.text for b in line).strip() for line in lines]
    line_heights = [
        max(b.height for b in line) for line in lines
    ]
    line_bottoms = [max(b.bottom for b in line) for line in lines]
    line_tops = [min(b.top for b in line) for line in lines]

    paragraphs: list[str] = [line_texts[0]]
    for i in range(1, len(lines)):
        gap = line_tops[i] - line_bottoms[i - 1]
        avg_h = (line_heights[i] + line_heights[i - 1]) / 2
        if gap > avg_h * 0.8:
            paragraphs.append(line_texts[i])
        else:
            paragraphs[-1] += line_texts[i]
    return [p for p in paragraphs if p]


def _ocr_page(engine, page: fitz.Page, dpi: int) -> str:
    """渲染单页并 OCR，返回该页的 Markdown 文本。"""
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=matrix, alpha=False)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    img_array = np.array(img)

    result, _ = engine(img_array)
    boxes = _parse_boxes(result)
    lines = _group_into_lines(boxes)
    paragraphs = _lines_to_paragraphs(lines)
    return "\n\n".join(paragraphs)


def ocr_pdf(
    path: str | Path,
    *,
    dpi: int = DEFAULT_DPI,
    progress_cb: ProgressCb | None = None,
) -> str:
    """对扫描件 PDF 做 OCR，返回整份文档的 Markdown。

    每页输出一个二级标题 `## 第 N 页`。
    """
    from rapidocr_onnxruntime import RapidOCR

    path = Path(path)
    if progress_cb:
        progress_cb(0, 1, "正在加载 OCR 模型…")
    engine = RapidOCR()

    doc = fitz.open(str(path))
    pages_md: list[str] = []
    total = len(doc)
    try:
        for i, page in enumerate(doc, 1):
            if progress_cb:
                progress_cb(i - 1, total, f"OCR 识别中：第 {i}/{total} 页")
            text = _ocr_page(engine, page, dpi)
            header = f"## 第 {i} 页"
            pages_md.append(f"{header}\n\n{text}" if text else header)
    finally:
        doc.close()

    if progress_cb:
        progress_cb(total, total, "OCR 完成")

    title = f"# {path.stem}"
    pages_md.insert(0, title)
    return "\n\n".join(pages_md) + "\n"
