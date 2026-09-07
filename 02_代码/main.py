# -*- coding: utf-8 -*-
"""
================================================================================
软件全称：省域数字经济与低碳协同综合评估系统
软件简称：数字低碳协同系统 (DEC-CES)
版 本 号：V1.0
模块名称：main (主程序统一控制与调度入口)
功能描述：
1. 统一调度中心：提供命令行批处理 (CLI) 与桌面现代化图形界面 (GUI) 双模启动机制。
2. 自动化执行流水线：顺序驱动数据审计、熵权赋权、计量回归、稳健性检验、政策仿真与报表导出 8 大核心模块。
3. 提供软件元数据、版本参数解析及无界面流水线批处理选项。
================================================================================
"""

import argparse
from pathlib import Path
import runpy
import sys


sys.dont_write_bytecode = True

APP_FULL_NAME = "省域数字经济与低碳协同综合评估系统"
APP_SHORT_NAME = "数字低碳协同系统 (DEC-CES)"
APP_VERSION = "V1.0"

MODULES = [
    ("指标赋权与综合指数测算", "entropy_weight_engine.py"),
    ("面板计量回归与条件关系分析", "panel_regression_analyzer.py"),
    ("稳健性诊断与敏感度检验", "robustness_validator.py"),
    ("政策多目标仿真与Pareto寻优", "policy_simulation_optimizer.py"),
    ("综合评估指标与数据报表导出", "report_exporter.py"),
    ("核心评估图表与情景推绘制图", "core_chart_generator.py"),
    ("数据完整性审计与质量体检", "data_quality_checker.py"),
    ("系统运行自检与一致性验证", "system_integrity_validator.py"),
]


def print_system_info() -> None:
    """输出系统全称、版本及模块清单。"""
    print("=" * 70)
    print(f"软件全称：{APP_FULL_NAME}")
    print(f"软件简称：{APP_SHORT_NAME}")
    print(f"版 本 号：{APP_VERSION}")
    print("=" * 70)
    print("系统已集成模块：")
    for i, (desc, script) in enumerate(MODULES, 1):
        print(f"  {i:02d}. {desc} [{script}]")
    print("=" * 70)


def run_pipeline() -> None:
    """按依赖拓扑顺序执行全流程自动化数据分析流水线。"""
    root = Path(__file__).resolve().parent
    print("=" * 70)
    print(f"{APP_FULL_NAME} {APP_VERSION} - 自动化分析流水线开始执行")
    print("=" * 70)

    for desc, script_name in MODULES:
        script_path = root / script_name
        print(f"\n>> [{desc}] 运行模块: {script_name} ...")
        runpy.run_path(str(script_path), run_name="__main__")

    print("\n" + "=" * 70)
    print(f"{APP_FULL_NAME} {APP_VERSION} - 全流程执行完毕，所有结果与报表已更新。")
    print("=" * 70)


def launch_gui() -> None:
    """启动现代化桌面图形交互界面 (GUI)。"""
    from gui_app import main as gui_main
    gui_main()


def print_inputs_table() -> None:
    """输出当前数据源目录中的全部输入文件元数据表格。"""
    from model_utils import get_raw_data_dir, list_input_files_metadata
    raw_dir = get_raw_data_dir()
    files = list_input_files_metadata(raw_dir)
    print("=" * 90)
    print(f"当前数据源目录：{raw_dir} (共 {len(files)} 份输入源表)")
    print("=" * 90)
    print(f"{'编号':<8} {'符号':<10} {'文件名':<32} {'系统角色':<24} {'状态'}")
    print("-" * 90)
    for item in files:
        print(f"{item['id']:<8} {item['var']:<10} {item['file']:<32} {item['role']:<24} {item['status']}")
    print("=" * 90)


def handle_add_input(file_path: str, var_name: str | None, var_role: str) -> None:
    """处理命令行导入/添加输入文件逻辑。"""
    from model_utils import import_input_file
    try:
        res = import_input_file(file_path, var_name=var_name, var_role=var_role)
        print("=" * 70)
        print("✓ 数据文件添加成功！")
        print(f"• 目标文件：{res['filename']}")
        print(f"• 变量符号：{res['var']}")
        print(f"• 模型角色：{res['role']}")
        print(f"• 样本覆盖：{res['info']['provinces_count']} 个省份, {res['info']['rows']} 行 x {res['info']['cols']} 列")
        print(f"• 年份跨度：{res['info']['year_min']} - {res['info']['year_max']}")
        print(f"• 归档路径：{res['target_path']}")
        print("=" * 70)
    except Exception as e:
        print(f"✗ 导入输入文件失败: {e}")
        sys.exit(1)


def main() -> None:
    """统一命令行参数解析与入口调度。"""
    parser = argparse.ArgumentParser(description=f"{APP_FULL_NAME} {APP_VERSION}")
    parser.add_argument("--cli", action="store_true", help="以命令行批处理模式运行流水线")
    parser.add_argument("--gui", action="store_true", help="启动图形桌面交互界面 (默认)")
    parser.add_argument("--add-input", type=str, metavar="FILE", help="导入/添加外部输入数据文件 (.xlsx/.xls/.csv) 到系统数据源")
    parser.add_argument("--var-name", type=str, metavar="SYMBOL", help="指定导入变量的英文/拼音符号 (如 INNOV, RD, PATENT)")
    parser.add_argument("--var-role", type=str, default="控制变量", help="指定导入变量的模型角色 (默认: 控制变量)")
    parser.add_argument("--input-dir", type=str, metavar="DIR", help="指定或切换自定义原始数据输入目录")
    parser.add_argument("--list-inputs", action="store_true", help="列出当前系统数据源中的所有输入文件及元数据清单")
    parser.add_argument("--version", "-v", action="store_true", help="查看软件版本信息")
    parser.add_argument("--info", action="store_true", help="查看系统软件详细信息与架构清单")
    args, unknown = parser.parse_known_args()

    if args.input_dir:
        from model_utils import set_raw_data_dir
        set_raw_data_dir(args.input_dir)
        print(f"[配置] 原始数据目录已切换为: {args.input_dir}")

    if args.add_input:
        handle_add_input(args.add_input, args.var_name, args.var_role)
    elif args.list_inputs:
        print_inputs_table()
    elif args.version:
        print(f"{APP_FULL_NAME} {APP_VERSION} [{APP_SHORT_NAME}]")
    elif args.info:
        print_system_info()
    elif args.cli:
        run_pipeline()
    else:
        launch_gui()


if __name__ == "__main__":
    main()
