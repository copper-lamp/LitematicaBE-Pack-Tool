#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LitematicaBE 资源包生成工具
==========================

从 Java 版原版资源包自动生成基岩版 LitematicaBE 投影材质包。

功能特点：
- 自动裁剪多面贴图（如草方块侧面），只保留顶部一面
- 支持分辨率缩放（1x / 0.5x / 0.25x）
- 为每个方块生成 normal（白色）和 error（红色）两种粒子
- 生成符合基岩版格式的 manifest.json

使用方法：
    pip install Pillow
    python generate_pack.py

作者：LitematicaBE
许可证：MIT
"""

import os
import sys
import json
import zipfile
import uuid
import shutil
import tempfile
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from datetime import datetime

# =============================================================================
# 依赖检查
# =============================================================================
try:
    from PIL import Image
except ImportError:
    # 如果缺少 Pillow，显示错误对话框后退出
    _r = tk.Tk()
    _r.withdraw()
    messagebox.showerror(
        "依赖缺失",
        "需要安装 Pillow 库\n\n请运行: pip install Pillow",
    )
    sys.exit(1)

# =============================================================================
# 常量定义
# =============================================================================
FONT_FAMILY = "黑体"
FONT_FAMILY_CODE = "Consolas"

SCRIPT_DIR = Path(__file__).parent.resolve()  # 脚本所在目录
PACK_ICON = SCRIPT_DIR / "pack_icon.png"       # 资源包图标路径
RESOLUTION_MAP = {"1x": 1.0, "0.5x": 0.5, "0.25x": 0.25}  # 分辨率缩放映射

# 提示文本：原始资源目录
SRC_DIR_TIP = (
    "请提取 Java 版原版资源包中的 assets/minecraft/textures 目录。\n\n"
    "提取方法：\n"
    "1. 使用压缩软件打开 .minecraft/versions/<版本>/<版本>.jar\n"
    "2. 解压 assets/minecraft/textures 目录\n"
    "3. 选择解压后的 textures 文件夹作为输入目录"
)

# 提示文本：粒子持续时间
LIFETIME_TIP = (
    "粒子存活时间（秒）。\n\n"
    "请将插件配置文件 config.json 中\n"
    "particleRespawn.lifetime 修改为相同值，\n"
    "以支持此材质包的正常显示。\n\n"
    "默认 45 秒。"
)


# =============================================================================
# 工具类：鼠标悬停提示
# =============================================================================
class ToolTip:
    """为 tkinter 控件添加鼠标悬停提示"""

    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tw = None  # 提示窗口引用
        # 绑定鼠标进入和离开事件
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, _event=None):
        """显示提示窗口"""
        if self.tw:
            return
        # 计算提示窗口位置（控件右下方）
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        # 创建无边框置顶窗口
        self.tw = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.attributes("-topmost", True)
        # 提示标签样式
        lbl = tk.Label(
            tw,
            text=self.text,
            justify="left",
            background="#ffffe0",
            relief="solid",
            borderwidth=1,
            font=(FONT_FAMILY, 9),
            wraplength=320,
        )
        lbl.pack(ipadx=6, ipady=4)

    def _hide(self, _event=None):
        """隐藏提示窗口"""
        if self.tw:
            self.tw.destroy()
            self.tw = None


# =============================================================================
# 核心功能函数
# =============================================================================

def create_particle_json(block_name, texture_path, lifetime, size, tex_size):
    """
    创建正常状态（白色）粒子 JSON

    参数:
        block_name: 方块名称（用于生成粒子 ID）
        texture_path: 贴图路径
        lifetime: 粒子存活时间（秒）
        size: 粒子显示大小
        tex_size: 贴图尺寸（用于 UV 计算）

    返回:
        dict: 粒子 JSON 对象
    """
    return {
        "format_version": "1.10.0",
        "particle_effect": {
            "description": {
                "identifier": f"litematica:block_{block_name}_normal",
                "basic_render_parameters": {
                    "material": "particles_alpha",
                    "texture": f"textures/blocks/{texture_path}",
                },
            },
            "components": {
                # 瞬时发射 1 个粒子
                "minecraft:emitter_rate_instant": {"num_particles": 1},
                # 发射器只执行一次
                "minecraft:emitter_lifetime_once": {},
                # 粒子存活时间
                "minecraft:particle_lifetime_expression": {
                    "max_lifetime": lifetime
                },
                # 静态粒子（无运动）
                "minecraft:particle_motion_static": {},
                # 广告牌渲染（始终面向相机）
                "minecraft:particle_appearance_billboard": {
                    "size": [size, size],
                    "facing_camera_mode": "rotate_xyz",
                    "uv": {
                        "texture_width": tex_size,
                        "texture_height": tex_size,
                        "uv": [0, 0],
                        "uv_size": [tex_size, tex_size],
                    },
                },
                # 白色半透明着色
                "minecraft:particle_appearance_tinting": {
                    "color": [1.0, 1.0, 1.0, 0.6]
                },
            },
        },
    }


def create_error_particle_json(block_name, texture_path, lifetime, size, tex_size):
    """
    创建错误状态（红色）粒子 JSON

    与正常状态的区别：
    - 标识符后缀为 _error
    - 着色为红色（R:1.0, G:0.3, B:0.3），透明度更高
    """
    return {
        "format_version": "1.10.0",
        "particle_effect": {
            "description": {
                "identifier": f"litematica:block_{block_name}_error",
                "basic_render_parameters": {
                    "material": "particles_alpha",
                    "texture": f"textures/blocks/{texture_path}",
                },
            },
            "components": {
                "minecraft:emitter_rate_instant": {"num_particles": 1},
                "minecraft:emitter_lifetime_once": {},
                "minecraft:particle_lifetime_expression": {
                    "max_lifetime": lifetime
                },
                "minecraft:particle_motion_static": {},
                "minecraft:particle_appearance_billboard": {
                    "size": [size, size],
                    "facing_camera_mode": "rotate_xyz",
                    "uv": {
                        "texture_width": tex_size,
                        "texture_height": tex_size,
                        "uv": [0, 0],
                        "uv_size": [tex_size, tex_size],
                    },
                },
                # 红色半透明着色（用于错误提示）
                "minecraft:particle_appearance_tinting": {
                    "color": [1.0, 0.3, 0.3, 0.7]
                },
            },
        },
    }


def process_texture(src_path, scale):
    """
    处理贴图：裁剪多面贴图并缩放

    参数:
        src_path: 源贴图路径
        scale: 缩放比例（1.0 / 0.5 / 0.25）

    返回:
        (Image, int): 处理后的图片对象和最终尺寸
    """
    # 打开图片并转换为 RGBA 模式（支持透明）
    img = Image.open(src_path).convert("RGBA")
    w, h = img.size

    # 裁剪多面贴图：如果高度是宽度的整数倍且大于宽度，只保留顶部一面
    # 例如草方块侧面贴图通常是 16x64（4 个面垂直排列）
    if h > w and h % w == 0:
        img = img.crop((0, 0, w, w))

    w, h = img.size

    # 按指定比例缩放
    if scale != 1.0:
        nw = max(1, round(w * scale))
        nh = max(1, round(h * scale))
        img = img.resize((nw, nh), Image.LANCZOS)  # 使用 LANCZOS 算法保持清晰度
        w, h = nw, nh

    return img, w


def generate_manifest(description):
    """
    生成资源包 manifest.json

    参数:
        description: 资源包描述文本

    返回:
        dict: manifest JSON 对象
    """
    return {
        "format_version": 2,
        "header": {
            "name": "\u00a76LitematicaBE",  # §6 为金色颜色代码
            "description": description,
            "uuid": str(uuid.uuid4()),  # 随机生成 UUID
            "version": [1, 0, 0],
            "min_engine_version": [1, 21, 0],  # 最低支持基岩版 1.21
        },
        "modules": [
            {
                "type": "resources",  # 资源包类型
                "uuid": str(uuid.uuid4()),
                "version": [1, 0, 0],
            }
        ],
    }


def find_block_dir(src_dir):
    """
    查找方块贴图目录

    支持的目录结构：
    - textures/block/
    - assets/minecraft/textures/block/

    返回:
        str: 方块贴图目录路径，未找到返回 None
    """
    candidates = [
        os.path.join(src_dir, "block"),
        os.path.join(src_dir, "assets", "minecraft", "textures", "block"),
    ]
    for c in candidates:
        if os.path.isdir(c):
            return c
    # 如果目录本身包含 PNG 文件，直接返回
    pngs = [f for f in os.listdir(src_dir) if f.endswith(".png")]
    if pngs:
        return src_dir
    return None


# =============================================================================
# 颜色常量（白色调）
# =============================================================================
COLOR_BG = "#f5f5f5"
COLOR_HEADER = "#ffffff"
COLOR_ACCENT = "#666666"
COLOR_CARD = "#ffffff"
COLOR_PRIMARY = "#333333"
COLOR_TEXT = "#555555"
COLOR_MUTED = "#999999"


# =============================================================================
# GUI 主窗口类
# =============================================================================
class App(tk.Tk):
    """LitematicaBE 资源包生成工具主窗口"""

    def __init__(self):
        super().__init__()
        self.title("LitematicaBE 资源包生成工具")
        self.geometry("600x580")
        self.resizable(False, False)
        self.configure(bg=COLOR_BG)

        self._setup_styles()
        self._build_ui()

    def _setup_styles(self):
        """配置界面样式"""
        style = ttk.Style(self)
        available = style.theme_names()
        if "vista" in available:
            style.theme_use("vista")
        elif "clam" in available:
            style.theme_use("clam")

        style.configure("Title.TLabel", font=(FONT_FAMILY, 17, "bold"), foreground=COLOR_PRIMARY)
        style.configure("Sub.TLabel", font=(FONT_FAMILY, 9), foreground=COLOR_MUTED)
        style.configure("Field.TLabel", font=(FONT_FAMILY, 10), foreground=COLOR_PRIMARY)
        style.configure("Help.TLabel", foreground="#1976D2", font=(FONT_FAMILY, 11, "bold"))
        style.configure(
            "Gen.TButton",
            font=(FONT_FAMILY, 12, "bold"),
            padding=(30, 10),
        )
        style.configure("LogH.TLabel", font=(FONT_FAMILY, 10, "bold"), foreground=COLOR_PRIMARY)

    def _build_ui(self):
        """构建用户界面"""

        # ---- 顶部标题栏 ----
        header = tk.Frame(self, bg=COLOR_HEADER, height=72)
        header.pack(fill="x")
        header.pack_propagate(False)

        header_inner = tk.Frame(header, bg=COLOR_HEADER)
        header_inner.pack(side="left", fill="both", expand=True, padx=24, pady=(12, 0))
        tk.Label(
            header_inner,
            text="LitematicaBE 资源包生成工具",
            font=(FONT_FAMILY, 17, "bold"),
            fg=COLOR_PRIMARY,
            bg=COLOR_HEADER,
        ).pack(anchor="w")
        tk.Label(
            header_inner,
            text="从 Java 版原版资源包生成基岩版投影材质包",
            font=(FONT_FAMILY, 9),
            fg=COLOR_MUTED,
            bg=COLOR_HEADER,
        ).pack(anchor="w", pady=(2, 0))

        # ---- 主体区域 ----
        body = tk.Frame(self, bg=COLOR_BG)
        body.pack(fill="both", expand=True, padx=16, pady=12)

        # 设置卡片
        card = tk.Frame(body, bg=COLOR_CARD, highlightbackground="#e0e0e6",
                        highlightthickness=1, padx=18, pady=16)
        card.pack(fill="x")

        self._build_src_dir(card)
        self._build_lifetime(card)
        self._build_scale(card)
        self._build_size(card)
        self._build_output(card)

        # 生成按钮
        self.gen_btn = tk.Button(
            body,
            text="生成资源包",
            font=(FONT_FAMILY, 13, "bold"),
            bg="#4a4a4a",
            fg="#ffffff",
            activebackground="#333333",
            activeforeground="#ffffff",
            relief="flat",
            cursor="hand2",
            padx=40,
            pady=10,
            bd=0,
            command=self._on_generate,
        )
        self.gen_btn.pack(pady=(14, 8))

        # 进度条
        self.progress = ttk.Progressbar(body, mode="determinate")
        self.progress.pack(fill="x")
        self.progress_label = tk.Label(
            body,
            text="",
            font=(FONT_FAMILY, 9),
            fg=COLOR_MUTED,
            bg=COLOR_BG,
        )
        self.progress_label.pack(pady=(2, 8))

        # 日志标签
        tk.Label(
            body,
            text="输出日志",
            font=(FONT_FAMILY, 10, "bold"),
            fg=COLOR_PRIMARY,
            bg=COLOR_BG,
        ).pack(anchor="w")

        # 日志区域
        log_frame = tk.Frame(body, bg=COLOR_BG)
        log_frame.pack(fill="both", expand=True)
        self.log_text = tk.Text(
            log_frame,
            height=7,
            font=(FONT_FAMILY_CODE, 9),
            bg="#1e1e1e",
            fg="#d4d4d4",
            insertbackground="white",
            relief="flat",
            borderwidth=1,
            wrap="word",
            padx=8,
            pady=6,
        )
        sb = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=sb.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # 日志颜色标签
        self.log_text.tag_configure("info", foreground="#9cdcfe")
        self.log_text.tag_configure("ok", foreground="#6a9955")
        self.log_text.tag_configure("err", foreground="#f44747")
        self.log_text.tag_configure("warn", foreground="#dcdcaa")

    def _card_row(self, parent, label_text, **kw):
        """创建一行带标签的卡片行"""
        f = tk.Frame(parent, bg=COLOR_CARD)
        f.pack(fill="x", pady=5)
        tk.Label(f, text=label_text, font=(FONT_FAMILY, 10),
                 fg=COLOR_PRIMARY, bg=COLOR_CARD, width=14, anchor="w").pack(side="left")
        return f

    def _build_src_dir(self, parent):
        """构建原始资源目录输入行"""
        f = self._card_row(parent, "原始资源目录")
        self.src_var = tk.StringVar()
        ent = tk.Entry(
            f, textvariable=self.src_var,
            font=(FONT_FAMILY, 10),
            relief="solid", bd=1, bg="#fafafa",
        )
        ent.pack(side="left", fill="x", expand=True, padx=(0, 4))
        tk.Button(
            f, text="浏览", width=6,
            font=(FONT_FAMILY, 9),
            relief="flat", bg="#e0e0e6", fg=COLOR_PRIMARY,
            activebackground="#d0d0d6", cursor="hand2", bd=0,
            command=self._browse_src,
        ).pack(side="left", padx=(0, 4))
        h = tk.Label(f, text=" ?", font=(FONT_FAMILY, 12, "bold"),
                     fg="#1976D2", bg=COLOR_CARD, cursor="hand2")
        h.pack(side="left")
        ToolTip(h, SRC_DIR_TIP)

    def _build_lifetime(self, parent):
        """构建粒子持续时间输入行"""
        f = self._card_row(parent, "粒子持续时间")
        self.lifetime_var = tk.StringVar(value="45")
        tk.Entry(
            f, textvariable=self.lifetime_var, width=7,
            font=(FONT_FAMILY, 10),
            relief="solid", bd=1, bg="#fafafa",
        ).pack(side="left")
        tk.Label(f, text=" 秒", font=(FONT_FAMILY, 10),
                 fg=COLOR_MUTED, bg=COLOR_CARD).pack(side="left")
        h = tk.Label(f, text=" ?", font=(FONT_FAMILY, 12, "bold"),
                     fg="#1976D2", bg=COLOR_CARD, cursor="hand2")
        h.pack(side="left", padx=(12, 0))
        ToolTip(h, LIFETIME_TIP)

    def _build_scale(self, parent):
        """构建分辨率缩放下拉框"""
        f = self._card_row(parent, "分辨率缩放")
        self.scale_var = tk.StringVar(value="1x")
        cb = ttk.Combobox(
            f, textvariable=self.scale_var,
            values=["1x", "0.5x", "0.25x"],
            state="readonly", width=8,
            font=(FONT_FAMILY, 10),
        )
        cb.pack(side="left")

    def _build_size(self, parent):
        """构建粒子大小滑块"""
        f = self._card_row(parent, "粒子大小")
        self.size_var = tk.DoubleVar(value=1.0)
        sl = ttk.Scale(
            f, from_=0.42, to=1.50,
            variable=self.size_var,
            orient="horizontal",
            command=self._on_size,
        )
        sl.pack(side="left", fill="x", expand=True)
        self.size_lbl = tk.Label(
            f, text="1.00", width=5,
            font=(FONT_FAMILY, 10, "bold"),
            fg=COLOR_PRIMARY, bg=COLOR_CARD,
        )
        self.size_lbl.pack(side="left", padx=(8, 0))

    def _build_output(self, parent):
        """构建输出文件输入行"""
        f = self._card_row(parent, "输出文件")
        default_out = str(SCRIPT_DIR / "LitematicaBE.mcpack")
        self.out_var = tk.StringVar(value=default_out)
        tk.Entry(
            f, textvariable=self.out_var,
            font=(FONT_FAMILY, 10),
            relief="solid", bd=1, bg="#fafafa",
        ).pack(side="left", fill="x", expand=True, padx=(0, 4))
        tk.Button(
            f, text="浏览", width=6,
            font=(FONT_FAMILY, 9),
            relief="flat", bg="#e0e0e6", fg=COLOR_PRIMARY,
            activebackground="#d0d0d6", cursor="hand2", bd=0,
            command=self._browse_out,
        ).pack(side="left")

    def _browse_src(self):
        """浏览选择原始资源目录"""
        d = filedialog.askdirectory(title="选择 Java 版资源包的 textures 目录")
        if d:
            self.src_var.set(d)

    def _browse_out(self):
        """浏览选择输出文件路径"""
        f = filedialog.asksaveasfilename(
            title="保存资源包",
            defaultextension=".mcpack",
            filetypes=[("Minecraft 资源包", "*.mcpack"), ("所有文件", "*.*")],
        )
        if f:
            self.out_var.set(f)

    def _on_size(self, val):
        """滑块值变化时更新显示"""
        self.size_lbl.config(text=f"{float(val):.2f}")

    def _log(self, msg, tag="info"):
        """
        添加日志到输出区域

        参数:
            msg: 日志内容
            tag: 颜色标签（info/ok/err/warn）
        """
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{ts}] {msg}\n", tag)
        self.log_text.see("end")
        self.update_idletasks()

    def _on_generate(self):
        """生成按钮点击处理"""
        # 验证输入
        src = self.src_var.get().strip()
        if not src or not os.path.isdir(src):
            messagebox.showerror("错误", "请选择有效的原始资源目录")
            return

        try:
            lt = float(self.lifetime_var.get())
            if lt <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("错误", "粒子持续时间必须为正数")
            return

        scale = RESOLUTION_MAP.get(self.scale_var.get(), 1.0)
        size = round(self.size_var.get(), 2)
        out = self.out_var.get().strip()
        if not out:
            messagebox.showerror("错误", "请指定输出文件路径")
            return

        # 禁用生成按钮，重置进度
        self.gen_btn.config(state="disabled")
        self.progress["value"] = 0
        self.progress_label.config(text="")
        self.log_text.delete("1.0", "end")

        try:
            self._do_generate(src, out, lt, size, scale)
        except Exception as e:
            self._log(f"❌ 生成失败: {e}", "err")
            messagebox.showerror("错误", str(e))
        finally:
            self.gen_btn.config(state="normal")

    def _do_generate(self, src_dir, output_path, lifetime, size, scale):
        """
        执行资源包生成 — 只生成方块粒子，不复制无关纹理

        参数:
            src_dir: 原始资源目录
            output_path: 输出文件路径
            lifetime: 粒子存活时间
            size: 粒子大小
            scale: 分辨率缩放比例
        """
        self._log("开始生成资源包...", "info")

        # 查找方块贴图目录
        block_dir = find_block_dir(src_dir)
        if not block_dir:
            raise FileNotFoundError(f"在 {src_dir} 中未找到 block 子目录")

        # 获取所有方块贴图文件（排除 .mcmeta 元文件）
        textures = sorted(
            f
            for f in os.listdir(block_dir)
            if f.lower().endswith(".png") and not f.lower().endswith(".png.mcmeta")
        )
        self._log(f"找到 {len(textures)} 个方块贴图", "info")
        self.progress["maximum"] = len(textures) + 3  # +3 给 manifest / 图标 / 打包

        # 使用临时目录构建资源包结构
        with tempfile.TemporaryDirectory() as tmp:
            t_block = os.path.join(tmp, "textures", "blocks")
            t_part = os.path.join(tmp, "particles")
            os.makedirs(t_block)
            os.makedirs(t_part)

            processed = 0
            errors = 0

            # 处理每个方块贴图
            for tex_file in textures:
                tex_name = tex_file[:-4]  # 去掉 .png 后缀
                src_path = os.path.join(block_dir, tex_file)
                try:
                    # 处理贴图（裁剪 + 缩放）
                    img, tex_px = process_texture(src_path, scale)
                    img.save(os.path.join(t_block, tex_file))

                    # 生成两种粒子 JSON
                    normal = create_particle_json(tex_name, tex_name, lifetime, size, tex_px)
                    error_p = create_error_particle_json(tex_name, tex_name, lifetime, size, tex_px)

                    with open(
                        os.path.join(t_part, f"block_{tex_name}_normal.json"),
                        "w",
                        encoding="utf-8",
                    ) as fp:
                        json.dump(normal, fp, indent=2, ensure_ascii=False)
                    with open(
                        os.path.join(t_part, f"block_{tex_name}_error.json"),
                        "w",
                        encoding="utf-8",
                    ) as fp:
                        json.dump(error_p, fp, indent=2, ensure_ascii=False)

                    processed += 1
                except Exception as e:
                    errors += 1
                    self._log(f"⚠ 跳过 {tex_file}: {e}", "warn")

                # 更新进度条
                self.progress["value"] = processed + errors
                if (processed + errors) % 50 == 0 or (processed + errors) == len(textures):
                    self.progress_label.config(
                        text=f"{processed + errors} / {len(textures)} 贴图已处理"
                    )
                    self.update_idletasks()

            self._log(f"贴图处理完成: {processed} 成功, {errors} 跳过", "ok")
            self.progress["value"] += 1

            # 生成 manifest.json
            scale_label = self.scale_var.get()
            desc = (
                f"LitematicaBE投影材质包 | "
                f"{processed}种方块粒子 | "
                f"分辨率{scale_label} | "
                f"粒子大小{size} | "
                f"持续{int(lifetime)}秒"
            )
            manifest = generate_manifest(desc)
            with open(os.path.join(tmp, "manifest.json"), "w", encoding="utf-8") as fp:
                json.dump(manifest, fp, indent=2, ensure_ascii=False)
            self._log("生成 manifest.json", "ok")
            self.progress["value"] += 1

            # 复制图标
            if PACK_ICON.exists():
                shutil.copy2(str(PACK_ICON), os.path.join(tmp, "pack_icon.png"))
                self._log("复制 pack_icon.png", "ok")
            else:
                self._log("⚠ 未找到 pack_icon.png，跳过图标", "warn")
            self.progress["value"] += 1

            # 打包为 .mcpack
            self._log("打包 .mcpack 文件...", "info")
            out_dir = os.path.dirname(os.path.abspath(output_path))
            os.makedirs(out_dir, exist_ok=True)
            self._pack(tmp, output_path)

            # 完成
            self.progress["value"] = self.progress["maximum"]
            self.progress_label.config(text="✅ 完成!")
            self._log(f"✔ 资源包已生成: {output_path}", "ok")
            self._log(
                f"共 {processed} 种方块, {processed * 2} 个粒子文件",
                "ok",
            )

            # 显示文件大小
            fsize = os.path.getsize(output_path)
            if fsize > 1024 * 1024:
                sz = f"{fsize / 1024 / 1024:.2f} MB"
            else:
                sz = f"{fsize / 1024:.1f} KB"
            self._log(f"文件大小: {sz}", "ok")

    def _pack(self, src_dir, output_path):
        """
        将目录打包为 zip（.mcpack）

        参数:
            src_dir: 源目录
            output_path: 输出 zip 文件路径
        """
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _dirs, files in os.walk(src_dir):
                for fname in files:
                    fpath = os.path.join(root, fname)
                    # 使用正斜杠作为路径分隔符（跨平台兼容）
                    arcname = os.path.relpath(fpath, src_dir).replace("\\", "/")
                    zf.write(fpath, arcname)


# =============================================================================
# 程序入口
# =============================================================================
if __name__ == "__main__":
    app = App()
    app.mainloop()
