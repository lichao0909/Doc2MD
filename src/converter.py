from pathlib import Path
from typing import Callable

from markitdown import MarkItDown

SUPPORTED_EXTENSIONS = {
    ".pdf", ".docx", ".doc",
    ".pptx", ".xlsx", ".xls",
    ".html", ".htm",
    ".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp",
}

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"}

ProgressCb = Callable[[int, int, str], None]

ENGINE_AUTO = "auto"
ENGINE_LOCAL = "local"
ENGINE_VISION = "vision"
VALID_ENGINES = {ENGINE_AUTO, ENGINE_LOCAL, ENGINE_VISION}


class ConversionError(Exception):
    pass


def _convert_with_markitdown(input_path: Path) -> str:
    md = MarkItDown()
    return md.convert(str(input_path)).text_content


def _is_scanned_pdf(input_path: Path) -> bool:
    from .ocr_pdf import is_scanned_pdf
    return is_scanned_pdf(input_path)


def _vision_defaults() -> tuple[str, str, str]:
    """从 config.json 读取视觉后端配置（智谱 GLM-4V-Flash）。"""
    try:
        from . import settings
        cfg = settings.load()
        return (
            str(cfg.get("vision_base_url", "") or "https://open.bigmodel.cn/api/paas/v4"),
            str(cfg.get("vision_model", "") or "glm-4v-flash"),
            str(cfg.get("vision_api_key", "") or ""),
        )
    except Exception:
        return (
            "https://open.bigmodel.cn/api/paas/v4",
            "glm-4v-flash",
            "",
        )


def convert_text(
    input_path: str | Path,
    *,
    engine: str = ENGINE_AUTO,
    vision_base_url: str | None = None,
    vision_model: str | None = None,
    vision_api_key: str | None = None,
    vision_dpi: int = 150,
    progress_cb: ProgressCb | None = None,
) -> str:
    """转换文档为 Markdown。

    engine:
      - auto:   PDF 走文字提取，扫描件有 API Key 时走视觉识别，否则回退本地 OCR；
                图片文件优先视觉识别，不可用时回退本地 OCR。
      - local:  扫描件/图片强制使用本地 RapidOCR。
      - vision: 扫描件/图片强制使用智谱 GLM-4V-Flash 视觉模型。

    vision_base_url / vision_model / vision_api_key 未显式传入时，
    从项目根 .env 或 config.json 读取（默认智谱 GLM-4V-Flash）。
    """
    cfg_base, cfg_model, cfg_key = _vision_defaults()
    if vision_base_url is None:
        vision_base_url = cfg_base
    if vision_model is None:
        vision_model = cfg_model
    if vision_api_key is None:
        vision_api_key = cfg_key
    vision_api_key = (vision_api_key or "").strip()

    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"文件不存在: {input_path}")

    suffix = input_path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ConversionError(
            f"不支持的格式: {suffix}（支持: {', '.join(sorted(SUPPORTED_EXTENSIONS))}）"
        )
    if engine not in VALID_ENGINES:
        raise ConversionError(f"未知引擎: {engine}")

    use_vision = False
    use_local_ocr = False

    if suffix == ".pdf":
        if progress_cb:
            progress_cb(0, 1, "检测 PDF 类型…")
        if engine == ENGINE_VISION:
            use_vision = True
        elif engine == ENGINE_LOCAL:
            if _is_scanned_pdf(input_path):
                use_local_ocr = True
        else:  # auto
            if _is_scanned_pdf(input_path):
                if vision_api_key:
                    use_vision = True
                else:
                    use_local_ocr = True

    elif suffix in IMAGE_EXTENSIONS:
        if engine == ENGINE_VISION:
            use_vision = True
        elif engine == ENGINE_LOCAL:
            use_local_ocr = True
        else:  # auto
            if vision_api_key:
                use_vision = True
            else:
                use_local_ocr = True

    # 执行分支
    if use_vision:
        from .vision_ocr import recognize, VisionError
        if progress_cb:
            progress_cb(0, 1, "使用视觉模型识别…")
        try:
            return recognize(
                input_path,
                base_url=vision_base_url,
                model=vision_model,
                api_key=vision_api_key,
                dpi=vision_dpi,
                progress_cb=progress_cb,
            )
        except VisionError:
            if engine == ENGINE_AUTO:
                if progress_cb:
                    progress_cb(0, 1, "视觉识别失败，回退本地 OCR…")
                from .ocr_pdf import ocr_pdf
                return ocr_pdf(input_path, progress_cb=progress_cb)
            raise

    if use_local_ocr:
        from .ocr_pdf import ocr_pdf
        if progress_cb:
            progress_cb(0, 1, "使用本地 OCR…")
        return ocr_pdf(input_path, progress_cb=progress_cb)

    if progress_cb:
        progress_cb(0, 1, "正在转换…")
    text = _convert_with_markitdown(input_path)
    if progress_cb:
        progress_cb(1, 1, "完成")
    return text


def convert_file(
    input_path: str | Path,
    output_path: str | Path | None = None,
    *,
    engine: str = ENGINE_AUTO,
    vision_base_url: str | None = None,
    vision_model: str | None = None,
    vision_api_key: str | None = None,
    vision_dpi: int = 150,
    progress_cb: ProgressCb | None = None,
) -> Path:
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"文件不存在: {input_path}")
    if not input_path.is_file():
        raise ConversionError(f"不是文件: {input_path}")

    suffix = input_path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ConversionError(
            f"不支持的格式: {suffix}（支持: {', '.join(sorted(SUPPORTED_EXTENSIONS))}）"
        )

    if output_path is None:
        output_path = input_path.with_suffix(".md")
    else:
        output_path = Path(output_path)
        if output_path.is_dir():
            output_path = output_path / (input_path.stem + ".md")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    text = convert_text(
        input_path,
        engine=engine,
        vision_base_url=vision_base_url,
        vision_model=vision_model,
        vision_api_key=vision_api_key,
        vision_dpi=vision_dpi,
        progress_cb=progress_cb,
    )
    output_path.write_text(text, encoding="utf-8")
    return output_path
