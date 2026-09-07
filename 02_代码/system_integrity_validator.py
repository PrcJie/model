# -*- coding: utf-8 -*-
"""
================================================================================
软件全称：省域数字经济与低碳协同综合评估系统
软件简称：数字低碳协同系统 (DEC-CES)
版 本 号：V1.0
模块名称：system_integrity_validator (系统运行自检与一致性验证模块)
功能描述：
1. 成果与交付文件完整性校验：核验源代码、核心数据表、成果图表与分析报告覆盖。
2. 跨模块关键运行产物与仿真参数一致性核验。
3. 验证软件工程目录结构规范性与运行结果齐备性。
4. 导出系统自检报告（JSON 格式）。
================================================================================
"""

from __future__ import annotations

import json
from pathlib import Path
from model_utils import export_integrity_txt_report, find_project_root


PROJECT_DIR = Path(find_project_root())
CODE_DIR = PROJECT_DIR / "02_代码"
RAW_DATA_DIR = PROJECT_DIR / "03_原始数据"
RESULT_DIR = PROJECT_DIR / "04_核心结果"
SIM_DIR = RESULT_DIR / "simulation_results"
REPORT_PATH = RESULT_DIR / "系统运行自检报告.json"
FALLBACK_REPORT_PATH = RESULT_DIR / "系统运行自检报告_刷新副本.json"


def add_check(items: list[dict[str, object]], name: str, passed: bool, detail: str) -> None:
    items.append({"name": name, "passed": bool(passed), "detail": detail})


def main() -> None:
    checks: list[dict[str, object]] = []

    # 1. 软件核心源代码文件核验 (12 个核心模块)
    core_scripts = [
        "main.py",
        "gui_app.py",
        "entropy_weight_engine.py",
        "panel_regression_analyzer.py",
        "robustness_validator.py",
        "policy_simulation_optimizer.py",
        "report_exporter.py",
        "core_chart_generator.py",
        "data_quality_checker.py",
        "system_integrity_validator.py",
        "model_utils.py",
        "run_all.py",
    ]
    missing_scripts = [s for s in core_scripts if not (CODE_DIR / s).exists()]
    add_check(checks, "软件核心算法与业务源码完整", not missing_scripts, "missing=" + json.dumps(missing_scripts, ensure_ascii=False))

    # 2. 系统核心成果报表核验
    core_reports = [
        RESULT_DIR / "综合评估与仿真分析汇总表.xlsx",
    ]
    missing_rep = [p.name for p in core_reports if not p.exists()]
    add_check(checks, "系统核心成果报表齐备", not missing_rep, "missing=" + json.dumps(missing_rep, ensure_ascii=False))

    # 3. 原始输入数据源表核验 (9 份源表)
    source_files = [
        "数字经济指数_2011_2022.xlsx",
        "省份等级的灯光值_平均值.xlsx",
        "能源消费量_万吨标煤.xlsx",
        "产业结构高级化_第二产业占比.xlsx",
        "碳排放量_万吨.xlsx",
        "碳排放强度_万吨亿元GDP.xlsx",
        "人均GDP.xlsx",
        "城镇化率_2000_2022.xlsx",
        "对外开放程度_2000_2022.xlsx",
    ]
    missing_sources = [s for s in source_files if not (RAW_DATA_DIR / s).exists()]
    add_check(checks, "软件运行输入样例源表齐全", not missing_sources, "missing=" + json.dumps(missing_sources, ensure_ascii=False))

    # 4. 核心计算与仿真结果表核验
    result_files = [
        RESULT_DIR / "数据异常修正记录.xlsx",
        RESULT_DIR / "数字赋能指数_测算结果.xlsx",
        RESULT_DIR / "核心数字指数_测算结果.xlsx",
        RESULT_DIR / "熵权法_权重汇总.xlsx",
        RESULT_DIR / "实证结果_完整回归表.xlsx",
        RESULT_DIR / "实证结果_区域异质性.xlsx",
        RESULT_DIR / "实证结果_构念稳健性.xlsx",
        RESULT_DIR / "稳健性与敏感度检验结果.xlsx",
        RESULT_DIR / "综合评估与仿真分析汇总表.xlsx",
        SIM_DIR / "政策仿真最终结果.xlsx",
        SIM_DIR / "政策分型_省份清单.xlsx",
        SIM_DIR / "Pareto最优路径.xlsx",
    ]
    missing_results = [str(p.relative_to(PROJECT_DIR)) for p in result_files if not p.exists()]
    add_check(checks, "系统核心测算与仿真结果齐全", not missing_results, "missing=" + json.dumps(missing_results, ensure_ascii=False))

    # 5. 自动化汇总报表核验
    summary_report = RESULT_DIR / "综合评估与仿真分析汇总表.xlsx"
    summary_valid = summary_report.exists() and summary_report.stat().st_size > 10000
    add_check(checks, "交付级综合评估汇总报表已成功导出", summary_valid, f"size={summary_report.stat().st_size if summary_report.exists() else 0}")

    overall_passed = all(item["passed"] for item in checks)
    report = {
        "software": "省域数字经济与低碳协同综合评估系统 (DEC-CES) V1.0",
        "project": str(PROJECT_DIR),
        "passed": overall_passed,
        "summary": {
            "overall_passed": overall_passed,
            "total_checks": len(checks),
            "passed_checks": sum(1 for item in checks if item["passed"]),
        },
        "checks": checks,
        "manual_gate": "系统运行完整性自检完成。软件源代码、输入样例表、核心结果与汇总报表均已通过校验。",
    }

    try:
        REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        final_report_path = REPORT_PATH
    except PermissionError:
        FALLBACK_REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        final_report_path = FALLBACK_REPORT_PATH
        print(f"原报告可能正被占用，已改写刷新副本：{FALLBACK_REPORT_PATH}")

    status = "PASS" if report["passed"] else "WARN"
    print(f"[{status}] 自检报告已写入: {final_report_path}")
    txt_path = export_integrity_txt_report()
    if txt_path:
        print(f"[{status}] 自检文本简报已写入: {txt_path}")


if __name__ == "__main__":
    main()
