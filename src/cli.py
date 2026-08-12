import argparse
import sys
from pathlib import Path

from .converter import (
    ENGINE_AUTO, ENGINE_LOCAL, ENGINE_VISION,
    convert_file, convert_text, SUPPORTED_EXTENSIONS, ConversionError,
)

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="md-convert",
        description="将 PDF / Word 等文档转换为 Markdown",
    )
    parser.add_argument(
        "inputs",
        nargs="*",
        metavar="FILE",
        help="输入文件（支持多个）",
    )
    parser.add_argument(
        "-o", "--output",
        help="输出文件（单文件）或输出目录（多文件）",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="将结果打印到终端而不写入文件",
    )
    parser.add_argument(
        "--list-formats",
        action="store_true",
        help="列出支持的输入格式后退出",
    )
    parser.add_argument(
        "--engine",
        choices=[ENGINE_AUTO, ENGINE_LOCAL, ENGINE_VISION],
        default=ENGINE_AUTO,
        help="扫描件/图片识别引擎：auto（默认，视觉优先回退本地）、local（本地OCR）、vision（智谱GLM-4V-Flash）",
    )
    parser.add_argument(
        "--vision-url",
        default=None,
        help="视觉模型地址（默认读取 config.json，未配置时为智谱 https://open.bigmodel.cn/api/paas/v4）",
    )
    parser.add_argument(
        "--vision-model",
        default=None,
        help="视觉模型名（默认读取 config.json，未配置时为 glm-4v-flash）",
    )
    parser.add_argument(
        "--vision-key",
        default=None,
        help="智谱 API Key（不传则读取 config.json 的 vision_api_key）",
    )
    parser.add_argument(
        "--vision-dpi",
        type=int,
        default=150,
        help="视觉识别时 PDF 渲染 DPI（默认 150）",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list_formats:
        print("支持的格式:", ", ".join(sorted(SUPPORTED_EXTENSIONS)))
        return 0

    if not args.inputs:
        parser.error("需要至少一个输入文件")
        return 2

    if args.stdout and args.output:
        parser.error("--stdout 与 -o/--output 不能同时使用")
        return 2

    output = Path(args.output) if args.output else None

    if args.stdout and len(args.inputs) != 1:
        parser.error("--stdout 仅支持单个输入文件")
        return 2

    try:
        for inp in args.inputs:
            inp_path = Path(inp)
            if args.stdout:
                sys.stdout.write(convert_text(
                    inp_path,
                    engine=args.engine,
                    vision_base_url=args.vision_url,
                    vision_model=args.vision_model,
                    vision_api_key=args.vision_key,
                    vision_dpi=args.vision_dpi,
                ))
                continue

            if output is not None and output.is_dir() and len(args.inputs) > 1:
                dst = output
            elif output is not None and len(args.inputs) == 1 and output.suffix == ".md":
                dst = output
            else:
                dst = None

            result_path = convert_file(
                inp_path, dst,
                engine=args.engine,
                vision_base_url=args.vision_url,
                vision_model=args.vision_model,
                vision_api_key=args.vision_key,
                vision_dpi=args.vision_dpi,
            )
            print(f"[OK] {inp_path} -> {result_path}")
    except (FileNotFoundError, ConversionError) as e:
        print(f"错误: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"转换失败: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
