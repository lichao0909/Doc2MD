"""通过视觉模型识别扫描件/图片。

直接调用智谱 AI 的 GLM-4V-Flash（完全免费），需要智谱 API Key。
比本地 RapidOCR 更强：能理解版面、表格、公式、图示，并直接输出 Markdown。
"""
from __future__ import annotations

import base64
import io
from pathlib import Path
from typing import Callable

import fitz  # pymupdf
import requests
from PIL import Image

ProgressCb = Callable[[int, int, str], None]

# 智谱 AI 官方 OpenAI 兼容端点
DEFAULT_ZHIPU_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
DEFAULT_ZHIPU_MODEL = "glm-4v-flash"
DEFAULT_TIMEOUT = 240  # 单页给足时间

VISION_PROMPT = (
    "你是一个高精度的文档 OCR 与排版还原引擎。请识别图片中的全部文字内容，"
    "并输出严格的 Markdown 文档。要求：\n"
    "1. 按阅读顺序输出，正确识别标题层级（用 #、##、###）；\n"
    "2. 表格用 GFM 表格语法（| 列 | 列 |），保留所有行列；\n"
    "3. 列表用 - 或 1.，有层级就缩进；\n"
    "4. 保留原文段落划分，不要自行增删、润色、翻译或总结；\n"
    "5. 公式用 $...$ 或 $$...$$；\n"
    "6. 不要输出 Markdown 代码块围栏（```），直接输出内容；\n"
    "7. 如果页面是空白或无法识别，输出空字符串。"
)


class VisionError(Exception):
    pass


def _pil_to_data_url(img: Image.Image, quality: int = 85) -> str:
    if img.mode != "RGB":
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


def _render_pdf_pages(
    path: Path, dpi: int, quality: int
) -> list[tuple[str, str]]:
    """返回 [(data_url, page_label), ...]"""
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    pages: list[tuple[str, str]] = []
    doc = fitz.open(str(path))
    try:
        total = len(doc)
        for i, page in enumerate(doc, 1):
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            pages.append((_pil_to_data_url(img, quality), f"第 {i}/{total} 页"))
    finally:
        doc.close()
    return pages


def _image_file_to_data_url(path: Path, quality: int) -> str:
    with Image.open(path) as img:
        return _pil_to_data_url(img, quality)


def _call_vision(
    base_url: str,
    model: str,
    data_url: str,
    prompt: str,
    timeout: float,
    api_key: str = "",
) -> str:
    """调用智谱 GLM-4V-Flash 视觉模型，返回 Markdown 文本。"""
    payload = {
        "model": model,
        "stream": False,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
    }
    base = base_url.rstrip("/")
    url = f"{base}/chat/completions"

    headers = {}
    if api_key:
        key = api_key.strip()
        if not key.lower().startswith("bearer "):
            key = f"Bearer {key}"
        headers["Authorization"] = key

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
    except requests.RequestException as e:
        raise VisionError(f"无法连接视觉服务 {base_url}：{e}") from e

    if resp.status_code != 200:
        raise VisionError(
            f"视觉服务返回 {resp.status_code}：{resp.text[:500]}"
        )

    try:
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    except (ValueError, KeyError, IndexError) as e:
        raise VisionError(f"视觉服务响应解析失败：{e}；原始：{resp.text[:300]}") from e


def recognize(
    input_path: str | Path,
    *,
    base_url: str = DEFAULT_ZHIPU_BASE_URL,
    model: str = DEFAULT_ZHIPU_MODEL,
    api_key: str = "",
    dpi: int = 150,
    jpeg_quality: int = 85,
    prompt: str = VISION_PROMPT,
    timeout: float = DEFAULT_TIMEOUT,
    progress_cb: ProgressCb | None = None,
) -> str:
    """对 PDF 或图片文件做视觉识别，返回 Markdown。

    使用智谱 GLM-4V-Flash（免费，需 API Key）。
    PDF：逐页渲染并识别，每页加 `## 第 N 页` 标题
    图片：直接识别
    """
    path = Path(input_path)
    if not path.is_file():
        raise FileNotFoundError(f"文件不存在: {path}")

    suffix = path.suffix.lower()
    if suffix == ".pdf":
        if progress_cb:
            progress_cb(0, 1, "渲染 PDF 页面…")
        pages = _render_pdf_pages(path, dpi, jpeg_quality)
        total = len(pages)
        chunks: list[str] = [f"# {path.stem}"]
        for i, (data_url, label) in enumerate(pages, 1):
            if progress_cb:
                progress_cb(i - 1, total, f"视觉识别 {label}…")
            text = _call_vision(base_url, model, data_url, prompt, timeout, api_key)
            chunks.append(f"## 第 {i} 页\n\n{text}" if text else f"## 第 {i} 页")
        if progress_cb:
            progress_cb(total, total, "视觉识别完成")
        return "\n\n".join(chunks) + "\n"

    if suffix in {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"}:
        if progress_cb:
            progress_cb(0, 1, "加载图片…")
        data_url = _image_file_to_data_url(path, jpeg_quality)
        if progress_cb:
            progress_cb(0, 1, "视觉识别中…")
        text = _call_vision(base_url, model, data_url, prompt, timeout, api_key)
        if progress_cb:
            progress_cb(1, 1, "视觉识别完成")
        if not text:
            text = ""
        return f"# {path.stem}\n\n{text}\n"

    raise VisionError(f"视觉识别不支持的格式: {suffix}")
