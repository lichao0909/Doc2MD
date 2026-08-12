# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — 文档转 Markdown GUI 打包配置。

构建: venv\\Scripts\\pyinstaller.exe main.spec --noconfirm
产物: dist\\main\\main.exe
"""
from PyInstaller.utils.hooks import collect_all, copy_metadata

datas = []
binaries = []
hiddenimports = []

# 含数据文件 / 动态导入的包，整体收集
for pkg in (
    "customtkinter",          # 主题 JSON 等资源
    "tkinterdnd2",            # tcl 拖拽脚本
    "rapidocr_onnxruntime",   # ONNX 模型 + 配置
    "onnxruntime",            # provider DLL
    "pymupdf",                # fitz
    "PIL",                    # Pillow
):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# markitdown 通过 entry points 动态发现转换器，需要元数据
try:
    datas += copy_metadata("markitdown")
except Exception:
    pass

# 显式拉入 markitdown 各转换器及其可选依赖，避免动态导入遗漏
hiddenimports += [
    "markitdown",
    "markitdown.converters",
    "markitdown.converters._docx_converter",
    "markitdown.converters._pdf_converter",
    "markitdown.converters._pptx_converter",
    "markitdown.converters._xlsx_converter",
    "markitdown.converters._html_converter",
    "markitdown.converters._image_converter",
    "markitdown.converters._csv_converter",
    "markitdown.converters._plain_text_converter",
    "markitdown.converters._zip_converter",
    "mammoth",
    "docx",
    "pptx",
    "openpyxl",
    "pdfminer",
    "pdfplumber",
    "pypdf",
    "fitz",
    "numpy",
    "cv2",
    "yaml",
    "requests",
]

# 显式拉入 markitdown 各转换器及其可选依赖，避免动态导入遗漏
a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["selenium", "matplotlib", "pandas", "IPython", "jupyter"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Doc2MD",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Doc2MD",
)
