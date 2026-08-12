"""生成带表格的扫描件 PDF（纯图片，无文字层），用于对比视觉模型对表格的还原能力。"""
from pathlib import Path

import fitz
from PIL import Image, ImageDraw, ImageFont

FONT = r"C:\Windows\Fonts\simhei.ttf"
OUT = Path(__file__).parent / "scanned_table.pdf"

W, H = 1240, 1754
M = 120


def render():
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    title_f = ImageFont.truetype(FONT, 44)
    h_f = ImageFont.truetype(FONT, 30)
    cell_f = ImageFont.truetype(FONT, 26)

    d.text((M, M), "季度销售统计表", fill="black", font=title_f)
    d.text((M, M + 80), "单位：万元", fill="black", font=h_f)

    cols = ["地区", "Q1", "Q2", "Q3", "Q4", "合计"]
    rows = [
        ["华北", "120", "135", "150", "180", "585"],
        ["华东", "200", "220", "210", "260", "890"],
        ["华南", "160", "170", "185", "200", "715"],
        ["西南", "80",  "85",  "95",  "110", "370"],
        ["总计", "560", "610", "640", "750", "2560"],
    ]

    x0, y0 = M, M + 160
    col_w = [180, 110, 110, 110, 110, 130]
    row_h = 56

    # 表头
    cx = x0
    for i, c in enumerate(cols):
        d.rectangle([cx, y0, cx + col_w[i], y0 + row_h], outline="black", width=2)
        bbox = d.textbbox((0, 0), c, font=cell_f)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        d.text((cx + (col_w[i] - tw) / 2, y0 + (row_h - th) / 2 - 4), c, fill="black", font=cell_f)
        cx += col_w[i]

    # 数据行
    for r, row in enumerate(rows):
        cy = y0 + (r + 1) * row_h
        cx = x0
        bold = r == len(rows) - 1
        font = ImageFont.truetype(FONT, 27) if bold else cell_f
        for i, val in enumerate(row):
            d.rectangle([cx, cy, cx + col_w[i], cy + row_h], outline="black", width=2)
            bbox = d.textbbox((0, 0), val, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            d.text((cx + (col_w[i] - tw) / 2, cy + (row_h - th) / 2 - 4), val, fill="black", font=font)
            cx += col_w[i]

    # 一段说明
    note_y = y0 + (len(rows) + 1) * row_h + 40
    d.text((M, note_y), "说明：本表为图片渲染生成，专门用于测试扫描件表格识别。", fill="black", font=h_f)
    d.text((M, note_y + 50), "合计列由各季度相加所得，总计行为各地区相加所得。", fill="black", font=h_f)

    tmp = Path(__file__).parent / "_table_tmp.png"
    img.save(tmp, "PNG")

    doc = fitz.open()
    page = doc.new_page(width=W * 72 / 150, height=H * 72 / 150)
    page.insert_image(page.rect, filename=str(tmp))
    doc.save(str(OUT))
    doc.close()
    tmp.unlink(missing_ok=True)
    print(f"已生成: {OUT}")


if __name__ == "__main__":
    render()
