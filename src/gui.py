"""PDF / Word → Markdown 转换器 GUI。"""
from __future__ import annotations

import os
import threading
import traceback
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
from tkinterdnd2 import DND_FILES, TkinterDnD

from . import settings
from .converter import (
    ENGINE_AUTO, ENGINE_LOCAL, ENGINE_VISION,
    SUPPORTED_EXTENSIONS, convert_file,
)

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")


class DnDCTk(ctk.CTk, TkinterDnD.DnDWrapper):
    """同时具备 customtkinter 外观与 tkinterdnd2 拖放能力的根窗口。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.TkdndVersion = TkinterDnD._require(self)


class FileListFrame(ctk.CTkScrollableFrame):
    """可滚动的待转换文件列表。"""

    def __init__(self, master, on_remove):
        super().__init__(master, label_text="待转换文件")
        self.on_remove = on_remove
        self._rows: dict[str, tuple[ctk.CTkFrame, ctk.CTkLabel]] = {}

    def add_files(self, paths):
        added = 0
        for p in paths:
            p = Path(p)
            if not p.is_file():
                continue
            key = str(p.resolve())
            if key in self._rows:
                continue
            if p.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            self._add_row(key, p)
            added += 1
        return added

    def _add_row(self, key: str, path: Path):
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=4, pady=2)

        icon = ctk.CTkLabel(row, text="📄", width=28, anchor="w")
        icon.pack(side="left")

        name = ctk.CTkLabel(
            row, text=path.name, anchor="w",
            font=ctk.CTkFont(size=13),
        )
        name.pack(side="left", fill="x", expand=True)

        size_kb = path.stat().st_size / 1024
        size_lbl = ctk.CTkLabel(
            row, text=f"{size_kb:,.0f} KB",
            text_color=("gray50", "gray70"),
            font=ctk.CTkFont(size=11), width=70, anchor="e",
        )
        size_lbl.pack(side="left", padx=(4, 8))

        remove_btn = ctk.CTkButton(
            row, text="×", width=26, height=24,
            fg_color="transparent", hover_color=("#d0d0d0", "#404040"),
            text_color=("gray20", "gray80"),
            command=lambda: self.remove(key),
        )
        remove_btn.pack(side="right")

        self._rows[key] = (row, name)

    def remove(self, key: str):
        row = self._rows.pop(key, None)
        if row:
            row[0].destroy()
            self.on_remove(key)

    def clear(self):
        for key in list(self._rows.keys()):
            self.remove(key)

    def paths(self) -> list[str]:
        return list(self._rows.keys())

    def __len__(self):
        return len(self._rows)


class ConverterApp:
    def __init__(self):
        self.cfg = settings.load()

        self.root = DnDCTk()
        self.root.title("PDF / Word → Markdown 转换器")
        self.root.geometry("980x820")
        self.root.minsize(820, 680)

        ctk.set_appearance_mode(self.cfg.get("appearance_mode", "System"))

        self.output_mode = ctk.StringVar(value=self.cfg.get("output_mode", "source"))
        self.output_dir_var = ctk.StringVar(value=self.cfg.get("output_dir", ""))
        self.status_var = ctk.StringVar(value="就绪")
        self.engine_var = ctk.StringVar(value=self.cfg.get("engine", ENGINE_AUTO))
        self.zhipu_key_var = ctk.StringVar(value=self.cfg.get("vision_api_key", ""))
        self.vision_url_var = ctk.StringVar(
            value=self.cfg.get("vision_base_url", "https://open.bigmodel.cn/api/paas/v4"))
        self.vision_model_var = ctk.StringVar(value=self.cfg.get("vision_model", "glm-4v-flash"))

        self._build_ui()
        self._bind_dnd()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------- UI 构建 ----------
    def _build_ui(self):
        self.root.grid_columnconfigure(0, weight=3)
        self.root.grid_columnconfigure(1, weight=2)
        self.root.grid_rowconfigure(1, weight=1)

        # 顶部标题栏
        header = ctk.CTkFrame(self.root, corner_radius=0, height=52)
        header.grid(row=0, column=0, columnspan=2, sticky="nsew")
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header, text="  文档 → Markdown 转换器",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=12, pady=10)

        ctk.CTkButton(
            header, text="🌓  主题", width=80,
            command=self._toggle_theme,
        ).grid(row=0, column=1, padx=12)

        # 左侧：拖放 + 文件列表
        left = ctk.CTkFrame(self.root)
        left.grid(row=1, column=0, sticky="nsew", padx=(12, 6), pady=12)
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(2, weight=1)

        self.drop_zone = ctk.CTkFrame(
            left, corner_radius=10,
            border_width=2, border_color=("#3a86ff", "#2563eb"),
            fg_color=("#eef4ff", "#1e293b"),
            height=110,
        )
        self.drop_zone.grid(row=0, column=0, sticky="ew", padx=10, pady=(12, 8))
        self.drop_zone.grid_columnconfigure(0, weight=1)
        self.drop_zone.grid_propagate(False)

        ctk.CTkLabel(
            self.drop_zone, text="⬇  拖放文件到这里",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).grid(row=0, column=0, pady=(18, 2))
        ctk.CTkLabel(
            self.drop_zone,
            text=f"支持 {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
            text_color=("gray40", "gray70"),
            font=ctk.CTkFont(size=11),
        ).grid(row=1, column=0)
        ctk.CTkButton(
            self.drop_zone, text="添加文件", width=110,
            command=self._pick_files,
        ).grid(row=2, column=0, pady=(6, 10))

        btn_row = ctk.CTkFrame(left, fg_color="transparent")
        btn_row.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 4))
        btn_row.grid_columnconfigure(1, weight=1)
        ctk.CTkButton(
            btn_row, text="清空列表", width=90,
            fg_color="transparent", border_width=1,
            command=self._clear_files,
        ).grid(row=0, column=0, sticky="w")
        self.count_lbl = ctk.CTkLabel(
            btn_row, text="共 0 个文件", text_color=("gray40", "gray70"),
        )
        self.count_lbl.grid(row=0, column=1, sticky="e", padx=4)

        self.file_list = FileListFrame(left, on_remove=lambda _k: self._refresh_count())
        self.file_list.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 12))

        # 右侧容器：上部可滚动设置，下部固定进度条 + 转换按钮
        right = ctk.CTkFrame(self.root)
        right.grid(row=1, column=1, sticky="nsew", padx=(6, 12), pady=12)
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=0)

        # 可滚动的设置区
        scroll = ctk.CTkScrollableFrame(right, corner_radius=0)
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            scroll, text="输出设置",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=14, pady=(8, 6))

        ctk.CTkRadioButton(
            scroll, text="与源文件同目录",
            variable=self.output_mode, value="source",
            command=self._on_mode_change,
        ).grid(row=1, column=0, sticky="w", padx=18, pady=4)

        ctk.CTkRadioButton(
            scroll, text="统一输出到目录：",
            variable=self.output_mode, value="custom",
            command=self._on_mode_change,
        ).grid(row=2, column=0, sticky="w", padx=18, pady=(8, 2))

        dir_row = ctk.CTkFrame(scroll, fg_color="transparent")
        dir_row.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 8))
        dir_row.grid_columnconfigure(0, weight=1)
        self.dir_entry = ctk.CTkEntry(
            dir_row, textvariable=self.output_dir_var,
            placeholder_text="未选择",
        )
        self.dir_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.browse_btn = ctk.CTkButton(
            dir_row, text="…", width=34, command=self._pick_dir,
        )
        self.browse_btn.grid(row=0, column=1)

        self.open_out_btn = ctk.CTkButton(
            scroll, text="📂  打开输出目录",
            fg_color="transparent", border_width=1,
            command=self._open_output_dir,
        )
        self.open_out_btn.grid(row=4, column=0, sticky="ew", padx=14, pady=(4, 10))

        # 识别引擎
        ctk.CTkLabel(
            scroll, text="识别引擎",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=5, column=0, sticky="w", padx=14, pady=(4, 2))

        engine_row = ctk.CTkFrame(scroll, fg_color="transparent")
        engine_row.grid(row=6, column=0, sticky="ew", padx=14, pady=(0, 4))
        engine_row.grid_columnconfigure((0, 1, 2), weight=1)
        ctk.CTkRadioButton(
            engine_row, text="自动", variable=self.engine_var, value=ENGINE_AUTO,
            command=self._save_settings,
        ).grid(row=0, column=0, sticky="w", padx=2)
        ctk.CTkRadioButton(
            engine_row, text="本地OCR", variable=self.engine_var, value=ENGINE_LOCAL,
            command=self._save_settings,
        ).grid(row=0, column=1, sticky="w", padx=2)
        ctk.CTkRadioButton(
            engine_row, text="GLM-4V视觉", variable=self.engine_var, value=ENGINE_VISION,
            command=self._save_settings,
        ).grid(row=0, column=2, sticky="w", padx=2)

        # 智谱 GLM-4V-Flash 视觉设置
        zhipu_frame = ctk.CTkFrame(scroll, fg_color=("#f4f6fb", "#1a1f2e"))
        zhipu_frame.grid(row=8, column=0, sticky="ew", padx=14, pady=(4, 10))
        zhipu_frame.grid_columnconfigure(0, weight=1)

        zh_head = ctk.CTkFrame(zhipu_frame, fg_color="transparent")
        zh_head.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 2))
        zh_head.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            zh_head, text="智谱 GLM-4V-Flash（免费识图）",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=0, sticky="w")

        self.zhipu_url_entry = ctk.CTkEntry(
            zhipu_frame, textvariable=self.vision_url_var,
            placeholder_text="https://open.bigmodel.cn/api/paas/v4",
            height=28, font=ctk.CTkFont(size=11),
        )
        self.zhipu_url_entry.grid(row=1, column=0, sticky="ew", padx=10, pady=(2, 4))

        self.zhipu_model_entry = ctk.CTkEntry(
            zhipu_frame, textvariable=self.vision_model_var,
            placeholder_text="glm-4v-flash",
            height=28, font=ctk.CTkFont(size=11),
        )
        self.zhipu_model_entry.grid(row=2, column=0, sticky="ew", padx=10, pady=(2, 4))

        key_row = ctk.CTkFrame(zhipu_frame, fg_color="transparent")
        key_row.grid(row=3, column=0, sticky="ew", padx=10, pady=(2, 4))
        key_row.grid_columnconfigure(0, weight=1)
        self.zhipu_key_entry = ctk.CTkEntry(
            key_row, textvariable=self.zhipu_key_var, show="*",
            placeholder_text="智谱 API Key（open.bigmodel.cn 免费申请）",
            height=28, font=ctk.CTkFont(size=11),
        )
        self.zhipu_key_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.show_zhipu_btn = ctk.CTkButton(
            key_row, text="👁", width=30, height=28,
            fg_color="transparent", border_width=1,
            command=self._toggle_zhipu_key_visibility,
        )
        self.show_zhipu_btn.grid(row=0, column=1)

        ctk.CTkButton(
            zhipu_frame, text="保存智谱设置", height=28,
            font=ctk.CTkFont(size=11),
            fg_color="transparent", border_width=1,
            command=self._save_zhipu_settings,
        ).grid(row=4, column=0, sticky="ew", padx=10, pady=(2, 8))

        # 底部固定区：进度 + 转换按钮
        bottom = ctk.CTkFrame(right, fg_color="transparent")
        bottom.grid(row=1, column=0, sticky="ew", padx=14, pady=(6, 12))
        bottom.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            bottom, text="进度",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=0, column=0, sticky="w", pady=(0, 2))

        self.progress = ctk.CTkProgressBar(bottom)
        self.progress.grid(row=1, column=0, sticky="ew", pady=2)
        self.progress.set(0)

        ctk.CTkLabel(
            bottom, textvariable=self.status_var,
            text_color=("gray40", "gray70"),
            font=ctk.CTkFont(size=11),
        ).grid(row=2, column=0, sticky="w", pady=(2, 6))

        self.convert_btn = ctk.CTkButton(
            bottom, text="🚀  开始转换", height=42,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._start_conversion,
        )
        self.convert_btn.grid(row=3, column=0, sticky="ew", pady=(2, 0))

        # 日志区
        log_frame = ctk.CTkFrame(self.root)
        log_frame.grid(row=2, column=0, columnspan=2, sticky="nsew",
                       padx=12, pady=(0, 12))
        self.root.grid_rowconfigure(2, weight=0)
        log_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            log_frame, text="日志",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(8, 2))

        self.log_box = ctk.CTkTextbox(
            log_frame, height=130, wrap="word",
            font=ctk.CTkFont(family="Consolas", size=11),
        )
        self.log_box.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.log_box.configure(state="disabled")

        self._on_mode_change()

    def _bind_dnd(self):
        self.drop_zone.drop_target_register(DND_FILES)
        self.drop_zone.dnd_bind("<<Drop>>", self._on_drop)
        self.drop_zone.dnd_bind("<<DragEnter>>", self._on_drag_enter)
        self.drop_zone.dnd_bind("<<DragLeave>>", self._on_drag_leave)

        self.file_list.drop_target_register(DND_FILES)
        self.file_list.dnd_bind("<<Drop>>", self._on_drop)

    # ---------- 事件处理 ----------
    def _on_drag_enter(self, _event):
        self.drop_zone.configure(border_color=("#22c55e", "#16a34a"))

    def _on_drag_leave(self, _event):
        self.drop_zone.configure(border_color=("#3a86ff", "#2563eb"))

    def _on_drop(self, event):
        self._on_drag_leave(None)
        paths = self.root.tk.splitlist(event.data)
        added = self.file_list.add_files(paths)
        if added:
            self._log(f"已添加 {added} 个文件")
        else:
            self._log("未添加新文件（可能格式不支持或重复）")
        self._refresh_count()

    def _pick_files(self):
        filetypes = [
            ("支持的文档", " ".join(f"*{e}" for e in sorted(SUPPORTED_EXTENSIONS))),
            ("所有文件", "*.*"),
        ]
        paths = filedialog.askopenfilenames(title="选择文件", filetypes=filetypes)
        if paths:
            added = self.file_list.add_files(paths)
            self._log(f"已添加 {added} 个文件")
            self._refresh_count()

    def _pick_dir(self):
        d = filedialog.askdirectory(title="选择输出目录")
        if d:
            self.output_dir_var.set(d)
            self.output_mode.set("custom")
            self._save_settings()

    def _clear_files(self):
        self.file_list.clear()
        self._refresh_count()
        self._log("已清空文件列表")

    def _refresh_count(self):
        self.count_lbl.configure(text=f"共 {len(self.file_list)} 个文件")

    def _on_mode_change(self):
        is_custom = self.output_mode.get() == "custom"
        self.dir_entry.configure(state="normal" if is_custom else "disabled")
        self.browse_btn.configure(state="normal" if is_custom else "disabled")
        self._save_settings()

    def _toggle_theme(self):
        current = ctk.get_appearance_mode()
        ctk.set_appearance_mode("Light" if current == "Dark" else "Dark")
        self._save_settings()

    def _on_close(self):
        self._save_settings()
        self.root.destroy()

    def _open_output_dir(self):
        target = self._resolve_output_dir()
        if target and Path(target).exists():
            os.startfile(target)
        else:
            messagebox.showinfo("提示", "输出目录尚不存在，开始转换后会自动创建。")

    def _resolve_output_dir(self) -> str | None:
        if self.output_mode.get() == "custom":
            d = self.output_dir_var.get().strip()
            return d or None
        return None

    # ---------- 设置持久化 ----------
    def _save_settings(self):
        self.cfg.update({
            "engine": self.engine_var.get(),
            "vision_base_url": self.vision_url_var.get().strip(),
            "vision_model": self.vision_model_var.get().strip() or "glm-4v-flash",
            "output_mode": self.output_mode.get(),
            "output_dir": self.output_dir_var.get().strip(),
            "appearance_mode": ctk.get_appearance_mode(),
        })
        # 注意：vision_api_key 不写入 config.json，仅通过 .env / 环境变量管理
        try:
            settings.save(self.cfg)
        except OSError:
            pass

    # ---------- 视觉设置 ----------
    def _toggle_zhipu_key_visibility(self):
        if self.zhipu_key_entry.cget("show") == "*":
            self.zhipu_key_entry.configure(show="")
            self.show_zhipu_btn.configure(text="🙈")
        else:
            self.zhipu_key_entry.configure(show="*")
            self.show_zhipu_btn.configure(text="👁")

    def _save_zhipu_settings(self):
        self._save_settings()
        self._log("智谱 GLM-4V-Flash 设置已保存")
        self.status_var.set("就绪")

    # ---------- 转换 ----------
    def _start_conversion(self):
        paths = self.file_list.paths()
        if not paths:
            messagebox.showwarning("提示", "请先添加要转换的文件")
            return

        out_dir = self._resolve_output_dir()
        if self.output_mode.get() == "custom" and not out_dir:
            messagebox.showwarning("提示", "请选择输出目录，或改用“与源文件同目录”")
            return

        # 视觉引擎预检（智谱 GLM-4V-Flash）
        if self.engine_var.get() == ENGINE_VISION:
            key = self.zhipu_key_var.get().strip()
            if not key:
                if messagebox.askyesno(
                    "未配置智谱 API Key",
                    "使用 GLM-4V-Flash 视觉引擎需要智谱 API Key（免费申请：open.bigmodel.cn）。\n\n"
                    "当前未配置 Key，是否切换为“自动”模式继续转换？",
                ):
                    self.engine_var.set(ENGINE_AUTO)
                else:
                    return

        self.convert_btn.configure(state="disabled", text="转换中…")
        self.progress.set(0)
        self.status_var.set("开始转换…")
        self._log(f"开始转换 {len(paths)} 个文件")

        thread = threading.Thread(
            target=self._convert_worker, args=(paths, out_dir), daemon=True,
        )
        thread.start()

    def _convert_worker(self, paths, out_dir):
        total = len(paths)
        success = 0
        failed = 0
        engine = self.engine_var.get()
        vision_url = self.vision_url_var.get().strip() or "https://open.bigmodel.cn/api/paas/v4"
        vision_model = self.vision_model_var.get().strip() or "glm-4v-flash"
        vision_api_key = self.zhipu_key_var.get().strip()
        vision_dpi = int(self.cfg.get("vision_dpi", 150))

        for i, p in enumerate(paths):
            name = Path(p).name

            def on_progress(cur, tot, msg, _i=i, _total=total):
                overall = (_i + (cur / tot if tot else 0)) / _total
                self.root.after(0, self._set_progress, min(overall, 0.999))
                self._post_status(f"[{_i + 1}/{_total}] {name} — {msg}")
                self._post_log(f"    · {msg}")

            try:
                self._post_log(f"[{i + 1}/{total}] 转换中: {name}（引擎: {engine}）")
                self._post_status(f"[{i + 1}/{total}] {name}")
                result = convert_file(
                    p, out_dir,
                    engine=engine,
                    vision_base_url=vision_url,
                    vision_model=vision_model,
                    vision_api_key=vision_api_key,
                    vision_dpi=vision_dpi,
                    progress_cb=on_progress,
                )
                self._post_log(f"    ✓ -> {result}")
                success += 1
            except Exception as e:
                failed += 1
                self._post_log(f"    ✗ 失败: {e}")
                self._post_log(traceback.format_exc().strip().splitlines()[-1])
            self.root.after(0, self._set_progress, (i + 1) / total)

        msg = f"完成：成功 {success}，失败 {failed}"
        self._post_log(msg)
        self._post_status(msg)
        self.root.after(0, self._conversion_done, failed == 0)

    def _conversion_done(self, all_ok):
        self.convert_btn.configure(state="normal", text="🚀  开始转换")
        if all_ok:
            messagebox.showinfo("完成", "全部转换成功！")
        else:
            messagebox.showwarning("完成（有错误）", "部分文件转换失败，请查看日志。")

    def _set_progress(self, value: float):
        self.progress.set(value)

    # ---------- 线程安全日志 ----------
    def _log(self, text: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self._append_log(f"[{ts}] {text}\n")

    def _post_log(self, text: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.root.after(0, self._append_log, f"[{ts}] {text}\n")

    def _post_status(self, text: str):
        self.root.after(0, self.status_var.set, text)

    def _append_log(self, text: str):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", text)
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    # ---------- 启动 ----------
    def run(self):
        self.root.mainloop()


def main():
    app = ConverterApp()
    app.run()


if __name__ == "__main__":
    main()
