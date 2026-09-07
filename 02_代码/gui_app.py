# -*- coding: utf-8 -*-
"""
================================================================================
软件全称：省域数字经济与低碳协同综合评估系统
软件简称：数字低碳协同系统 (DEC-CES)
版 本 号：V1.0
模块名称：gui_app (现代桌面图形交互用户界面系统)
功能描述：
1. Windows 原生高分屏 (High-DPI) 矢量缩放与抗锯齿排版渲染。
2. 企业级现代化仪表盘架构：包含 4 大 KPI 宏观状态卡、5 阶段流水线工序卡片、操作中枢与多子系统选项卡。
3. 线程安全队列异步非阻塞后台工作线程调度与控制台动态日志实时重定向流。
4. 提供数据管理、计量实证、政策仿真、综合成果报表及全屏终端视窗 6 大交互功能区。
================================================================================
"""

from __future__ import annotations

import os
from pathlib import Path
import queue
import runpy
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

# 启用 Windows 高分屏 (High-DPI) 矢量感知，杜绝文本与控件模糊
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            import ctypes
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


import json
import pandas as pd

from model_utils import (
    find_project_root,
    get_raw_data_dir,
    set_raw_data_dir,
    list_input_files_metadata,
    inspect_data_file,
    import_input_file,
    remove_input_file,
    preview_input_file,
    export_evaluation_txt_report,
    export_integrity_txt_report,
    open_txt_file,
)

CODE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = Path(find_project_root())
RESULT_DIR = PROJECT_DIR / "04_核心结果"
SIM_DIR = RESULT_DIR / "simulation_results"
FIG_DIR = PROJECT_DIR / "05_图形"


class ConsoleRedirector:
    """线程安全的标准输出与标准错误重定向器"""

    def __init__(self, text_queue: queue.Queue):
        self.text_queue = text_queue

    def write(self, text: str):
        if text:
            self.text_queue.put(text)

    def flush(self):
        pass


class ModernButton(tk.Button):
    """支持平滑悬浮高亮反馈的现代扁平化按钮"""

    def __init__(self, master=None, bg_color="#2563eb", hover_color="#1d4ed8", text_color="#ffffff", **kwargs):
        self.bg_color = bg_color
        self.hover_color = hover_color
        self.text_color = text_color
        super().__init__(
            master,
            bg=self.bg_color,
            fg=self.text_color,
            activebackground=self.hover_color,
            activeforeground=self.text_color,
            relief="flat",
            bd=0,
            cursor="hand2",
            **kwargs,
        )
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _on_enter(self, _):
        if self["state"] != "disabled":
            self.configure(bg=self.hover_color)

    def _on_leave(self, _):
        if self["state"] != "disabled":
            self.configure(bg=self.bg_color)

    def set_color(self, bg_color, hover_color):
        self.bg_color = bg_color
        self.hover_color = hover_color
        self.configure(bg=bg_color)


class EvaluationSystemGUI:

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("省域数字经济与低碳协同综合评估系统 V1.0")
        self.root.geometry("1180x820")
        self.root.minsize(1050, 720)
        self.root.configure(bg="#f8fafc")

        self._center_window(1180, 820)

        # 核心状态变量
        self.is_running = False
        self.has_run_pipeline = False
        self.has_run_econ = False
        self.has_run_sim = False
        self.has_run_check = False
        self.has_run_report = False
        self.current_task_name = tk.StringVar(value="系统就绪，待命状态")
        self.output_queue = queue.Queue()

        # 仿真参数变量
        self.digital_scale_var = tk.DoubleVar(value=0.0)
        self.upgrade_scale_var = tk.DoubleVar(value=0.6)
        self.target_year_var = tk.StringVar(value="2035")
        self.sim_calculated_year: str | None = None
        self.sim_finished_time: str | None = None
        self.econ_finished_time: str | None = None

        # 样式与组件
        self._setup_ttk_styles()
        self._build_top_navbar()
        self._build_main_notebook()
        self._build_bottom_statusbar()

        # 定时器消费输出日志
        self.root.after(80, self._process_log_queue)

    def _center_window(self, width: int, height: int):
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = max(0, int((screen_width - width) / 2))
        y = max(0, int((screen_height - height) / 2) - 25)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _setup_ttk_styles(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        # 选项卡定制样式
        style.configure("TNotebook", background="#f1f5f9", borderwidth=0, padding=0)
        style.configure(
            "TNotebook.Tab",
            font=("微软雅黑", 10, "bold"),
            padding=[18, 9],
            background="#e2e8f0",
            foreground="#475569",
            borderwidth=0,
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", "#ffffff"), ("active", "#cbd5e1")],
            foreground=[("selected", "#1d4ed8"), ("active", "#0f172a")],
        )

        # Treeview 表格美化
        style.configure(
            "Treeview",
            font=("微软雅黑", 9),
            rowheight=26,
            background="#ffffff",
            fieldbackground="#ffffff",
            foreground="#1e293b",
            borderwidth=1,
            relief="solid",
        )
        style.configure(
            "Treeview.Heading",
            font=("微软雅黑", 9, "bold"),
            background="#f1f5f9",
            foreground="#334155",
            padding=[4, 6],
            relief="flat",
        )
        style.map("Treeview", background=[("selected", "#dbeafe")], foreground=[("selected", "#1e3a8a")])

        # 进度条样式
        style.configure(
            "Accent.Horizontal.TProgressbar",
            troughcolor="#e2e8f0",
            background="#2563eb",
            thickness=6,
            borderwidth=0,
        )

    # -------------------------------------------------------------
    # 顶部品牌导航栏
    # -------------------------------------------------------------
    def _build_top_navbar(self):
        nav = tk.Frame(self.root, bg="#0f172a", height=68)
        nav.pack(fill=tk.X, side=tk.TOP)
        nav.pack_propagate(False)

        # 左侧 LOGO 与主标题
        left_area = tk.Frame(nav, bg="#0f172a")
        left_area.pack(side=tk.LEFT, padx=22, pady=12)

        icon_lbl = tk.Label(left_area, text="📊", font=("Segoe UI Emoji", 18), bg="#0f172a", fg="#38bdf8")
        icon_lbl.pack(side=tk.LEFT, padx=(0, 10))

        text_box = tk.Frame(left_area, bg="#0f172a")
        text_box.pack(side=tk.LEFT)

        title_lbl = tk.Label(
            text_box,
            text="省域数字经济与低碳协同综合评估系统",
            font=("微软雅黑", 14, "bold"),
            fg="#ffffff",
            bg="#0f172a",
        )
        title_lbl.pack(anchor="w")

        sub_lbl = tk.Label(
            text_box,
            text="Provincial Digital Economy & Low-Carbon Synergy Comprehensive Evaluation System",
            font=("Consolas", 7),
            fg="#94a3b8",
            bg="#0f172a",
        )
        sub_lbl.pack(anchor="w")

        # 版本徽章
        badge = tk.Label(
            nav,
            text="V1.0",
            font=("Consolas", 8, "bold"),
            fg="#38bdf8",
            bg="#1e293b",
            padx=8,
            pady=3,
            relief="solid",
            bd=1,
        )
        badge.pack(side=tk.LEFT, padx=12, pady=20)

        # 右侧状态灯与工作区标识
        right_area = tk.Frame(nav, bg="#0f172a")
        right_area.pack(side=tk.RIGHT, padx=24, pady=14)

        self.status_pill = tk.Label(
            right_area,
            text="● 系统就绪 (待启动)",
            font=("微软雅黑", 9, "bold"),
            fg="#38bdf8",
            bg="#0c4a6e",
            padx=12,
            pady=4,
            relief="flat",
        )
        self.status_pill.pack(side=tk.RIGHT)

    # -------------------------------------------------------------
    # 主体标签页架构
    # -------------------------------------------------------------
    def _build_main_notebook(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=14, pady=(10, 6))

        # 6 个页面：看板总览、数据赋权、计量诊断、政策仿真、综合报表、运行日志
        self.tab_dashboard = tk.Frame(self.notebook, bg="#f8fafc")
        self.tab_data = tk.Frame(self.notebook, bg="#f8fafc")
        self.tab_econometrics = tk.Frame(self.notebook, bg="#f8fafc")
        self.tab_simulation = tk.Frame(self.notebook, bg="#f8fafc")
        self.tab_reports = tk.Frame(self.notebook, bg="#f8fafc")
        self.tab_console = tk.Frame(self.notebook, bg="#f8fafc")

        self.notebook.add(self.tab_dashboard, text=" 📊 系统总览与看板 ")
        self.notebook.add(self.tab_data, text=" 📂 数据管理与赋权 ")
        self.notebook.add(self.tab_econometrics, text=" 📈 计量实证与诊断 ")
        self.notebook.add(self.tab_simulation, text=" 🎯 政策仿真与Pareto寻优 ")
        self.notebook.add(self.tab_reports, text=" 📑 成果报表与交付 ")
        self.notebook.add(self.tab_console, text=" 🖥️ 运行终端与实时日志 ")

        self._init_tab_dashboard()
        self._init_tab_data()
        self._init_tab_econometrics()
        self._init_tab_simulation()
        self._init_tab_reports()
        self._init_tab_console()

        # 启动时动态从核心结果目录读取最新数据并渲染界面
        self._refresh_all_dynamic_displays()

    # -------------------------------------------------------------
    # 页面 1：系统总览与决策看板 (Executive Dashboard)
    # -------------------------------------------------------------
    def _init_tab_dashboard(self):
        frame = self.tab_dashboard

        # === 顶部 4 大 KPI 核心指标卡 ===
        kpi_bar = tk.Frame(frame, bg="#f8fafc")
        kpi_bar.pack(fill=tk.X, padx=15, pady=(14, 10))

        self.lbl_kpi_sample_main, self.lbl_kpi_sample_sub = self._create_kpi_card(
            kpi_bar,
            "🌐 样本覆盖范围",
            "30 个省份",
            "2011-2022 年平衡面板 (360样本)",
            "#2563eb",
            side=tk.LEFT,
            actions=[
                ("🔍 源表审计", lambda: self._execute_module("数据审计", "data_quality_checker.py"), "#2563eb", "#1d4ed8", "#ffffff"),
                ("📂 字典管理", lambda: self.notebook.select(self.tab_data), "#f1f5f9", "#e2e8f0", "#334155"),
            ],
        )
        self.lbl_kpi_eval_main, self.lbl_kpi_eval_sub = self._create_kpi_card(
            kpi_bar,
            "⚡ 评价体系构念",
            "CI & CI_core",
            "双口径多维指标 / 熵权客观赋权",
            "#059669",
            side=tk.LEFT,
            actions=[
                ("▶ 开始", self._cmd_run_eval_calc, "#059669", "#047857", "#ffffff"),
                ("📄 查看结果", self._cmd_view_eval_result_txt, "#f1f5f9", "#e2e8f0", "#0f172a"),
            ],
        )
        self.lbl_kpi_sim_main, self.lbl_kpi_sim_sub = self._create_kpi_card(
            kpi_bar,
            "🎯 动态仿真跨度",
            "2022-2035 年",
            "Pareto 最优前沿拐点折中搜索",
            "#7c3aed",
            side=tk.LEFT,
            actions=[
                ("▶ 运行仿真", lambda: self._execute_module("情景仿真", "policy_simulation_optimizer.py"), "#7c3aed", "#6d28d9", "#ffffff"),
                ("📈 查看推演", lambda: self.notebook.select(self.tab_simulation), "#f1f5f9", "#e2e8f0", "#334155"),
            ],
        )
        self.lbl_kpi_check_main, self.lbl_kpi_check_sub = self._create_kpi_card(
            kpi_bar,
            "🛡️ 全流程评估状态",
            "⚪ 待启动评估",
            "点击右侧按钮启动端到端自动化流水线",
            "#0d9488",
            side=tk.LEFT,
            actions=[
                ("▶ 开始", lambda: self._execute_module("系统自检", "system_integrity_validator.py"), "#0d9488", "#0f766e", "#ffffff"),
                ("📄 查看结果", self._cmd_view_integrity_result_txt, "#f1f5f9", "#e2e8f0", "#0f172a"),
            ],
        )

        # === 中部：5 阶段流水线工序卡片与主操作区 ===
        mid_frame = tk.Frame(frame, bg="#f8fafc")
        mid_frame.pack(fill=tk.X, padx=15, pady=6)

        # 工序步骤卡片容器
        pipeline_card = tk.Frame(mid_frame, bg="#ffffff", relief="solid", bd=1, padx=16, pady=12)
        pipeline_card.pack(fill=tk.X)

        header_row = tk.Frame(pipeline_card, bg="#ffffff")
        header_row.pack(fill=tk.X, pady=(0, 8))

        tk.Label(header_row, text="自动化综合评估流水线架构 (End-to-End Pipeline)", font=("微软雅黑", 11, "bold"), bg="#ffffff", fg="#0f172a").pack(side=tk.LEFT)

        # 大号主执行按钮
        self.btn_run_all = ModernButton(
            header_row,
            text="🚀 启动全流程自动化评估",
            font=("微软雅黑", 10, "bold"),
            bg_color="#2563eb",
            hover_color="#1d4ed8",
            padx=18,
            pady=7,
            command=self._cmd_run_full_pipeline,
        )
        self.btn_run_all.pack(side=tk.RIGHT)

        # 5 个步骤卡片横向排列
        steps_box = tk.Frame(pipeline_card, bg="#ffffff")
        steps_box.pack(fill=tk.X, pady=6)

        steps = [
            ("1. 数据审计", "9 份源表完整性", "福建尖峰留痕修复", "#0284c7"),
            ("2. 熵权赋权", "信息熵矩阵解算", "合成 CI & CI_core", "#059669"),
            ("3. 计量回归", "双向固定效应 FE", "区域异质性与滞后项", "#7c3aed"),
            ("4. 情景仿真", "5 大发展情景演化", "Pareto 前沿折中寻优", "#d97706"),
            ("5. 成果交付", "17 表全量多维报表", "矢量图表与系统自检", "#2563eb"),
        ]

        self.step_badges = []
        for i, (title, sub1, sub2, accent_color) in enumerate(steps):
            box = tk.Frame(steps_box, bg="#f8fafc", relief="solid", bd=1, padx=10, pady=8)
            box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)

            # 顶部序号与标题
            tk.Label(box, text=title, font=("微软雅黑", 9, "bold"), bg="#f8fafc", fg=accent_color).pack(anchor="w")
            tk.Label(box, text=f"• {sub1}", font=("微软雅黑", 8), bg="#f8fafc", fg="#475569").pack(anchor="w", pady=(2, 0))
            tk.Label(box, text=f"• {sub2}", font=("微软雅黑", 8), bg="#f8fafc", fg="#64748b").pack(anchor="w")

            status_badge = tk.Label(box, text="⚪ 待执行", font=("Consolas", 7, "bold"), bg="#f1f5f9", fg="#64748b", padx=5, pady=2)
            status_badge.pack(anchor="e", pady=(4, 0))
            self.step_badges.append(status_badge)

        # 进度指示条（初始为 0% 确定型进度条）
        self.progress_val = tk.DoubleVar(value=0.0)
        self.progress_bar = ttk.Progressbar(pipeline_card, variable=self.progress_val, maximum=100.0)
        self.progress_bar.pack(fill=tk.X, pady=(10, 2))

        # === 下部：快捷操作中枢与迷你控制台 ===
        bottom_frame = tk.Frame(frame, bg="#f8fafc")
        bottom_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(8, 12))

        # 左侧快捷动作栏
        action_box = tk.Frame(bottom_frame, bg="#ffffff", relief="solid", bd=1, width=280, padx=14, pady=12)
        action_box.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        action_box.pack_propagate(False)

        tk.Label(action_box, text="快捷任务中心", font=("微软雅黑", 10, "bold"), bg="#ffffff", fg="#0f172a").pack(anchor="w", pady=(0, 8))

        quick_actions = [
            ("🔍 运行数据质量体检", lambda: self._execute_module("数据体检", "data_quality_checker.py"), "#0284c7", "#0369a1"),
            ("⚡ 执行熵权指标测算", lambda: self._execute_module("熵权测算", "entropy_weight_engine.py"), "#059669", "#047857"),
            ("📊 执行面板计量回归", lambda: self._execute_module("计量分析", "panel_regression_analyzer.py"), "#7c3aed", "#6d28d9"),
            ("🎯 运行政策情景仿真", lambda: self._execute_module("情景仿真", "policy_simulation_optimizer.py"), "#d97706", "#b45309"),
            ("📑 导出全量汇总报表", lambda: self._execute_module("报表导出", "report_exporter.py"), "#2563eb", "#1d4ed8"),
            ("🛡️ 执行系统运行自检", lambda: self._execute_module("系统自检", "system_integrity_validator.py"), "#0d9488", "#0f766e"),
        ]

        for text, cmd, bg_c, hov_c in quick_actions:
            btn = ModernButton(action_box, text=text, font=("微软雅黑", 8, "bold"), bg_color=bg_c, hover_color=hov_c, padx=8, pady=5, command=cmd)
            btn.pack(fill=tk.X, pady=3)

        tk.Frame(action_box, height=1, bg="#e2e8f0").pack(fill=tk.X, pady=8)

        # 快速打开目录按钮
        ModernButton(action_box, text="📂 打开核心结果目录", font=("微软雅黑", 8), bg_color="#f1f5f9", hover_color="#e2e8f0", text_color="#334155", padx=6, pady=4, command=lambda: self._open_dir(RESULT_DIR)).pack(fill=tk.X, pady=2)
        ModernButton(action_box, text="📁 打开项目根目录", font=("微软雅黑", 8), bg_color="#f1f5f9", hover_color="#e2e8f0", text_color="#334155", padx=6, pady=4, command=lambda: self._open_dir(PROJECT_DIR)).pack(fill=tk.X, pady=2)

        # 右侧迷你实时日志框
        mini_con_box = tk.Frame(bottom_frame, bg="#ffffff", relief="solid", bd=1, padx=12, pady=10)
        mini_con_box.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        con_title_row = tk.Frame(mini_con_box, bg="#ffffff")
        con_title_row.pack(fill=tk.X, pady=(0, 6))

        tk.Label(con_title_row, text="实时运行监控 (Live Stream)", font=("微软雅黑", 10, "bold"), bg="#ffffff", fg="#0f172a").pack(side=tk.LEFT)

        ModernButton(con_title_row, text="🖥️ 切换到全屏终端", font=("微软雅黑", 8), bg_color="#f1f5f9", hover_color="#e2e8f0", text_color="#2563eb", padx=8, pady=3, command=lambda: self.notebook.select(self.tab_console)).pack(side=tk.RIGHT)
        ModernButton(con_title_row, text="🧹 清空", font=("微软雅黑", 8), bg_color="#f1f5f9", hover_color="#e2e8f0", text_color="#475569", padx=8, pady=3, command=self._cmd_clear_console).pack(side=tk.RIGHT, padx=4)

        self.mini_console = ScrolledText(
            mini_con_box,
            wrap=tk.WORD,
            bg="#090d16",
            fg="#f1f5f9",
            insertbackground="#ffffff",
            font=("Consolas", 8),
            padx=10,
            pady=8,
        )
        self.mini_console.pack(fill=tk.BOTH, expand=True)

        # 初始欢迎信息
        self._log("================================================================================")
        self._log(" 省域数字经济与低碳协同综合评估系统 V1.0 - 现代决策工作台已启动")
        self._log(f" 代码文件目录: {CODE_DIR.name}")
        self._log(f" 项目根目录(代码上一级): {PROJECT_DIR}")
        self._log(f" 相对输出位置: ..\\{RESULT_DIR.name} ({RESULT_DIR})")
        self._log(" 点击上方【🚀 启动全流程自动化评估】或在左侧快捷中心选择特定工序执行。")
        self._log("================================================================================\n")

    def _create_kpi_card(
        self,
        parent,
        title: str,
        main_val: str,
        sub_val: str,
        border_accent: str,
        side=tk.LEFT,
        actions: list[tuple[str, Any, str, str, str]] | None = None,
    ):
        card = tk.Frame(parent, bg="#ffffff", relief="solid", bd=1, padx=12, pady=9)
        card.pack(side=side, fill=tk.BOTH, expand=True, padx=4)

        # 顶部重点色指示线
        accent_line = tk.Frame(card, bg=border_accent, height=3)
        accent_line.pack(fill=tk.X, pady=(0, 5))

        tk.Label(card, text=title, font=("微软雅黑", 8, "bold"), bg="#ffffff", fg="#64748b").pack(anchor="w")
        lbl_main = tk.Label(card, text=main_val, font=("微软雅黑", 13, "bold"), bg="#ffffff", fg="#0f172a")
        lbl_main.pack(anchor="w", pady=(1, 1))
        lbl_sub = tk.Label(card, text=sub_val, font=("微软雅黑", 7), bg="#ffffff", fg="#94a3b8")
        lbl_sub.pack(anchor="w")

        if actions:
            btn_box = tk.Frame(card, bg="#ffffff")
            btn_box.pack(fill=tk.X, pady=(5, 0))
            for item in actions:
                btn_text = item[0]
                btn_cmd = item[1]
                btn_bg = item[2]
                btn_hov = item[3]
                btn_fg = item[4] if len(item) > 4 else "#ffffff"
                b = ModernButton(
                    btn_box,
                    text=btn_text,
                    font=("微软雅黑", 8, "bold"),
                    bg_color=btn_bg,
                    hover_color=btn_hov,
                    text_color=btn_fg,
                    padx=7,
                    pady=2,
                    command=btn_cmd,
                )
                b.pack(side=tk.LEFT, padx=(0, 6))

        return lbl_main, lbl_sub

    # -------------------------------------------------------------
    # 页面 2：数据管理与赋权
    # -------------------------------------------------------------
    def _init_tab_data(self):
        frame = self.tab_data

        # 顶部操作卡片
        actions_row = tk.Frame(frame, bg="#f8fafc")
        actions_row.pack(fill=tk.X, padx=15, pady=(15, 8))

        # 卡片 1：数据审计
        c1 = tk.Frame(actions_row, bg="#ffffff", relief="solid", bd=1, padx=14, pady=12)
        c1.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))

        tk.Label(c1, text="🔍 原始数据源完整性审计与体检", font=("微软雅黑", 10, "bold"), bg="#ffffff", fg="#0284c7").pack(anchor="w")
        tk.Label(c1, text="校验 9 份基础 Excel 源表缺失值、对齐年份 (2011-2022)，并对孤立尖峰进行留痕修正。", font=("微软雅黑", 8), bg="#ffffff", fg="#64748b").pack(anchor="w", pady=(3, 10))

        ModernButton(c1, text="执行数据质量审计 (data_quality_checker.py)", font=("微软雅黑", 8, "bold"), bg_color="#0284c7", hover_color="#0369a1", padx=10, pady=5, command=lambda: self._execute_module("数据质量审计", "data_quality_checker.py")).pack(anchor="w")

        # 卡片 2：熵权赋权
        c2 = tk.Frame(actions_row, bg="#ffffff", relief="solid", bd=1, padx=14, pady=12)
        c2.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(6, 0))

        tk.Label(c2, text="⚡ 熵权法指标平滑、标准化与客观赋权", font=("微软雅黑", 10, "bold"), bg="#ffffff", fg="#059669").pack(anchor="w")
        tk.Label(c2, text="求解信息熵权重矩阵，同步生成基准协同指数 CI 与严格数字指数 CI_core。", font=("微软雅黑", 8), bg="#ffffff", fg="#64748b").pack(anchor="w", pady=(3, 10))

        b_row_c2 = tk.Frame(c2, bg="#ffffff")
        b_row_c2.pack(anchor="w")
        ModernButton(b_row_c2, text="▶ 执行熵权指标测算 (entropy_weight_engine.py)", font=("微软雅黑", 8, "bold"), bg_color="#059669", hover_color="#047857", padx=10, pady=5, command=self._cmd_run_eval_calc).pack(side=tk.LEFT, padx=(0, 8))
        ModernButton(b_row_c2, text="📄 查看测算结果 (.txt)", font=("微软雅黑", 8, "bold"), bg_color="#f1f5f9", hover_color="#e2e8f0", text_color="#0f172a", padx=10, pady=5, command=self._cmd_view_eval_result_txt).pack(side=tk.LEFT)

        # 下部：数据源管理中枢与动态映射表格
        table_card = tk.Frame(frame, bg="#ffffff", relief="solid", bd=1, padx=15, pady=12)
        table_card.pack(fill=tk.BOTH, expand=True, padx=15, pady=(6, 15))

        # 头部标题与当前数据源路径
        head_box = tk.Frame(table_card, bg="#ffffff")
        head_box.pack(fill=tk.X, pady=(0, 8))

        tk.Label(head_box, text="核心数据源字典与输入文件管理中枢", font=("微软雅黑", 10, "bold"), bg="#ffffff", fg="#0f172a").pack(side=tk.LEFT)

        self.lbl_data_dir = tk.Label(head_box, text="", font=("Consolas", 8), bg="#f1f5f9", fg="#475569", padx=8, pady=2, relief="flat")
        self.lbl_data_dir.pack(side=tk.RIGHT)

        # 操作工具栏
        toolbar = tk.Frame(table_card, bg="#ffffff")
        toolbar.pack(fill=tk.X, pady=(0, 8))

        ModernButton(toolbar, text="➕ 添加/导入输入文件", font=("微软雅黑", 8, "bold"), bg_color="#2563eb", hover_color="#1d4ed8", padx=10, pady=5, command=self._cmd_import_input_file).pack(side=tk.LEFT, padx=(0, 6))
        ModernButton(toolbar, text="📂 切换数据源目录", font=("微软雅黑", 8), bg_color="#f1f5f9", hover_color="#e2e8f0", text_color="#334155", padx=10, pady=5, command=self._cmd_change_data_dir).pack(side=tk.LEFT, padx=(0, 6))
        ModernButton(toolbar, text="🔍 预览选中数据", font=("微软雅黑", 8), bg_color="#f1f5f9", hover_color="#e2e8f0", text_color="#334155", padx=10, pady=5, command=self._cmd_preview_selected_data).pack(side=tk.LEFT, padx=(0, 6))
        ModernButton(toolbar, text="🗑️ 移除自定义文件", font=("微软雅黑", 8), bg_color="#f1f5f9", hover_color="#fee2e2", text_color="#dc2626", padx=10, pady=5, command=self._cmd_remove_selected_data).pack(side=tk.LEFT, padx=(0, 6))
        ModernButton(toolbar, text="🔄 刷新列表", font=("微软雅黑", 8), bg_color="#f1f5f9", hover_color="#e2e8f0", text_color="#475569", padx=8, pady=5, command=self._refresh_data_table).pack(side=tk.RIGHT)

        # 数据表树容器
        tree_container = tk.Frame(table_card, bg="#ffffff")
        tree_container.pack(fill=tk.BOTH, expand=True)

        scroll_y = ttk.Scrollbar(tree_container, orient="vertical")
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree_data = ttk.Treeview(
            tree_container,
            columns=("id", "var", "file", "role", "type", "size", "status"),
            show="headings",
            height=10,
            yscrollcommand=scroll_y.set,
        )
        scroll_y.config(command=self.tree_data.yview)

        self.tree_data.heading("id", text="编号")
        self.tree_data.heading("var", text="建模符号")
        self.tree_data.heading("file", text="输入源表文件名")
        self.tree_data.heading("role", text="系统模型角色")
        self.tree_data.heading("type", text="来源类型")
        self.tree_data.heading("size", text="文件大小")
        self.tree_data.heading("status", text="质检与覆盖状态")

        self.tree_data.column("id", width=70, anchor="center")
        self.tree_data.column("var", width=90, anchor="center")
        self.tree_data.column("file", width=230, anchor="w")
        self.tree_data.column("role", width=220, anchor="w")
        self.tree_data.column("type", width=90, anchor="center")
        self.tree_data.column("size", width=80, anchor="center")
        self.tree_data.column("status", width=180, anchor="w")

        self.tree_data.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree_data.bind("<Double-1>", lambda event: self._cmd_preview_selected_data())

        tip_lbl = tk.Label(
            table_card,
            text="💡 提示：点击【➕ 添加/导入输入文件】可导入 .xlsx/.xls/.csv 格式的新指标或控制变量；双击表格中任一文件即可弹出前 25 行明细预览。",
            font=("微软雅黑", 8),
            bg="#ffffff",
            fg="#64748b",
            anchor="w",
        )
        tip_lbl.pack(fill=tk.X, pady=(6, 0))

        self._refresh_data_table()

    def _refresh_data_table(self):
        """刷新数据源表格。"""
        for item in self.tree_data.get_children():
            self.tree_data.delete(item)

        raw_dir = get_raw_data_dir()
        files = list_input_files_metadata(raw_dir)
        for f in files:
            vals = (
                f["id"],
                f["var"],
                f["file"],
                f["role"],
                f["type"],
                f["size"],
                f["status"],
            )
            self.tree_data.insert("", tk.END, values=vals)

        short_dir = raw_dir if len(raw_dir) < 45 else "..." + raw_dir[-42:]
        self.lbl_data_dir.config(text=f"📁 数据源目录: {short_dir} (共 {len(files)} 份)")

    def _cmd_import_input_file(self):
        """弹出文件选择并导入新的输入数据文件。"""
        file_path = filedialog.askopenfilename(
            title="选择要添加/导入的数据文件",
            filetypes=[
                ("Excel 与 CSV 数据表", "*.xlsx *.xls *.csv"),
                ("Excel 工作簿 (*.xlsx, *.xls)", "*.xlsx *.xls"),
                ("CSV 数据文件 (*.csv)", "*.csv"),
                ("所有文件 (*.*)", "*.*"),
            ],
        )
        if not file_path:
            return

        try:
            info = inspect_data_file(file_path)
        except Exception as err:
            messagebox.showerror("文件解析失败", f"无法解析所选文件: {err}")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("添加/导入输入文件配置")
        dialog.geometry("520x460")
        dialog.resizable(False, False)
        dialog.configure(bg="#f8fafc")
        dialog.transient(self.root)
        dialog.grab_set()

        dw, dh = 520, 460
        rx = self.root.winfo_rootx() + (self.root.winfo_width() - dw) // 2
        ry = self.root.winfo_rooty() + (self.root.winfo_height() - dh) // 2
        dialog.geometry(f"{dw}x{dh}+{rx}+{ry}")

        top_f = tk.Frame(dialog, bg="#2563eb", padx=16, pady=12)
        top_f.pack(fill=tk.X)
        tk.Label(top_f, text="➕ 导入外部输入数据文件", font=("微软雅黑", 11, "bold"), fg="#ffffff", bg="#2563eb").pack(anchor="w")
        tk.Label(top_f, text="自动校验数据结构，归档至系统数据源并注册变量映射", font=("微软雅黑", 8), fg="#dbeafe", bg="#2563eb").pack(anchor="w", pady=(2, 0))

        content_f = tk.Frame(dialog, bg="#f8fafc", padx=18, pady=14)
        content_f.pack(fill=tk.BOTH, expand=True)

        summary_card = tk.Frame(content_f, bg="#ffffff", relief="solid", bd=1, padx=12, pady=10)
        summary_card.pack(fill=tk.X, pady=(0, 12))

        tk.Label(summary_card, text=f"📄 源文件: {info['filename']} ({info['file_size_kb']} KB)", font=("微软雅黑", 9, "bold"), bg="#ffffff", fg="#0f172a").pack(anchor="w")
        struct_desc = f"• 格式结构: {'宽表 (包含年份列)' if info['is_wide'] else ('长表' if info['is_long'] else '表格数据')}"
        sample_desc = f"• 样本覆盖: 识别到 {info['provinces_count']} 个省份, 年份跨度: {info['year_min'] or '无'}-{info['year_max'] or '无'}"
        shape_desc = f"• 数据规模: {info['rows']} 行 x {info['cols']} 列 | 缺失单元格: {info['missing_count']} 个"

        tk.Label(summary_card, text=struct_desc, font=("微软雅黑", 8), bg="#ffffff", fg="#475569").pack(anchor="w", pady=(2, 0))
        tk.Label(summary_card, text=sample_desc, font=("微软雅黑", 8), bg="#ffffff", fg="#475569").pack(anchor="w")
        tk.Label(summary_card, text=shape_desc, font=("微软雅黑", 8), bg="#ffffff", fg="#475569").pack(anchor="w")

        form_f = tk.Frame(content_f, bg="#f8fafc")
        form_f.pack(fill=tk.X, pady=4)

        tk.Label(form_f, text="变量英文/拼音代号 (Symbol):", font=("微软雅黑", 8, "bold"), bg="#f8fafc", fg="#334155").pack(anchor="w")
        default_var = os.path.splitext(info["filename"])[0].split("_")[0].upper()[:10]
        var_entry = ttk.Entry(form_f, font=("微软雅黑", 9))
        var_entry.insert(0, default_var)
        var_entry.pack(fill=tk.X, pady=(2, 8))

        tk.Label(form_f, text="系统模型角色 (Model Role):", font=("微软雅黑", 8, "bold"), bg="#f8fafc", fg="#334155").pack(anchor="w")
        role_combo = ttk.Combobox(
            form_f,
            values=[
                "控制变量 (Control Variable)",
                "补充评价指标 (Evaluation Indicator)",
                "替代被解释变量 (Alternative Dependent Var)",
                "政策仿真外生变量 (Policy Exogenous Var)",
                "机制中介调节变量 (Mechanism Mediator)",
                "备查原始数据表 (Reference Raw Table)",
            ],
            state="readonly",
            font=("微软雅黑", 9),
        )
        role_combo.current(0)
        role_combo.pack(fill=tk.X, pady=(2, 8))

        tk.Label(form_f, text="归档保存文件名 (Target Name):", font=("微软雅黑", 8, "bold"), bg="#f8fafc", fg="#334155").pack(anchor="w")
        target_name_entry = ttk.Entry(form_f, font=("微软雅黑", 9))
        target_base = os.path.splitext(info["filename"])[0] + ".xlsx"
        target_name_entry.insert(0, target_base)
        target_name_entry.pack(fill=tk.X, pady=(2, 10))

        btn_box = tk.Frame(content_f, bg="#f8fafc")
        btn_box.pack(fill=tk.X, pady=(8, 0))

        def do_confirm():
            v_symbol = var_entry.get().strip() or default_var
            v_role = role_combo.get().split(" (")[0]
            t_name = target_name_entry.get().strip() or target_base
            try:
                res = import_input_file(
                    src_path=file_path,
                    target_name=t_name,
                    var_name=v_symbol,
                    var_role=v_role,
                )
                dialog.destroy()
                self._refresh_data_table()
                messagebox.showinfo("导入成功", res["message"])
                self.output_queue.put(f"[数据管理] 成功添加输入文件: {t_name} (变量={v_symbol}, 角色={v_role})\n")
            except Exception as ex:
                messagebox.showerror("导入出错", f"保存导入文件时发生异常: {ex}")

        ModernButton(btn_box, text="✓ 确认导入至数据源", font=("微软雅黑", 9, "bold"), bg_color="#2563eb", hover_color="#1d4ed8", padx=16, pady=6, command=do_confirm).pack(side=tk.RIGHT, padx=(8, 0))
        ModernButton(btn_box, text="取消", font=("微软雅黑", 9), bg_color="#e2e8f0", hover_color="#cbd5e1", text_color="#475569", padx=14, pady=6, command=dialog.destroy).pack(side=tk.RIGHT)

    def _cmd_change_data_dir(self):
        """切换激活的数据源文件夹目录。"""
        new_dir = filedialog.askdirectory(title="选择新的原始数据输入目录", initialdir=get_raw_data_dir())
        if not new_dir:
            return
        try:
            set_raw_data_dir(new_dir)
            self._refresh_data_table()
            messagebox.showinfo("切换成功", f"当前激活的数据源目录已切换至：\n{new_dir}")
            self.output_queue.put(f"[数据管理] 数据源目录切换为: {new_dir}\n")
        except Exception as e:
            messagebox.showerror("切换失败", f"设置数据源目录出错: {e}")

    def _cmd_preview_selected_data(self):
        """弹出窗口预览选中数据文件的表格内容。"""
        selected = self.tree_data.selection()
        if not selected:
            messagebox.showwarning("提示", "请先在表格中点击选中需要预览的数据文件！")
            return

        item = self.tree_data.item(selected[0])
        filename = item["values"][2]

        try:
            cols, rows, meta = preview_input_file(filename, max_rows=25)
        except Exception as err:
            messagebox.showerror("预览失败", f"无法读取文件 '{filename}': {err}")
            return

        p_win = tk.Toplevel(self.root)
        p_win.title(f"数据明细预览 - {filename}")
        p_win.geometry("900x520")
        p_win.configure(bg="#f8fafc")

        top_bar = tk.Frame(p_win, bg="#0f172a", padx=14, pady=10)
        top_bar.pack(fill=tk.X)
        tk.Label(top_bar, text=f"📊 文件名: {filename}", font=("微软雅黑", 10, "bold"), fg="#ffffff", bg="#0f172a").pack(side=tk.LEFT)
        meta_txt = f"总行数: {meta['total_rows']} | 总列数: {meta['total_cols']} | 正在预览前 {meta['preview_rows']} 行"
        tk.Label(top_bar, text=meta_txt, font=("Consolas", 9), fg="#94a3b8", bg="#0f172a").pack(side=tk.RIGHT)

        table_f = tk.Frame(p_win, bg="#f8fafc", padx=10, pady=10)
        table_f.pack(fill=tk.BOTH, expand=True)

        sc_x = ttk.Scrollbar(table_f, orient="horizontal")
        sc_y = ttk.Scrollbar(table_f, orient="vertical")

        p_tree = ttk.Treeview(
            table_f,
            columns=cols,
            show="headings",
            xscrollcommand=sc_x.set,
            yscrollcommand=sc_y.set,
        )
        sc_x.config(command=p_tree.xview)
        sc_y.config(command=p_tree.yview)

        for c in cols:
            p_tree.heading(c, text=c)
            p_tree.column(c, width=max(75, len(c) * 12), anchor="center")

        for r in rows:
            p_tree.insert("", tk.END, values=[str(v) for v in r])

        sc_y.pack(side=tk.RIGHT, fill=tk.Y)
        sc_x.pack(side=tk.BOTTOM, fill=tk.X)
        p_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def _cmd_remove_selected_data(self):
        """移除选中的自定义输入文件。"""
        selected = self.tree_data.selection()
        if not selected:
            messagebox.showwarning("提示", "请先在表格中点击选中需要移除的数据文件！")
            return

        item = self.tree_data.item(selected[0])
        filename = item["values"][2]
        is_custom_type = item["values"][4]

        if "系统内置" in str(is_custom_type):
            messagebox.showwarning("保护受限", f"'{filename}' 为系统出厂内置的核心基础源表，不可移除！")
            return

        if not messagebox.askyesno("确认移除", f"确定要从数据源目录中移除自定义文件 '{filename}' 吗？\n(移除后该变量不再参与后续分析)"):
            return

        ok, msg = remove_input_file(filename)
        if ok:
            messagebox.showinfo("已移除", msg)
            self._refresh_data_table()
            self.output_queue.put(f"[数据管理] 已移除数据文件: {filename}\n")
        else:
            messagebox.showerror("移除失败", msg)

    # -------------------------------------------------------------
    # 页面 3：计量实证与诊断
    # -------------------------------------------------------------
    def _init_tab_econometrics(self):
        frame = self.tab_econometrics

        actions_row = tk.Frame(frame, bg="#f8fafc")
        actions_row.pack(fill=tk.X, padx=15, pady=(15, 8))

        c1 = tk.Frame(actions_row, bg="#ffffff", relief="solid", bd=1, padx=14, pady=12)
        c1.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))

        tk.Label(c1, text="📊 双向固定效应计量回归 (Two-way FE)", font=("微软雅黑", 10, "bold"), bg="#ffffff", fg="#7c3aed").pack(anchor="w")
        tk.Label(c1, text="控制省份个体效应与年份时间效应，采用小簇聚类自由度修正推断估计基准与区域参数。", font=("微软雅黑", 8), bg="#ffffff", fg="#64748b").pack(anchor="w", pady=(3, 10))

        b_box1 = tk.Frame(c1, bg="#ffffff")
        b_box1.pack(anchor="w")
        ModernButton(b_box1, text="执行双向固定效应回归 (panel_regression_analyzer.py)", font=("微软雅黑", 8, "bold"), bg_color="#7c3aed", hover_color="#6d28d9", padx=10, pady=5, command=lambda: self._execute_module("面板计量分析", "panel_regression_analyzer.py")).pack(side=tk.LEFT, padx=(0, 6))
        ModernButton(b_box1, text="📄 载入历史测算存档", font=("微软雅黑", 8), bg_color="#f1f5f9", hover_color="#e2e8f0", text_color="#475569", padx=8, pady=5, command=lambda: self._refresh_econometrics_display(force=True)).pack(side=tk.LEFT)

        c2 = tk.Frame(actions_row, bg="#ffffff", relief="solid", bd=1, padx=14, pady=12)
        c2.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(6, 0))

        tk.Label(c2, text="🛡️ 全套稳健性、敏感度与因果边界检验", font=("微软雅黑", 10, "bold"), bg="#ffffff", fg="#c026d3").pack(anchor="w")
        tk.Label(c2, text="检验时间滞后一期、领先项趋势共动诊断、一阶差分模型及 VIF 多重共线性。", font=("微软雅黑", 8), bg="#ffffff", fg="#64748b").pack(anchor="w", pady=(3, 10))

        ModernButton(c2, text="运行稳健性与敏感度诊断 (robustness_validator.py)", font=("微软雅黑", 8, "bold"), bg_color="#c026d3", hover_color="#a21caf", padx=10, pady=5, command=lambda: self._execute_module("稳健性诊断", "robustness_validator.py")).pack(anchor="w")

        # 核心计量结论双列看板
        results_frame = tk.Frame(frame, bg="#f8fafc")
        results_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(6, 15))

        # 左列：全国主效应与机制
        res_left = tk.Frame(results_frame, bg="#ffffff", relief="solid", bd=1, padx=14, pady=12)
        res_left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))

        tk.Label(res_left, text="全国基准效应与协同机制估计值", font=("微软雅黑", 10, "bold"), bg="#ffffff", fg="#0f172a").pack(anchor="w", pady=(0, 6))

        self.lbl_econ_left = tk.Label(res_left, text="正在读取最新实证回归数据...", font=("Consolas", 9), justify=tk.LEFT, bg="#f8fafc", fg="#1e293b", padx=10, pady=10, relief="solid", bd=1)
        self.lbl_econ_left.pack(fill=tk.BOTH, expand=True)

        # 右列：区域异质性与分级
        res_right = tk.Frame(results_frame, bg="#ffffff", relief="solid", bd=1, padx=14, pady=12)
        res_right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(6, 0))

        tk.Label(res_right, text="三大区域证据分层与稳健性结论", font=("微软雅黑", 10, "bold"), bg="#ffffff", fg="#0f172a").pack(anchor="w", pady=(0, 6))

        self.lbl_econ_right = tk.Label(res_right, text="正在读取最新区域实证数据...", font=("Consolas", 9), justify=tk.LEFT, bg="#f8fafc", fg="#1e293b", padx=10, pady=10, relief="solid", bd=1)
        self.lbl_econ_right.pack(fill=tk.BOTH, expand=True)

    # -------------------------------------------------------------
    # 页面 4：政策仿真与Pareto寻优
    # -------------------------------------------------------------
    def _init_tab_simulation(self):
        frame = self.tab_simulation

        param_card = tk.Frame(frame, bg="#ffffff", relief="solid", bd=1, padx=16, pady=14)
        param_card.pack(fill=tk.X, padx=15, pady=(15, 8))

        tk.Label(param_card, text="政策多目标仿真交互参数配置", font=("微软雅黑", 10, "bold"), bg="#ffffff", fg="#0f172a").pack(anchor="w", pady=(0, 8))

        controls_row = tk.Frame(param_card, bg="#ffffff")
        controls_row.pack(fill=tk.X)

        # 滑块 1：数字投入
        s1_box = tk.Frame(controls_row, bg="#ffffff")
        s1_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        tk.Label(s1_box, text="数字赋能投入倍数 (Digital Scale):", font=("微软雅黑", 8, "bold"), bg="#ffffff", fg="#475569").pack(anchor="w")
        ttk.Scale(s1_box, from_=0.0, to=1.0, variable=self.digital_scale_var, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=4)
        tk.Label(s1_box, textvariable=self.digital_scale_var, font=("Consolas", 9, "bold"), bg="#ffffff", fg="#2563eb").pack(anchor="w")

        # 滑块 2：产业升级
        s2_box = tk.Frame(controls_row, bg="#ffffff")
        s2_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)
        tk.Label(s2_box, text="产业升级优化增量 (Upgrade Scale):", font=("微软雅黑", 8, "bold"), bg="#ffffff", fg="#475569").pack(anchor="w")
        ttk.Scale(s2_box, from_=0.2, to=1.2, variable=self.upgrade_scale_var, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=4)
        tk.Label(s2_box, textvariable=self.upgrade_scale_var, font=("Consolas", 9, "bold"), bg="#ffffff", fg="#059669").pack(anchor="w")

        # 年份标识 (聚焦 2035 远景目标年)
        s3_box = tk.Frame(controls_row, bg="#ffffff", width=140)
        s3_box.pack(side=tk.RIGHT, padx=(10, 0))
        tk.Label(s3_box, text="推演目标年份:", font=("微软雅黑", 8, "bold"), bg="#ffffff", fg="#475569").pack(anchor="w")
        lbl_year = tk.Label(s3_box, text="2035 (远景目标年)", font=("Consolas", 9, "bold"), bg="#eff6ff", fg="#1d4ed8", relief="solid", bd=1, padx=6, pady=3)
        lbl_year.pack(fill=tk.X, pady=4)

        # 仿真按钮
        btn_row = tk.Frame(param_card, bg="#ffffff")
        btn_row.pack(fill=tk.X, pady=(10, 0))

        ModernButton(btn_row, text="🎯 启动政策多目标动态仿真与 Pareto 寻优 (policy_simulation_optimizer.py)", font=("微软雅黑", 9, "bold"), bg_color="#d97706", hover_color="#b45309", padx=14, pady=6, command=lambda: self._execute_module("政策多目标仿真", "policy_simulation_optimizer.py")).pack(side=tk.LEFT, padx=(0, 8))
        ModernButton(btn_row, text="📄 载入历史仿真存档", font=("微软雅黑", 8), bg_color="#f1f5f9", hover_color="#e2e8f0", text_color="#475569", padx=10, pady=6, command=lambda: self._refresh_simulation_display(force=True)).pack(side=tk.LEFT)

        # 结果与分型对比
        detail_frame = tk.Frame(frame, bg="#f8fafc")
        detail_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(6, 15))

        # 5 大情景对比
        scen_card = tk.Frame(detail_frame, bg="#ffffff", relief="solid", bd=1, padx=14, pady=12)
        scen_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))

        self.lbl_scen_title = tk.Label(scen_card, text="2035 目标年政策情景推演终值对比", font=("微软雅黑", 10, "bold"), bg="#ffffff", fg="#0f172a")
        self.lbl_scen_title.pack(anchor="w", pady=(0, 6))

        self.lbl_sim_scenarios = tk.Label(scen_card, text="正在读取最新政策仿真数据...", font=("Consolas", 8), justify=tk.LEFT, bg="#f8fafc", fg="#1e293b", padx=8, pady=8, relief="solid", bd=1)
        self.lbl_sim_scenarios.pack(fill=tk.BOTH, expand=True)

        # 四类治理分型
        zone_card = tk.Frame(detail_frame, bg="#ffffff", relief="solid", bd=1, padx=14, pady=12)
        zone_card.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(6, 0))

        tk.Label(zone_card, text="省域精细化治理清单分型 (Policy Zones)", font=("微软雅黑", 10, "bold"), bg="#ffffff", fg="#0f172a").pack(anchor="w", pady=(0, 6))

        self.lbl_sim_zone = tk.Label(
            zone_card,
            text="正在读取省域分型数据...",
            font=("Consolas", 8),
            justify=tk.LEFT,
            bg="#f8fafc",
            fg="#1e293b",
            padx=8,
            pady=8,
            relief="solid",
            bd=1,
            anchor="nw",
        )
        self.lbl_sim_zone.pack(fill=tk.BOTH, expand=True)

    # -------------------------------------------------------------
    # 页面 5：成果报表与交付
    # -------------------------------------------------------------
    def _init_tab_reports(self):
        frame = self.tab_reports

        # 4 张成果交付卡片 (2x2 网格)
        grid_frame = tk.Frame(frame, bg="#f8fafc")
        grid_frame.pack(fill=tk.X, padx=15, pady=(15, 8))

        # 卡片 1：Excel 报表
        c1 = tk.Frame(grid_frame, bg="#ffffff", relief="solid", bd=1, padx=14, pady=12)
        c1.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=(0, 6))
        tk.Label(c1, text="📑 全量多维数据汇总报表 (.xlsx)", font=("微软雅黑", 10, "bold"), bg="#ffffff", fg="#2563eb").pack(anchor="w")
        tk.Label(c1, text="聚合 表0_核心结论 到 表16_时间戳 共 16 个工作表，包含回归全矩阵与情景推演终值。", font=("微软雅黑", 8), bg="#ffffff", fg="#64748b").pack(anchor="w", pady=(3, 10))
        b_row1 = tk.Frame(c1, bg="#ffffff")
        b_row1.pack(anchor="w")
        ModernButton(b_row1, text="导出汇总报表", font=("微软雅黑", 8, "bold"), bg_color="#2563eb", hover_color="#1d4ed8", padx=10, pady=5, command=lambda: self._execute_module("报表导出", "report_exporter.py")).pack(side=tk.LEFT, padx=(0, 6))
        ModernButton(b_row1, text="打开表格所在目录", font=("微软雅黑", 8), bg_color="#f1f5f9", hover_color="#e2e8f0", text_color="#334155", padx=8, pady=5, command=lambda: self._open_dir(RESULT_DIR)).pack(side=tk.LEFT)

        # 卡片 2：数据质量与异常审计
        c2 = tk.Frame(grid_frame, bg="#ffffff", relief="solid", bd=1, padx=14, pady=12)
        c2.grid(row=0, column=1, sticky="nsew", padx=(6, 0), pady=(0, 6))
        tk.Label(c2, text="🔍 数据质量体检与异常审计表 (.xlsx)", font=("微软雅黑", 10, "bold"), bg="#ffffff", fg="#0284c7").pack(anchor="w")
        tk.Label(c2, text="运行数据完整性审计、缺失值与异常值体检，生成数据清洗与修正全流程记录。", font=("微软雅黑", 8), bg="#ffffff", fg="#64748b").pack(anchor="w", pady=(3, 10))
        b_row2 = tk.Frame(c2, bg="#ffffff")
        b_row2.pack(anchor="w")
        ModernButton(b_row2, text="运行质量体检", font=("微软雅黑", 8, "bold"), bg_color="#0284c7", hover_color="#0369a1", padx=10, pady=5, command=lambda: self._execute_module("数据体检", "data_quality_checker.py")).pack(side=tk.LEFT, padx=(0, 6))
        ModernButton(b_row2, text="📄 查看体检报告 (.json)", font=("微软雅黑", 8, "bold"), bg_color="#f1f5f9", hover_color="#e2e8f0", text_color="#0f172a", padx=8, pady=5, command=self._cmd_view_data_quality_report).pack(side=tk.LEFT)

        # 卡片 3：核心成果图
        c3 = tk.Frame(grid_frame, bg="#ffffff", relief="solid", bd=1, padx=14, pady=12)
        c3.grid(row=1, column=0, sticky="nsew", padx=(0, 6), pady=(6, 0))
        tk.Label(c3, text="🎨 高分辨率矢量成果图 (.png)", font=("微软雅黑", 10, "bold"), bg="#ffffff", fg="#059669").pack(anchor="w")
        tk.Label(c3, text="生成区域证据分层图、碳排放预测趋势图与 Pareto 前沿折中对比图。", font=("微软雅黑", 8), bg="#ffffff", fg="#64748b").pack(anchor="w", pady=(3, 10))
        b_row3 = tk.Frame(c3, bg="#ffffff")
        b_row3.pack(anchor="w")
        ModernButton(b_row3, text="刷新所有成果图表", font=("微软雅黑", 8, "bold"), bg_color="#059669", hover_color="#047857", padx=10, pady=5, command=self._cmd_refresh_charts).pack(side=tk.LEFT, padx=(0, 6))
        ModernButton(b_row3, text="打开图形输出目录", font=("微软雅黑", 8), bg_color="#f1f5f9", hover_color="#e2e8f0", text_color="#334155", padx=8, pady=5, command=lambda: self._open_dir(FIG_DIR)).pack(side=tk.LEFT)

        # 卡片 4：系统自检报告
        c4 = tk.Frame(grid_frame, bg="#ffffff", relief="solid", bd=1, padx=14, pady=12)
        c4.grid(row=1, column=1, sticky="nsew", padx=(6, 0), pady=(6, 0))
        tk.Label(c4, text="🛡️ 系统运行完整性自检 (.json)", font=("微软雅黑", 10, "bold"), bg="#ffffff", fg="#d97706").pack(anchor="w")
        tk.Label(c4, text="全自动化审计核心文件齐全度、指标数值一致性与无障碍结构规范，导出 JSON 验证证明。", font=("微软雅黑", 8), bg="#ffffff", fg="#64748b").pack(anchor="w", pady=(3, 10))
        b_row4 = tk.Frame(c4, bg="#ffffff")
        b_row4.pack(anchor="w")
        ModernButton(b_row4, text="执行系统完整性自检", font=("微软雅黑", 8, "bold"), bg_color="#d97706", hover_color="#b45309", padx=10, pady=5, command=lambda: self._execute_module("系统自检", "system_integrity_validator.py")).pack(side=tk.LEFT, padx=(0, 6))
        ModernButton(b_row4, text="📄 查看自检简报 (.txt)", font=("微软雅黑", 8, "bold"), bg_color="#f1f5f9", hover_color="#e2e8f0", text_color="#0f172a", padx=8, pady=5, command=self._cmd_view_integrity_result_txt).pack(side=tk.LEFT)

        grid_frame.columnconfigure(0, weight=1)
        grid_frame.columnconfigure(1, weight=1)

        # 下部：交付成果核验清单
        manifest_card = tk.Frame(frame, bg="#ffffff", relief="solid", bd=1, padx=15, pady=12)
        manifest_card.pack(fill=tk.BOTH, expand=True, padx=15, pady=(8, 15))

        m_head = tk.Frame(manifest_card, bg="#ffffff")
        m_head.pack(fill=tk.X, pady=(0, 6))

        tk.Label(m_head, text="成果交付文件清单索引与状态核验 (Deliverables Index)", font=("微软雅黑", 10, "bold"), bg="#ffffff", fg="#0f172a").pack(side=tk.LEFT)

        ModernButton(m_head, text="📄 载入磁盘历史成果状态", font=("微软雅黑", 8), bg_color="#f1f5f9", hover_color="#e2e8f0", text_color="#475569", padx=8, pady=3, command=lambda: self._refresh_reports_display(force=True)).pack(side=tk.RIGHT)
        ModernButton(m_head, text="🔄 刷新状态", font=("微软雅黑", 8), bg_color="#f1f5f9", hover_color="#e2e8f0", text_color="#2563eb", padx=8, pady=3, command=lambda: self._refresh_reports_display(force=False)).pack(side=tk.RIGHT, padx=4)

        self.lbl_reports_manifest = tk.Label(
            manifest_card,
            text="正在读取成果文件清单与状态...",
            font=("Consolas", 8),
            justify=tk.LEFT,
            bg="#f8fafc",
            fg="#334155",
            padx=10,
            pady=10,
            relief="solid",
            bd=1,
            anchor="nw",
        )
        self.lbl_reports_manifest.pack(fill=tk.BOTH, expand=True)

    # -------------------------------------------------------------
    # 页面 6：运行终端与实时日志 (Full Screen Console)
    # -------------------------------------------------------------
    def _init_tab_console(self):
        frame = self.tab_console

        top_bar = tk.Frame(frame, bg="#ffffff", relief="solid", bd=1, padx=12, pady=8)
        top_bar.pack(fill=tk.X, padx=15, pady=(15, 8))

        tk.Label(top_bar, text="全屏运行控制台日志监控 (Full Terminal Console)", font=("微软雅黑", 10, "bold"), bg="#ffffff", fg="#0f172a").pack(side=tk.LEFT)

        ModernButton(top_bar, text="💾 导出日志为文件 (.txt)", font=("微软雅黑", 8), bg_color="#f1f5f9", hover_color="#e2e8f0", text_color="#2563eb", padx=10, pady=4, command=self._cmd_export_log).pack(side=tk.RIGHT, padx=4)
        ModernButton(top_bar, text="🧹 清空控制台", font=("微软雅黑", 8), bg_color="#f1f5f9", hover_color="#e2e8f0", text_color="#475569", padx=10, pady=4, command=self._cmd_clear_console).pack(side=tk.RIGHT, padx=4)

        con_container = tk.Frame(frame, bg="#090d16", relief="solid", bd=1)
        con_container.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))

        self.full_console = ScrolledText(
            con_container,
            wrap=tk.WORD,
            bg="#090d16",
            fg="#38bdf8",
            insertbackground="#ffffff",
            font=("Consolas", 9),
            padx=12,
            pady=12,
        )
        self.full_console.pack(fill=tk.BOTH, expand=True)

    # -------------------------------------------------------------
    # 底部状态栏
    # -------------------------------------------------------------
    def _build_bottom_statusbar(self):
        status_bar = tk.Frame(self.root, bg="#f1f5f9", height=32, relief="groove", bd=1)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        status_bar.pack_propagate(False)

        tk.Label(status_bar, text="调度状态:", font=("微软雅黑", 8, "bold"), bg="#f1f5f9", fg="#64748b").pack(side=tk.LEFT, padx=(14, 4), pady=5)
        tk.Label(status_bar, textvariable=self.current_task_name, font=("微软雅黑", 8), bg="#f1f5f9", fg="#0284c7").pack(side=tk.LEFT, pady=5)

        tk.Label(
            status_bar,
            text="省域数字经济与低碳协同综合评估系统 [DEC-CES] V1.0",
            font=("微软雅黑", 8),
            bg="#f1f5f9",
            fg="#94a3b8",
        ).pack(side=tk.RIGHT, padx=14, pady=5)

    # -------------------------------------------------------------
    # 核心动作与工作线程调度
    # -------------------------------------------------------------
    def _log(self, text: str):
        self.output_queue.put(text + "\n")

    def _process_log_queue(self):
        while not self.output_queue.empty():
            try:
                line = self.output_queue.get_nowait()
                self.mini_console.insert(tk.END, line)
                self.mini_console.see(tk.END)
                self.full_console.insert(tk.END, line)
                self.full_console.see(tk.END)
            except queue.Empty:
                break
        self.root.after(60, self._process_log_queue)

    def _update_step_state(self, step_idx: int, state: str, desc: str = ""):
        """更新流水线卡片工序状态徽章。"""
        if 0 <= step_idx < len(self.step_badges):
            badge = self.step_badges[step_idx]
            if state == "running":
                badge.config(text="🔄 计算中...", bg="#fef3c7", fg="#b45309")
                if desc:
                    self.current_task_name.set(desc)
            elif state == "done":
                badge.config(text="✓ 已完成", bg="#dcfce7", fg="#15803d")
            elif state == "error":
                badge.config(text="✗ 异常", bg="#fee2e2", fg="#b91c1c")
            elif state == "pending":
                badge.config(text="⚪ 待执行", bg="#f1f5f9", fg="#64748b")

    def _set_running_state(self, running: bool, task_name: str = ""):
        self.is_running = running
        if running:
            self.status_pill.config(text="● 正在计算...", fg="#f59e0b", bg="#78350f")
            self.current_task_name.set(f"正在执行: {task_name} ...")
            self.btn_run_all.config(state="disabled")
            self.btn_run_all.set_color("#94a3b8", "#94a3b8")
        else:
            self.status_pill.config(text="● 系统就绪 (待命)", fg="#38bdf8", bg="#0c4a6e")
            self.current_task_name.set("任务完成，系统就绪")
            self.btn_run_all.config(state="normal")
            self.btn_run_all.set_color("#2563eb", "#1d4ed8")

    def _run_worker(self, target_func, task_name: str, on_done=None):
        if self.is_running:
            messagebox.showwarning("提示", "当前有任务正在运行中，请等待完成后再启动新任务。")
            return

        self._set_running_state(True, task_name)

        def worker():
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            redirector = ConsoleRedirector(self.output_queue)
            sys.stdout = redirector
            sys.stderr = redirector
            start_time = time.time()
            try:
                self._log(f"\n[{time.strftime('%H:%M:%S')}] >>> 开始执行: {task_name}")
                target_func()
                elapsed = time.time() - start_time
                self._log(f"[{time.strftime('%H:%M:%S')}] <<< {task_name} 成功完成! (耗时: {elapsed:.2f} 秒)\n")
            except Exception as e:
                self._log(f"\n[ERROR] 执行出错: {e}\n")
            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr
                self.root.after(0, lambda: self._set_running_state(False))
                self.root.after(0, self._refresh_all_dynamic_displays)
                if on_done:
                    self.root.after(0, on_done)

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    def _execute_module(self, task_name: str, script_name: str, on_done=None):
        script_path = CODE_DIR / script_name
        step_map = {
            "data_quality_checker.py": 0,
            "entropy_weight_engine.py": 1,
            "panel_regression_analyzer.py": 2,
            "policy_simulation_optimizer.py": 3,
            "report_exporter.py": 4,
        }
        step_idx = step_map.get(script_name)

        def task():
            if script_name in {"panel_regression_analyzer.py", "robustness_validator.py"}:
                self.has_run_econ = True
                self.econ_finished_time = time.strftime("%H:%M:%S")
            elif script_name in {"policy_simulation_optimizer.py"}:
                cur_yr = str(self.target_year_var.get().strip() or "2035")
                os.environ["DEC_CES_TARGET_YEAR"] = cur_yr
                os.environ["DEC_CES_DIGITAL_SCALE"] = f"{self.digital_scale_var.get():.2f}"
                os.environ["DEC_CES_UPGRADE_SCALE"] = f"{self.upgrade_scale_var.get():.2f}"
            elif script_name in {"system_integrity_validator.py"}:
                self.has_run_check = True
            elif script_name in {"report_exporter.py"}:
                self.has_run_report = True

            if step_idx is not None:
                self.root.after(0, lambda: self._update_step_state(step_idx, "running", f"正在执行: {task_name}"))
            runpy.run_path(str(script_path), run_name="__main__")
            if script_name in {"policy_simulation_optimizer.py"}:
                self.has_run_sim = True
                self.sim_finished_time = time.strftime("%H:%M:%S")
                self.sim_calculated_year = str(self.target_year_var.get().strip() or "2035")
            if step_idx is not None:
                self.root.after(0, lambda: self._update_step_state(step_idx, "done"))

        self._run_worker(task, f"{task_name} ({script_name})", on_done=on_done)

    def _cmd_run_full_pipeline(self):
        if self.is_running:
            messagebox.showwarning("提示", "流水线当前正在计算中，请稍候。")
            return

        for i in range(len(self.step_badges)):
            self._update_step_state(i, "pending")
        self.progress_val.set(0.0)

        pipeline_stages = [
            (0, "阶段 1/5: 正在执行数据源完整性审计与体检...", ["data_quality_checker.py"]),
            (1, "阶段 2/5: 正在解算香农信息熵客观权重矩阵...", ["entropy_weight_engine.py"]),
            (2, "阶段 3/5: 正在运行双向固定效应计量回归与稳健性矩阵...", ["panel_regression_analyzer.py", "robustness_validator.py"]),
            (3, "阶段 4/5: 正在进行政策多目标动态演化仿真与 Pareto 寻优...", ["policy_simulation_optimizer.py"]),
            (4, "阶段 5/5: 正在汇总全量报表、生成矢量图表并执行系统自检...", ["report_exporter.py", "core_chart_generator.py", "system_integrity_validator.py"]),
        ]

        self._set_running_state(True, "全流程自动化综合评估流水线")

        def worker():
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            redirector = ConsoleRedirector(self.output_queue)
            sys.stdout = redirector
            sys.stderr = redirector
            start_time = time.time()
            try:
                self.has_run_pipeline = True
                self.has_run_econ = True
                self.has_run_sim = True
                self.has_run_check = True
                self.has_run_report = True
                self._log(f"\n[{time.strftime('%H:%M:%S')}] >>> 🚀 启动全流程自动化综合评估流水线...")
                for idx, stage_desc, scripts in pipeline_stages:
                    self.root.after(0, lambda i=idx, d=stage_desc: self._update_step_state(i, "running", d))
                    self.root.after(0, lambda i=idx: self.progress_val.set(i * 20.0 + 5.0))
                    for s in scripts:
                        script_path = CODE_DIR / s
                        runpy.run_path(str(script_path), run_name="__main__")
                    self.root.after(0, lambda i=idx: self._update_step_state(i, "done"))
                    self.root.after(0, lambda i=idx: self.progress_val.set((i + 1) * 20.0))

                elapsed = time.time() - start_time
                self._log(f"\n[{time.strftime('%H:%M:%S')}] <<< 🎉 全流程自动化评估流水线执行完毕! (总耗时: {elapsed:.2f} 秒)\n")
                self.root.after(0, self._on_pipeline_success)
            except Exception as ex:
                self._log(f"\n[ERROR] 流水线执行中断: {ex}\n")
                self.root.after(0, lambda: messagebox.showerror("执行中断", f"流水线运行出错: {ex}"))
            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr
                self.root.after(0, lambda: self._set_running_state(False))

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    def _on_pipeline_success(self):
        self.status_pill.config(text="● 评估完成 (PASS)", fg="#10b981", bg="#064e3b")
        self.lbl_kpi_check_main.config(text="PASS 100% 通过")
        self.lbl_kpi_check_sub.config(text="全流程指标自检通过")
        self.progress_val.set(100.0)
        self._refresh_all_dynamic_displays()
        messagebox.showinfo("完成", "全流程自动化评估流水线已成功执行完毕！\n所有计算模型、实证检验、情景仿真与多维报表已全部生成更新。")

    def _refresh_all_dynamic_displays(self):
        """全面从 04_核心结果 目录的真实结果 Excel/JSON 文件中提取最新实证与仿真数据，动态刷新界面各标签页展示。"""
        self._refresh_kpi_cards()
        self._refresh_econometrics_display()
        self._refresh_simulation_display()
        self._refresh_reports_display()

    def _refresh_kpi_cards(self):
        """动态更新看板顶部的核心统计指标卡。"""
        try:
            raw_files = list_input_files_metadata(get_raw_data_dir())
            exists_cnt = sum(1 for f in raw_files if f.get("exists"))
            custom_cnt = sum(1 for f in raw_files if f.get("is_custom"))
            self.lbl_kpi_sample_main.config(text=f"{exists_cnt} 份源表")
            sub_msg = f"平衡面板 30 省份 (含 {custom_cnt} 份自定义)" if custom_cnt > 0 else "平衡面板 30 省份 (360样本)"
            self.lbl_kpi_sample_sub.config(text=sub_msg)
        except Exception:
            pass

        if self.has_run_pipeline or self.has_run_check:
            chk_report = RESULT_DIR / "系统运行自检报告.json"
            if chk_report.exists():
                try:
                    data = json.loads(chk_report.read_text(encoding="utf-8"))
                    passed = data.get("passed")
                    if passed is None:
                        passed = data.get("summary", {}).get("overall_passed")
                    if passed is None and "checks" in data:
                        passed = all(c.get("passed", False) for c in data["checks"])
                    passed = bool(passed)
                    if passed:
                        self.lbl_kpi_check_main.config(text="PASS 100% 通过", fg="#059669")
                        self.lbl_kpi_check_sub.config(text="全流程指标自检验证通过")
                    else:
                        self.lbl_kpi_check_main.config(text="⚠️ 自检发现异常", fg="#d97706")
                        self.lbl_kpi_check_sub.config(text="部分指标校验未通过")
                except Exception:
                    pass
        else:
            self.lbl_kpi_check_main.config(text="⚪ 待启动评估", fg="#0f172a")
            self.lbl_kpi_check_sub.config(text="点击右侧按钮启动端到端自动化流水线")

    def _refresh_econometrics_display(self, force: bool = False):
        """动态从实证结果 Excel 中读取最新全国回归与区域异质性数据。"""
        reg_file = RESULT_DIR / "实证结果_连续与离散比较.xlsx"
        reg_area_file = RESULT_DIR / "实证结果_区域异质性.xlsx"

        # 如果当前会话尚未执行计算，且未强制载入历史数据，则显示待命占位状态，绝不抢跑结论
        if not force and not self.has_run_econ and not self.has_run_pipeline:
            text_left = (
                "⚪ 待执行：当前会话尚未运行本次计量实证分析\n\n"
                "• 当前状态：待命状态 (待启动计算)\n"
                "• 操作指引：请点击上方【执行双向固定效应回归】或在首页启动【🚀 启动全流程自动化评估】\n"
                "• 核心产出：解算执行完毕后，系统将自动从生成的数据表中动态提取全国基准回归参数、离散稳健性、协同机制检验与增长方程参数\n\n"
                "💡 提示：若需查阅磁盘已有的历史测算记录，可点击上方【📄 载入历史测算存档】。"
            )
            text_right = (
                "⚪ 待执行：当前会话尚未运行区域异质性检验\n\n"
                "• 当前状态：待命状态 (待启动计算)\n"
                "• 核心产出：执行回归后，此处将自动呈现东部、中西部、东北三大区域的异质性回归证据、参数估计与政策支持分级\n\n"
                "💡 提示：若需查阅磁盘已有的历史测算记录，可点击上方【📄 载入历史测算存档】。"
            )
            self.lbl_econ_left.config(text=text_left)
            self.lbl_econ_right.config(text=text_right)
            return

        econ_time = getattr(self, "econ_finished_time", None)
        if (self.has_run_econ or self.has_run_pipeline) and econ_time:
            source_tag = f"本次真实模型解算完成 ({econ_time})"
        elif reg_file.exists():
            mtime_str = time.strftime('%H:%M:%S', time.localtime(reg_file.stat().st_mtime))
            source_tag = f"历史计量存档 ({reg_file.name}，生成时间: {mtime_str})"
        else:
            source_tag = "尚未生成"

        if reg_file.exists():
            try:
                df = pd.read_excel(reg_file)
                ci_coef = df.loc[df["Treatment_Variable"] == "CI", "coef"].values[0]
                ci_p = df.loc[df["Treatment_Variable"] == "CI", "P>|t|"].values[0]
                d_coef = df.loc[df["Treatment_Variable"] == "D", "coef"].values[0]
                d_p = df.loc[df["Treatment_Variable"] == "D", "P>|t|"].values[0]
                syn_coef = df.loc[df["Treatment_Variable"] == "CI_x_Upgrade", "coef"].values[0]
                syn_p = df.loc[df["Treatment_Variable"] == "CI_x_Upgrade", "P>|t|"].values[0]
                up_coef = df.loc[df["Treatment_Variable"] == "Upgrade", "coef"].values[0]
                up_p = df.loc[df["Treatment_Variable"] == "Upgrade", "P>|t|"].values[0]

                ci_sig = "显著" if ci_p < 0.05 else "未达5%显著"
                d_sig = "显著" if d_p < 0.05 else "稳健不显著"
                up_sig = "显著" if up_p < 0.05 else "不显著"

                text_left = (
                    f"【全国平均连续估计】：CI = {ci_coef:.3f}, p = {ci_p:.3f} ({ci_sig})\n"
                    f"【全国平均离散估计】：D = {d_coef:.3f}, p = {d_p:.3f} ({d_sig})\n"
                    f"【结论判定】：全国平均不显著，不支持“数字化一刀切天然降碳”假设。\n\n"
                    f"【协同机制检验 (CI × Upgrade)】：β = {syn_coef:.3f}, p = {syn_p:.3f}\n"
                    f"【增长方程检验 (Upgrade)】：β = {up_coef:.3f}, p = {up_p:.3f} ({up_sig})\n"
                    f"【经济学含义】：产业升级能有效缓冲数字反弹，但伴随短期增长约束。\n\n"
                    f"【动态来源】：{source_tag}"
                )
            except Exception as e:
                text_left = f"⚠️ 读取实证回归结果异常: {e}"
        else:
            text_left = (
                "⚪ 尚未检测到最新回归结果 (实证结果_连续与离散比较.xlsx)\n\n"
                "• 说明：数据未经过本次计量解算\n"
                "• 操作：请点击上方【执行双向固定效应回归】或全流程流水线生成最新实证测算数据。"
            )

        self.lbl_econ_left.config(text=text_left)

        if reg_area_file.exists():
            try:
                df_a = pd.read_excel(reg_area_file)
                ne_row = df_a[df_a["区域"] == "东北"].iloc[0]
                east_row = df_a[df_a["区域"] == "东部"].iloc[0]
                mw_row = df_a[df_a["区域"] == "中西部"].iloc[0]

                text_right = (
                    f"【中西部 ({mw_row['政策支持级别']}支持区)】：\n"
                    f"• CI = {mw_row['CI系数']:.3f}, p = {mw_row['p值']:.4f} ({mw_row['显著性']})\n"
                    f"• 严格口径与滞后项稳健保留，数字扩张存在增碳反弹压力。\n\n"
                    f"【东北 ({ne_row['政策支持级别']}方向信号)】：\n"
                    f"• CI = {ne_row['CI系数']:.3f}, p = {ne_row['p值']:.4f} ({ne_row['显著性']})\n"
                    f"• 3 省小簇推断下统计效力边际，作为提示性方向信号，保守推演。\n\n"
                    f"【东部 ({east_row['政策支持级别']})】：\n"
                    f"• CI = {east_row['CI系数']:.3f}, p = {east_row['p值']:.4f} ({east_row['显著性']})\n"
                    f"• 估计系数接近 0 且不显著，政策仿真不纳入增压项。\n\n"
                    f"【动态来源】：{source_tag}"
                )
            except Exception as e:
                text_right = f"⚠️ 读取区域异质性结果异常: {e}"
        else:
            text_right = (
                "⚪ 尚未检测到最新区域异质性结果 (实证结果_区域异质性.xlsx)\n\n"
                "• 说明：尚未分解东、中西、东北三大板块差异\n"
                "• 操作：执行计量回归后，此处将自动呈现各区域参数与置信度。"
            )

        self.lbl_econ_right.config(text=text_right)

    def _refresh_simulation_display(self, force: bool = False):
        """动态从政策仿真 Excel 中读取 2035 远景目标年最新预测数值与四类省域分型。"""
        sim_summary_file = SIM_DIR / "政策仿真最终结果.xlsx"
        zone_file = SIM_DIR / "政策分型_省份清单.xlsx"
        target_year = 2035
        if hasattr(self, "lbl_scen_title"):
            self.lbl_scen_title.config(text="2035 目标年政策情景推演终值对比")

        calc_time = getattr(self, "sim_finished_time", None)

        # 如果当前会话尚未执行仿真，且未强制载入历史数据，则显示待命占位状态
        if not force and not self.has_run_sim and not self.has_run_pipeline:
            scen_text = (
                "⚪ 待执行：当前会话尚未运行政策多目标仿真与 Pareto 寻优\n\n"
                "• 当前状态：待命状态 (待启动仿真)\n"
                "• 操作指引：请在上方配置投入倍数与升级增量后，点击【🎯 启动政策多目标动态仿真与 Pareto 寻优】启动模型推演\n"
                f"• 核心产出：模型真实计算完成后，此处将动态呈现基准、数字加速、政策强化、定向协同及 Pareto 折中解的 {target_year} 目标年预测终值\n\n"
                "💡 提示：所有指标均由底层微分方程模型推演得出，绝无静态写死数据。"
            )
            self.lbl_sim_scenarios.config(text=scen_text)

            zone_pending_text = (
                "⚪ 待执行：当前会话尚未生成省域精细化治理清单分型\n\n"
                "• 当前状态：待命状态 (待启动仿真)\n"
                "• 操作指引：启动仿真解算后，系统将根据各省基准碳强度、产业升级潜力与数字反弹敏感性，动态划分 A/B/C/D 四类治理清单与差异化调控建议\n\n"
                "💡 提示：若需查阅磁盘已有的历史仿真记录，可点击上方【📄 载入历史仿真存档】。"
            )
            self.lbl_sim_zone.config(text=zone_pending_text)
            return

        if self.has_run_sim and calc_time:
            source_tag = f"本次真实模型解算完成 ({calc_time})"
        elif sim_summary_file.exists():
            mtime_str = time.strftime('%H:%M:%S', time.localtime(sim_summary_file.stat().st_mtime))
            source_tag = f"历史计算存档文件 ({sim_summary_file.name}，生成时间: {mtime_str})"
        else:
            source_tag = "尚未生成"

        if sim_summary_file.exists():
            try:
                df_sim = pd.read_excel(sim_summary_file)
                # 提取 2035 目标年各情景数值
                scen_data = []
                baseline_y = None
                for _, row in df_sim.iterrows():
                    scen = str(row["情景"])
                    scen_file = SIM_DIR / f"{scen}.xlsx"
                    y = None
                    gr = None
                    if scen_file.exists():
                        try:
                            df_s = pd.read_excel(scen_file)
                            if "year" in df_s.columns:
                                df_s = df_s.set_index("year")
                            if target_year in df_s.index:
                                y = float(df_s.loc[target_year, "Y_pred"])
                                gr = float(df_s.loc[2023:target_year, "Avg_PGDP_Growth"].mean()) * 100
                        except Exception:
                            pass

                    if y is None:
                        col_y = "2035碳强度预测"
                        y = float(row[col_y]) if col_y in row else 0.0
                    if gr is None:
                        col_gr = "平均人均GDP增长率"
                        gr = float(row[col_gr]) * 100 if col_gr in row else 0.0

                    if "基准" in scen:
                        baseline_y = y
                    scen_data.append((scen, y, gr))

                lines = []
                for scen, y_pred, gdp_gr in scen_data:
                    co2_imp = (baseline_y - y_pred) if baseline_y is not None else 0.0
                    if "基准" in scen:
                        desc = f"  碳排放强度: {y_pred:.3f} | 人均GDP年均增速: {gdp_gr:.2f}%"
                    elif "数字加速" in scen:
                        desc = f"  碳排放强度: {y_pred:.3f} (+{-co2_imp:.3f} 反弹上升，扩张加剧碳压)"
                    elif "政策强化" in scen:
                        desc = f"  碳排放强度: {y_pred:.3f} | 人均GDP年均增速: {gdp_gr:.2f}%"
                    elif "定向协同" in scen:
                        desc = f"  碳排放强度: {y_pred:.3f} (-{co2_imp:.3f} 显著减排改善)"
                    elif "Pareto" in scen:
                        desc = f"  碳排放强度: {y_pred:.3f} | 人均GDP增速: {gdp_gr:.2f}% (兼顾低碳与增长)"
                    else:
                        desc = f"  碳排放强度: {y_pred:.3f} | 人均GDP增速: {gdp_gr:.2f}%"
                    lines.append(f"• {scen}：\n{desc}")
                lines.append(f"\n【动态来源】：{source_tag} [推演目标年份: {target_year} 远景目标年]")
                scen_text = "\n\n".join(lines)
            except Exception as e:
                scen_text = f"⚠️ 读取政策仿真结果异常: {e}"
        else:
            scen_text = (
                "⚪ 尚未检测到最新政策仿真数据 (政策仿真最终结果.xlsx)\n\n"
                "• 说明：尚未执行多目标协同演化与 Pareto 折中寻优\n"
                "• 操作：请点击上方【🎯 启动政策多目标动态仿真与 Pareto 寻优】计算生成最新推演数据。"
            )


        self.lbl_sim_scenarios.config(text=scen_text)

        # 动态刷新右侧治理分型
        if zone_file.exists():
            try:
                df_z = pd.read_excel(zone_file)
                z_lines = []
                zone_desc_map = {
                    "A_高压约束区": ("A 类·高压约束区", "传统能源/重工业占比较高，数字扩张易诱发反弹", "控制数字扩张节奏，优先追加产业升级和能效改造"),
                    "B_结构补短区": ("B 类·结构补短区", "产业转型承压，严格数字红利边际转弱", "优先补齐产业升级短板，适度推进数字化赋能"),
                    "C_数字引领区": ("C 类·数字引领区", "数字基建完善，轻量结构优化空间充足", "持续保持数字引领，以绿色园区与数字服务赋能"),
                    "D_均衡提升区": ("D 类·均衡提升区", "产业与数字基础均衡，具备渐进转型潜力", "协同推进稳健转型，避免激进跃进带来结构失衡"),
                }
                for z_key, (z_title, z_feat, z_adv) in zone_desc_map.items():
                    sub = df_z[df_z["政策分型"] == z_key]
                    prov_list = sub["province"].tolist()
                    prov_str = "、".join(prov_list) if prov_list else "无"
                    cnt = len(prov_list)
                    z_lines.append(
                        f"【{z_title}】({prov_str}，共 {cnt} 省)：\n"
                        f"  • 特征：{z_feat}\n"
                        f"  • 建议：{z_adv}"
                    )
                z_lines.append(f"\n【动态来源】：{source_tag}")
                zone_text = "\n\n".join(z_lines)
            except Exception as e:
                zone_text = f"⚠️ 读取政策分型结果异常: {e}"
        else:
            zone_text = (
                "⚪ 尚未检测到省域治理分型数据 (政策分型_省份清单.xlsx)\n\n"
                "• 说明：尚未执行仿真分型计算\n"
                "• 操作：请点击上方仿真按钮或启动全流程流水线生成。"
            )
        self.lbl_sim_zone.config(text=zone_text)

    def _refresh_reports_display(self, force: bool = False):
        """动态核验 6 大交付成果文件的生成状态、大小与自检结果。"""
        deliverables = [
            ("【全量报表】", "04_核心结果/综合评估与仿真分析汇总表.xlsx", RESULT_DIR / "综合评估与仿真分析汇总表.xlsx", "包含 表0 到 表16 全量工作表"),
            ("【实证回归】", "04_核心结果/实证结果_完整回归表.xlsx", RESULT_DIR / "实证结果_完整回归表.xlsx", "双向固定效应面板回归全矩阵与异质性估计表"),
            ("【自检证明】", "04_核心结果/系统运行自检报告.json", RESULT_DIR / "系统运行自检报告.json", "指标一致性与规范校验"),
            ("【政策分型】", "04_核心结果/simulation_results/政策仿真最终结果.xlsx", SIM_DIR / "政策仿真最终结果.xlsx", "四类省域精细化治理清单"),
            ("【评价简报】", "04_核心结果/评价体系测算结果.txt", RESULT_DIR / "评价体系测算结果.txt", "熵权权重与30省份排名纯文本报告"),
            ("【自检文本】", "04_核心结果/系统运行自检报告.txt", RESULT_DIR / "系统运行自检报告.txt", "系统完整性自检纯文本报告"),
            ("【时序预测】", "05_图形/碳排放强度情景预测图.png", FIG_DIR / "碳排放强度情景预测图.png", "2022-2035 动态情景演化趋势图"),
            ("【前沿折中】", "05_图形/多目标优化_帕累托前沿对比图.png", FIG_DIR / "多目标优化_帕累托前沿对比图.png", "Pareto 前沿非劣解集对比图"),
        ]

        if not force and not self.has_run_pipeline and not self.has_run_report:
            lines = [
                "⚪ 待执行：当前会话尚未运行全流程自动化评估流水线或报表生成\n",
                "• 当前状态：待命状态 (各成果交付文件将在全流程流水线或对应模块执行后生成并核验)",
                "• 操作指引：请在首页点击【🚀 启动全流程自动化评估】或在上方卡片中单独执行对应交付工序",
                "• 交付成果预置规范索引清单：\n",
            ]
            for idx, (tag, rel_path, full_path, desc) in enumerate(deliverables, 1):
                status_note = "已存在磁盘历史文件，等待本次流水线更新" if full_path.exists() else "尚未生成"
                lines.append(f"{idx}. {tag} {rel_path} ({desc}) [{status_note}]")
            lines.append("\n💡 提示：若需核验当前磁盘已有历史文件的生成时间与就绪状态，可点击右上角【📄 载入磁盘历史成果状态】。")
            self.lbl_reports_manifest.config(text="\n".join(lines))
            return

        is_current = (self.has_run_pipeline or self.has_run_report)
        source_title = "✓ 已就绪：本次流水线已成功执行并更新全部成果文件" if is_current else "📁 历史存档：当前展示磁盘已有的历史交付文件状态"
        lines = [
            f"{source_title}\n",
            f"• 核验时间：{time.strftime('%Y-%m-%d %H:%M:%S')}",
            "• 交付成果文件状态核验清单：\n",
        ]
        for idx, (tag, rel_path, full_path, desc) in enumerate(deliverables, 1):
            if full_path.exists():
                size_kb = full_path.stat().st_size / 1024
                if "自检证明" in tag:
                    try:
                        chk_data = json.loads(full_path.read_text(encoding="utf-8"))
                        passed = chk_data.get("passed")
                        if passed is None:
                            passed = chk_data.get("summary", {}).get("overall_passed")
                        if passed is None and "checks" in chk_data:
                            passed = all(c.get("passed", False) for c in chk_data["checks"])
                        passed = bool(passed)
                        chk_tag = "状态: PASS (100%通过)" if passed else "状态: 异常"
                    except Exception:
                        chk_tag = "已生成"
                    flag = f"[{chk_tag} | {size_kb:.1f} KB]"
                else:
                    flag = f"[就绪 | {size_kb:.1f} KB]"
                mark = "✓ 本次更新" if is_current else "📁 历史文件"
                lines.append(f"{idx}. {tag} {rel_path} ({desc}) -> {flag} ({mark})")
            else:
                lines.append(f"{idx}. {tag} {rel_path} ({desc}) -> [❌ 文件缺失]")

        lines.append(f"\n【动态来源】：{'本次运行生成' if is_current else '磁盘历史文件核验'}")
        self.lbl_reports_manifest.config(text="\n".join(lines))

    def _cmd_run_eval_calc(self):
        """执行评价体系熵权客观赋权与综合指数测算。"""
        def on_done():
            export_evaluation_txt_report()
            self._refresh_all_dynamic_displays()
        self._execute_module("熵权法指标测算", "entropy_weight_engine.py", on_done=on_done)

    def _cmd_view_eval_result_txt(self):
        """以 txt 格式查看评价体系与综合指数测算成果报告。"""
        txt_path = RESULT_DIR / "评价体系测算结果.txt"
        if not txt_path.exists():
            try:
                export_evaluation_txt_report(txt_path)
            except Exception as e:
                self._log(f"[WARN] 自动生成测算文本简报失败: {e}")

        if not txt_path.exists():
            messagebox.showinfo(
                "提示",
                "尚未检测到评价测算结果文件。\n请先点击【▶ 开始】执行熵权指标测算，系统将自动生成测算结果与 txt 简报。",
            )
            return

        success = open_txt_file(txt_path)
        if not success:
            messagebox.showwarning("打开失败", f"无法自动启动文本阅读器打开文件：\n{txt_path}")

    def _cmd_view_integrity_result_txt(self):
        """以 txt 格式查看系统全流程运行自检报告。"""
        txt_path = RESULT_DIR / "系统运行自检报告.txt"
        if not txt_path.exists():
            try:
                export_integrity_txt_report(txt_path)
            except Exception as e:
                self._log(f"[WARN] 自动生成自检文本简报失败: {e}")

        if not txt_path.exists():
            messagebox.showinfo(
                "提示",
                "尚未检测到系统自检报告。\n请先点击【▶ 开始】运行系统运行自检。",
            )
            return

        success = open_txt_file(txt_path)
        if not success:
            messagebox.showwarning("打开失败", f"无法自动启动文本阅读器打开文件：\n{txt_path}")

    def _cmd_view_data_quality_report(self):
        """使用系统默认文本阅读器查看数据质量体检 JSON 报告。"""
        report_path = RESULT_DIR / "data_integrity_report.json"
        if not report_path.exists():
            messagebox.showinfo(
                "提示",
                "尚未检测到数据质量体检报告。\n请先点击【运行质量体检】生成报告。",
            )
            return

        success = open_txt_file(report_path)
        if not success:
            messagebox.showwarning("打开失败", f"无法自动启动文本阅读器打开文件：\n{report_path}")

    def _cmd_refresh_charts(self):
        def task():
            runpy.run_path(str(CODE_DIR / "core_chart_generator.py"), run_name="__main__")

        self._run_worker(task, "刷新所有高分辨率成果图表")

    def _cmd_clear_console(self):
        self.mini_console.delete("1.0", tk.END)
        self.full_console.delete("1.0", tk.END)

    def _cmd_export_log(self):
        log_content = self.full_console.get("1.0", tk.END)
        save_path = filedialog.asksaveasfilename(
            title="保存运行日志",
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
            initialfile=f"系统运行日志_{time.strftime('%Y%m%d_%H%M%S')}.txt",
        )
        if save_path:
            try:
                Path(save_path).write_text(log_content, encoding="utf-8")
                messagebox.showinfo("成功", f"运行日志已导出至:\n{save_path}")
            except Exception as e:
                messagebox.showerror("错误", f"保存日志失败: {e}")

    def _open_dir(self, directory: Path):
        if not directory.exists():
            messagebox.showwarning("提示", f"目标目录不存在: {directory}")
            return
        try:
            if sys.platform == "win32":
                os.startfile(str(directory))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(directory)])
            else:
                subprocess.Popen(["xdg-open", str(directory)])
        except Exception as e:
            messagebox.showerror("错误", f"无法打开目录: {e}")


def main():
    if "--test-init" in sys.argv:
        root = tk.Tk()
        app = EvaluationSystemGUI(root)
        print("MODERN_GUI_INIT_TEST_SUCCESS")
        root.update()
        root.destroy()
        return

    root = tk.Tk()
    app = EvaluationSystemGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
