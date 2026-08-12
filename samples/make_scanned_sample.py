"""生成一个"扫描件"PDF：把中文文字渲染成图片再嵌入 PDF，没有文字层。

用于测试 OCR 回退。需要 Windows 自带中文字体 simhei.ttf。
"""
from pathlib import Path

import fitz  # pymupdf
from PIL import Image, ImageDraw, ImageFont

FONT_PATH = r"C:\Windows\Fonts\simhei.ttf"
OUT_PATH = Path(__file__).parent / "scanned_demo.pdf"

PAGE_W, PAGE_H = 1240, 1754  # A4 @ 150 DPI
MARGIN = 120


def render_page(title: str, paragraphs: list[str], filename: str) -> str:
    img = Image.new("RGB", (PAGE_W, PAGE_H), "white")
    draw = ImageDraw.Draw(img)

    title_font = ImageFont.truetype(FONT_PATH, 48)
    body_font = ImageFont.truetype(FONT_PATH, 30)

    y = MARGIN
    draw.text((MARGIN, y), title, fill="black", font=title_font)
    y += 100

    for para in paragraphs:
        # 简单自动换行：按字符数截断
        max_chars = 32
        lines = [para[i:i + max_chars] for i in range(0, len(para), max_chars)]
        for line in lines:
            draw.text((MARGIN, y), line, fill="black", font=body_font)
            y += 50
        y += 30

    tmp_png = Path(__file__).parent / filename
    img.save(tmp_png, "PNG")
    return str(tmp_png)


def build_pdf():
    pages = [
        (
            "项目开发计划书",
            [
                "一、项目背景：本工具用于将PDF和Word文档批量转换为Markdown格式，方便在知识库中复用。",
                "二、主要功能：支持PDF扫描件自动OCR识别，保留标题、列表与表格结构。",
                "三、技术方案：使用Python开发，界面基于customtkinter，识别引擎采用RapidOCR。",
            ],
            "_scan_page1.png",
        ),
        (
            "里程碑安排",
            [
                "第一阶段：需求确认，第一周完成，交付需求文档。",
                "第二阶段：原型开发，第二至三周完成，交付可运行版本。",
                "第三阶段：测试优化，第四周完成，交付测试报告。",
                "备注：本文档为图片生成，专门用于验证扫描件OCR功能。",
            ],
            "_scan_page2.png",
        ),
    ]

    doc = fitz.open()
    for title, paras, png_name in pages:
        png_path = render_page(title, paras, png_name)
        page = doc.new_page(width=PAGE_W * 72 / 150, height=PAGE_H * 72 / 150)
        rect = page.rect
        page.insert_image(rect, filename=png_path)
        Path(png_path).unlink(missing_ok=True)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(OUT_PATH))
    doc.close()
    print(f"已生成扫描件 PDF: {OUT_PATH}")


if __name__ == "__main__":
    build_pdf()
