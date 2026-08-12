# Doc2MD — 文档转 Markdown 转换器

> 拖拽即转换，扫描件也能 OCR。支持 PDF / Word / PPT / Excel / 图片，一键输出干净 Markdown。

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

## ✨ 特性

- **📂 多格式支持** — PDF、Word (.docx/.doc)、PowerPoint、Excel、HTML、图片（PNG/JPG/BMP/TIFF/WebP）
- **🔍 扫描件 OCR** — 内置 RapidOCR（ONNXRuntime），离线识别扫描版 PDF，无需联网
- **👁 视觉模型加持** — 可选智谱 GLM-4V-Flash（**免费**），识别表格、公式、版面更强
- **🖥 GUI 拖放** — 拖文件进去，点一下开始，所见即所得
- **⌨️ CLI 命令行** — `python -m src input.pdf` 批量转换
- **🔐 隐私安全** — API Key 通过 `.env` 管理，不会误提交到 Git

## 📸 界面预览

```
┌─────────────────────────────────────────────────┐
│  📄 文档 → Markdown 转换器            🌓 主题   │
├──────────────────────┬──────────────────────────┤
│  ⬇ 拖放文件到这里     │  输出设置                 │
│  支持 .pdf .docx ... │  ○ 与源文件同目录          │
│  [添加文件]           │  ○ 统一输出到目录：[…]     │
│                      │                          │
│  [清空列表]   共 3 个 │  识别引擎                 │
│  ┌─────────────────┐ │  ○ 自动  ○ 本地OCR  ○ 视觉│
│  │ 📄 report.pdf   │ │                          │
│  │ 📄 slides.pptx  │ │  智谱 GLM-4V-Flash       │
│  │ 📄 notes.docx   │ │  [API Key: ****]         │
│  └─────────────────┘ │                          │
├──────────────────────┴──────────────────────────┤
│  进度 ████████░░░░░░░░░░                        │
│  [3/5] notes.docx — 完成                        │
│  [🚀 开始转换]                                   │
├─────────────────────────────────────────────────┤
│  日志                                           │
│  [20:15:01] 开始转换 5 个文件                      │
│  [20:15:02] [1/5] 转换中: report.pdf（引擎: auto） │
│  [20:15:15]     ✓ -> report.md                   │
└─────────────────────────────────────────────────┘
```

## 🚀 快速开始

### 环境要求

- Python 3.10+
- Windows / macOS / Linux

### 安装

```bash
# 1. 克隆仓库
git clone https://github.com/lichao0909/Doc2MD.git
cd Doc2MD

# 2. 创建虚拟环境
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置 API Key（可选，仅视觉模式需要）
cp .env.template .env
# 编辑 .env，填入你的智谱 API Key（免费申请：https://open.bigmodel.cn）
```

### 使用

**GUI 模式：**

```bash
python main.py
```

然后拖拽文件到窗口，点击「开始转换」即可。

**命令行模式：**

```bash
# 单文件转换
python -m src document.pdf

# 批量转换
python -m src doc1.pdf doc2.docx slide.pptx -o ./output/

# 指定引擎
python -m src scanned.pdf --engine vision    # 智谱视觉
python -m src scanned.pdf --engine local     # 本地 OCR

# 列出支持的格式
python -m src --list-formats
```

## ⚙️ 识别引擎说明

| 引擎 | 适用场景 | 需要联网 | 需要配置 |
|------|---------|---------|---------|
| **auto**（推荐）| 自动判断：文字 PDF 走 markitdown，扫描件优先视觉→回退 OCR | 视情况 | 无（自动降级）|
| **local** | 纯本地 OCR，适合离线/隐私场景 | ❌ | 首次自动下载模型(~10MB) |
| **vision** | 表格、公式、复杂版面，效果最好 | ✅ | 智谱 API Key（免费）|

### 获取智谱 API Key

1. 访问 [open.bigmodel.cn](https://open.bigmodel.cn)
2. 注册/登录，进入 API Keys 页面
3. 创建新的 API Key 并复制
4. 粘贴到 `.env` 文件的 `VISION_API_KEY` 字段

> GLM-4V-Flash 目前**完全免费**，无需充值。

## 📁 项目结构

```
Doc2MD/
├── main.py                 # GUI 入口
├── main.spec               # PyInstaller 打包配置
├── requirements.txt        # Python 依赖
├── .env.template           # 环境变量模板
├── config.example.json     # 配置文件模板
├── run_gui.bat             # Windows 一键启动
├── src/
│   ├── __init__.py         # 版本信息
│   ├── __main__.py         # CLI 入口
│   ├── cli.py              # 命令行参数解析
│   ├── converter.py        # 核心转换逻辑
│   ├── gui.py              # GUI 界面（customtkinter）
│   ├── ocr_pdf.py          # 本地 OCR（RapidOCR）
│   ├── vision_ocr.py       # 视觉模型识别（智谱 GLM-4V-Flash）
│   └── settings.py         # 配置持久化（含 .env 加载）
└── samples/                # 示例文件
    ├── demo.docx
    ├── scanned_demo.pdf
    └── scanned_table.pdf
```

## 🔧 打包为 EXE

```bash
pip install pyinstaller
pyinstaller main.spec --noconfirm
# 产物在 dist/Doc2MD/main.exe
```

## 🤝 贡献

欢迎提 Issue 和 PR。项目使用 MIT 协议。

## 📄 许可证

[MIT](LICENSE)

---

**致谢**

- [markitdown](https://github.com/microsoft/markitdown) — 微软出品的文档转 Markdown 引擎
- [RapidOCR](https://github.com/RapidAI/RapidOCR) — 轻量级离线 OCR
- [智谱 AI](https://open.bigmodel.cn) — GLM-4V-Flash 免费视觉模型
- [customtkinter](https://github.com/TomSchimansky/CustomTkinter) — 现代化 Tkinter 主题
