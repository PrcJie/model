# -*- coding: utf-8 -*-
"""
================================================================================
软件全称：省域数字经济与低碳协同综合评估系统
软件简称：数字低碳协同系统 (DEC-CES)
版 本 号：V1.0
模块名称：core_chart_generator (核心评估图表与情景推绘制图引擎)
功能描述：
1. 原生矢量质感渲染：在轻量级或无界面服务器环境下，基于 PIL/Pillow 高精度像素渲染算法输出核心决策大图：
   - 区域证据分层图.png (置信区间误差棒与显著性分层)
   - 碳排放强度情景预测图.png (2022-2035 动态时序情景对比)
   - 多目标优化_帕累托前沿对比图.png (Pareto 非劣解集与拐点标注)
2. 内置跨平台中文字体自适应探测与优雅降级机制。
3. 提供面向对象的工程级制图引擎类 CoreChartGenerator，支持批量渲染与刷新副本容错。
================================================================================
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd
from PIL import Image, ImageDraw, ImageFont

from model_utils import FIGURE_DIR, REGION_ORDER, SIM_DIR, choose_knee_point, ensure_dir, student_t_critical


W, H = 1800, 1050
BG = "white"
AXIS = "#334155"
GRID = "#dbe5f1"
TEXT = "#0f172a"
MUTED = "#475569"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """探测系统可用中文字体文件，若缺失则降级为默认字体。"""
    candidates = [
        r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                pass
    return ImageFont.load_default()


F_TITLE = font(46, True)
F_SUB = font(25)
F_LABEL = font(31)
F_SMALL = font(24)
F_TINY = font(21)
F_LEGEND = font(19)
F_LEGEND_SMALL = font(16)
F_LEGEND_TITLE = font(22, True)


def canvas() -> Tuple[Image.Image, ImageDraw.ImageDraw]:
    """创建标准分辨率绘图画布。"""
    img = Image.new("RGB", (W, H), BG)
    return img, ImageDraw.Draw(img)


def save(img: Image.Image, *paths: str) -> None:
    """安全保存图像文件，若文件被占用则自动生成时间戳刷新副本。"""
    for path in paths:
        ensure_dir(os.path.dirname(path))
        try:
            img.save(path)
        except PermissionError:
            target = str(Path(path).with_name(f"{Path(path).stem}_刷新副本{Path(path).suffix}"))
            img.save(target)
            print(f"原图可能正被占用，已改写刷新副本：{target}")


def map_value(value: float, src_min: float, src_max: float, dst_min: int, dst_max: int) -> float:
    """线性值域映射工具。"""
    if src_max == src_min:
        return (dst_min + dst_max) / 2
    return dst_min + (value - src_min) / (src_max - src_min) * (dst_max - dst_min)


def draw_pareto_legend(draw: ImageDraw.ImageDraw) -> None:
    """绘制 Pareto 前沿图专用图例卡片。"""
    x0, y0, x1, y1 = 1580, 205, 1775, 545
    draw.rounded_rectangle((x0, y0, x1, y1), radius=10, fill="#ffffff", outline="#cbd5e1", width=2)
    draw.text((x0 + 14, y0 + 12), "图例", fill=TEXT, font=F_LEGEND_TITLE)

    rows = [
        ("circle", "#99f6e4", "#0f766e", "定向协同候选", "分区施策组合"),
        ("circle", "#fde68a", "#f59e0b", "统一政策候选", "统一加码组合"),
        ("frontier", "#7c3aed", "#7c3aed", "Pareto 前沿", "不被同时超越"),
        ("knee", "#f59e0b", "#7c3aed", "折中最优点", "推荐平衡解"),
    ]

    y = y0 + 58
    for kind, fill, outline, label, note in rows:
        mx = x0 + 28
        if kind == "frontier":
            draw.line((mx - 14, y + 7, mx + 16, y + 7), fill=fill, width=5)
            draw.ellipse((mx - 6, y - 1, mx + 10, y + 15), fill=fill)
        elif kind == "knee":
            draw.regular_polygon((mx, y + 7, 14), n_sides=5, rotation=-18, fill=fill, outline=outline, width=3)
        else:
            draw.ellipse((mx - 10, y - 3, mx + 10, y + 17), fill=fill, outline=outline, width=2)

        draw.text((x0 + 52, y - 2), label, fill=TEXT, font=F_LEGEND)
        draw.text((x0 + 52, y + 21), note, fill=MUTED, font=F_LEGEND_SMALL)
        y += 62


def draw_region_plot() -> None:
    """渲染区域证据分层与置信区间误差棒图。"""
    reg_file = os.path.join(os.path.dirname(FIGURE_DIR), "04_核心结果", "实证结果_区域异质性.xlsx")
    if not os.path.exists(reg_file):
        return
    df = pd.read_excel(reg_file).set_index("区域").reindex(REGION_ORDER).reset_index()
    img, draw = canvas()
    draw.text((80, 50), "各区域数字经济赋能效应（CI 系数及 95% 置信区间）", fill=TEXT, font=F_TITLE)
    draw.text((80, 115), "中西部显著为正，东部、东北未达显著水平；政策赋权需实施分区分类治理", fill=MUTED, font=F_SUB)

    left, right, top, bottom = 220, 1700, 220, 900
    y_min, y_max = -5.0, 15.0

    for i in range(9):
        y_val = y_min + i * (y_max - y_min) / 8
        y_pos = int(map_value(y_val, y_min, y_max, bottom, top))
        draw.line((left, y_pos, right, y_pos), fill="#0f172a" if abs(y_val) < 1e-6 else GRID, width=3 if abs(y_val) < 1e-6 else 1)
        draw.text((left - 80, y_pos - 12), f"{y_val:.1f}", fill=MUTED, font=F_TINY)

    draw.line((left, top, left, bottom), fill=AXIS, width=3)
    draw.line((left, bottom, right, bottom), fill=AXIS, width=3)

    col_w = (right - left) / len(df)
    colors = ["#f59e0b", "#94a3b8", "#c2410c"]
    for i, row in df.iterrows():
        cx = int(left + (i + 0.5) * col_w)
        coef = float(row["CI系数"])
        se = float(row["标准误"])
        crit = student_t_critical(float(row.get("推断自由度", 29)))
        low, high = coef - crit * se, coef + crit * se

        y_c = int(map_value(coef, y_min, y_max, bottom, top))
        y_l = int(map_value(low, y_min, y_max, bottom, top))
        y_h = int(map_value(high, y_min, y_max, bottom, top))

        draw.line((cx, y_l, cx, y_h), fill=colors[i % len(colors)], width=5)
        draw.line((cx - 24, y_l, cx + 24, y_l), fill=colors[i % len(colors)], width=4)
        draw.line((cx - 24, y_h, cx + 24, y_h), fill=colors[i % len(colors)], width=4)
        draw.ellipse((cx - 14, y_c - 14, cx + 14, y_c + 14), fill=colors[i % len(colors)], outline="#ffffff", width=2)

        reg_name = str(row["区域"])
        p_val = float(row["p值"])
        draw.text((cx - 40, bottom + 25), reg_name, fill=TEXT, font=F_LABEL)
        draw.text((cx - 70, bottom + 70), f"系数: {coef:.3f}", fill=MUTED, font=F_TINY)
        draw.text((cx - 70, bottom + 100), f"p值: {p_val:.4f}", fill=MUTED, font=F_TINY)

    save(img, os.path.join(FIGURE_DIR, "区域证据分层图.png"))


def draw_scenario_plot() -> None:
    """渲染多情景碳排放强度动态推演走势图。"""
    scenarios = ["基准情景", "数字加速情景", "统一政策情景", "定向协同情景", "Pareto最优路径"]
    colors = {
        "基准情景": "#64748b",
        "数字加速情景": "#f97316",
        "统一政策情景": "#f59e0b",
        "定向协同情景": "#0f766e",
        "Pareto最优路径": "#8b5cf6",
    }
    dfs = {}
    for name in scenarios:
        p = os.path.join(SIM_DIR, f"{name}.xlsx")
        if os.path.exists(p):
            dfs[name] = pd.read_excel(p)

    if not dfs:
        return

    img, draw = canvas()
    draw.text((80, 50), "2022-2035 年不同政策组合下碳排放强度演进轨迹", fill=TEXT, font=F_TITLE)
    draw.text((80, 115), "基准与数字加速情景存在碳增压风险；定向协同与 Pareto 最优路径减碳成效显著", fill=MUTED, font=F_SUB)

    left, right, top, bottom = 180, 1450, 220, 920
    all_y = pd.concat([d["Y_pred"] for d in dfs.values()])
    y_min, y_max = float(all_y.min()) * 0.98, float(all_y.max()) * 1.02
    x_min, x_max = 2022, 2035

    for yr in range(2022, 2036, 2):
        x = int(map_value(yr, x_min, x_max, left, right))
        draw.line((x, top, x, bottom), fill=GRID, width=1)
        draw.text((x - 24, bottom + 16), str(yr), fill=MUTED, font=F_TINY)

    for i in range(6):
        yv = y_min + i * (y_max - y_min) / 5
        y = int(map_value(yv, y_min, y_max, bottom, top))
        draw.line((left, y, right, y), fill=GRID, width=1)
        draw.text((left - 80, y - 12), f"{yv:.3f}", fill=MUTED, font=F_TINY)

    draw.line((left, top, left, bottom), fill=AXIS, width=3)
    draw.line((left, bottom, right, bottom), fill=AXIS, width=3)

    for name, df in dfs.items():
        pts = [
            (
                int(map_value(int(r["year"]), x_min, x_max, left, right)),
                int(map_value(float(r["Y_pred"]), y_min, y_max, bottom, top)),
            )
            for _, r in df.iterrows()
        ]
        draw.line(pts, fill=colors.get(name, "#334155"), width=5)
        for x, y in pts:
            draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill=colors.get(name, "#334155"))

    lx0, ly0 = 1500, 250
    draw.rounded_rectangle((lx0, ly0, lx0 + 260, ly0 + 280), radius=10, fill="#ffffff", outline="#cbd5e1", width=2)
    draw.text((lx0 + 20, ly0 + 15), "情景方案", fill=TEXT, font=F_LEGEND_TITLE)
    for i, name in enumerate(scenarios):
        if name in dfs:
            cy = ly0 + 65 + i * 42
            draw.line((lx0 + 20, cy, lx0 + 60, cy), fill=colors[name], width=5)
            draw.ellipse((lx0 + 35, cy - 5, lx0 + 45, cy + 5), fill=colors[name])
            draw.text((lx0 + 72, cy - 12), name, fill=TEXT, font=F_LEGEND)

    save(img, os.path.join(FIGURE_DIR, "碳排放强度情景预测图.png"))


def draw_pareto_plot() -> None:
    """渲染多目标优化 Pareto 前沿折线与折中解标注图。"""
    p_file = os.path.join(SIM_DIR, "多目标优化_前沿对比数据.xlsx")
    if not os.path.exists(p_file):
        return
    df = pd.read_excel(p_file)
    frontier = df[df["Pareto_Flag"] == True].sort_values("Y_2035")
    optimal = choose_knee_point(df, "Y_2035", "Avg_PGDP_Growth")

    img, draw = canvas()
    draw.text((80, 50), "政策多目标优化：减碳成效与经济增速 Pareto 前沿权衡", fill=TEXT, font=F_TITLE)
    draw.text((80, 115), "非劣解集揭示减碳与增长的客观替代率；五角星标注欧氏距离最优折中决策点", fill=MUTED, font=F_SUB)

    left, right, top, bottom = 180, 1530, 220, 920
    x_min, x_max = float(df["Y_2035"].min()) * 0.995, float(df["Y_2035"].max()) * 1.005
    y_min, y_max = float(df["Avg_PGDP_Growth"].min()) * 100.0 * 0.98, float(df["Avg_PGDP_Growth"].max()) * 100.0 * 1.02

    for i in range(7):
        xv = x_min + i * (x_max - x_min) / 6
        x = int(map_value(xv, x_min, x_max, left, right))
        draw.line((x, top, x, bottom), fill=GRID, width=1)
        draw.text((x - 36, bottom + 18), f"{xv:.2f}", fill=MUTED, font=F_TINY)
    for i in range(6):
        yv = y_min + i * (y_max - y_min) / 5
        y = int(map_value(yv, y_min, y_max, bottom, top))
        draw.line((left, y, right, y), fill=GRID, width=2)
        draw.text((45, y - 15), f"{yv:.2f}", fill=MUTED, font=F_TINY)
    draw.line((left, bottom, right, bottom), fill=AXIS, width=3)
    draw.line((left, top, left, bottom), fill=AXIS, width=3)

    palette = {"定向协同": "#99f6e4", "统一政策": "#fde68a"}
    outline = {"定向协同": "#0f766e", "统一政策": "#f59e0b"}
    for _, row in df.iterrows():
        x = int(map_value(float(row["Y_2035"]), x_min, x_max, left, right))
        y = int(map_value(float(row["Avg_PGDP_Growth"]) * 100.0, y_min, y_max, bottom, top))
        strategy = str(row["策略类型"])
        draw.ellipse((x - 12, y - 12, x + 12, y + 12), fill=palette.get(strategy, "#e2e8f0"), outline=outline.get(strategy, AXIS), width=3)

    pts = [
        (
            int(map_value(float(row["Y_2035"]), x_min, x_max, left, right)),
            int(map_value(float(row["Avg_PGDP_Growth"]) * 100.0, y_min, y_max, bottom, top)),
        )
        for _, row in frontier.iterrows()
    ]
    if len(pts) > 1:
        draw.line(pts, fill="#7c3aed", width=6)
    for x, y in pts:
        draw.ellipse((x - 13, y - 13, x + 13, y + 13), fill="#7c3aed")

    ox = int(map_value(float(optimal["Y_2035"]), x_min, x_max, left, right))
    oy = int(map_value(float(optimal["Avg_PGDP_Growth"]) * 100.0, y_min, y_max, bottom, top))
    draw.regular_polygon((ox, oy, 28), n_sides=5, rotation=-18, fill="#f59e0b", outline="#7c3aed", width=4)
    note = f"折中最优：{optimal['策略类型']} | 碳强度={float(optimal['Y_2035']):.3f} | 增长={float(optimal['Avg_PGDP_Growth']) * 100.0:.2f}%"
    draw.rounded_rectangle((620, 495, 1280, 590), radius=12, fill="#ffffff", outline="#cbd5e1", width=3)
    draw.text((640, 524), note, fill=TEXT, font=F_TINY)
    draw_pareto_legend(draw)
    draw.text((620, 940), "2035 年碳排放强度（越低越优）", fill=TEXT, font=F_LABEL)
    draw.text((20, 460), "平均人均 GDP 增长率（%）", fill=TEXT, font=F_SMALL)
    save(img, os.path.join(FIGURE_DIR, "多目标优化_帕累托前沿对比图.png"))


class CoreChartGenerator:
    """核心评估图表与情景推绘制图引擎类。"""

    def __init__(self, figure_dir: str = FIGURE_DIR, sim_dir: str = SIM_DIR):
        self.figure_dir = figure_dir
        self.sim_dir = sim_dir

    def render_all_charts(self) -> None:
        """执行三张核心成果图表的批量渲染输出。"""
        ensure_dir(self.figure_dir)
        ensure_dir(self.sim_dir)
        draw_region_plot()
        draw_scenario_plot()
        draw_pareto_plot()


def main() -> None:
    """模块独立执行入口。"""
    generator = CoreChartGenerator()
    generator.render_all_charts()
    print("Pillow 核心图形已刷新。")


if __name__ == "__main__":
    main()
