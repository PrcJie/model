# 省域数字经济与低碳协同综合评估系统（DEC-CES）

![DEC-CES Logo](DEC-CES_logo.png)

DEC-CES V1.0 是面向省域面板数据的桌面分析系统。它将数据质量检查、香农熵权指数测算、双向固定效应回归、稳健性检验、政策情景仿真、Pareto 寻优和报表导出连接为一条分析流水线，同时提供 Tkinter 图形界面和命令行入口。

项目默认使用 **2011—2022 年、30 个省份**的九份 Excel 源表；数据完整时形成 360 条省份—年份观测，并以 2022 年为基期生成延伸至 2035 年的政策情景结果。

## 快速开始

需要 Python **3.10 或更高版本**；图形界面还需要可用的 Tkinter 和桌面显示环境。先在项目根目录创建并激活虚拟环境。

Windows PowerShell：

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS/Linux：

```bash
python3 -m venv .venv
source .venv/bin/activate
```

激活后安装依赖、核对输入，再运行全流程：

```bash
python -m pip install -r "02_代码/requirements.txt"
python "02_代码/main.py" --list-inputs
python "02_代码/main.py" --cli
```

运行 `--list-inputs` 时应先确认九份内置源表均显示为已找到；缺少源表时，请按下文的文件名放入 `03_原始数据/`。

如需使用图形界面，运行：

```bash
python "02_代码/main.py"
```

默认启动 GUI；`--gui` 也可显式指定。首次使用可以先在“数据工程”页检查输入，再从首页运行全流程。`--cli` 会重新计算并写入结果文件；如需保留历史结果，请先备份 `04_核心结果/` 和 `05_图形/`。

## 输入数据

内置分析模块按以下**固定文件名**读取 `03_原始数据/` 中的 Excel 工作簿：

| 文件名 | 用途 |
| --- | --- |
| `数字经济指数_2011_2022.xlsx` | 数字技术能力指标 |
| `省份等级的灯光值_平均值.xlsx` | 夜间灯光活跃度代理指标 |
| `能源消费量_万吨标煤.xlsx` | 低碳用能效率指标 |
| `产业结构高级化_第二产业占比.xlsx` | 产业结构指标 |
| `碳排放强度_万吨亿元GDP.xlsx` | 碳排放强度因变量 |
| `人均GDP.xlsx` | 经济发展水平控制变量 |
| `城镇化率_2000_2022.xlsx` | 城镇化控制变量 |
| `对外开放程度_2000_2022.xlsx` | 对外开放控制变量 |
| `碳排放量_万吨.xlsx` | 碳排放总量指标 |

源表采用**宽表**：首列为省份名称，年份为列名（可为数字或数字字符串），程序读取 2011—2022 年各列并转换为面板数据。数据质量模块会检查年份、缺失值和样本完整性；部分孤立尖峰的修正会记录在 `04_核心结果/数据异常修正记录.xlsx`。研究范围和模型口径由代码定义，替换源表时应保持文件名、字段结构和统计口径一致。

GUI 和 `--add-input` 支持登记额外的 `.xlsx`、`.xls`、`.csv` 文件；导入后会归档到数据目录，并在 `custom_inputs_manifest.json` 中记录元数据。**新增文件不会自动进入上述固定模型**。对于旧版 `.xls`，当前依赖清单没有单独列出其读取引擎，建议先转换为 `.xlsx`。

## 常用命令

| 命令 | 作用 |
| --- | --- |
| `python "02_代码/main.py"` | 启动 GUI |
| `python "02_代码/main.py" --cli` | 运行完整分析流水线 |
| `python "02_代码/main.py" --list-inputs` | 列出当前数据目录中的内置和自定义输入 |
| `python "02_代码/main.py" --info` | 查看系统及模块清单 |
| `python "02_代码/main.py" --version` | 查看版本 |
| `python "02_代码/run_all.py"` | 通过快捷脚本运行完整流水线 |

指定本次进程使用的输入目录，并查看其源表：

```bash
python "02_代码/main.py" --input-dir "你的数据目录" --list-inputs
```

导入一份扩展数据并指定变量符号、角色：

```bash
python "02_代码/main.py" --add-input "你的数据文件.xlsx" --var-name INNOV --var-role 控制变量
```

`--input-dir` 的切换只作用于当前程序进程；没有指定时，使用项目内的 `03_原始数据/`。

## 分析流程与输出

`--cli` 按 `02_代码/main.py` 中的顺序运行八个模块：

1. `entropy_weight_engine.py`：熵权测算，生成基准协同指数 `CI` 和核心数字指数 `CI_core`。
2. `panel_regression_analyzer.py`：双向固定效应回归及区域异质性分析。
3. `robustness_validator.py`：稳健性与敏感度检验。
4. `policy_simulation_optimizer.py`：2022—2035 年政策情景模拟及 Pareto 寻优。
5. `report_exporter.py`：汇总测算、实证与仿真结果。
6. `core_chart_generator.py`：绘制区域、碳排放强度预测与 Pareto 前沿图。
7. `data_quality_checker.py`：检查输入、结果和跨文件一致性。
8. `system_integrity_validator.py`：核验交付文件完整性并生成自检报告。

主要交付文件如下；`simulation_results/` 位于 `04_核心结果/` 下。

| 路径 | 内容 |
| --- | --- |
| `04_核心结果/数字赋能指数_测算结果.xlsx` | 省份—年份基准协同指数 |
| `04_核心结果/核心数字指数_测算结果.xlsx` | 核心数字指数 |
| `04_核心结果/熵权法_权重汇总.xlsx` | 指标权重 |
| `04_核心结果/实证结果_完整回归表.xlsx` | 面板回归结果 |
| `04_核心结果/simulation_results/政策仿真最终结果.xlsx` | 情景终值与政策比较 |
| `04_核心结果/综合评估与仿真分析汇总表.xlsx` | 全量汇总报表；完整运行时包含表 0 至表 16 |
| `04_核心结果/data_integrity_report.json` | 数据和结果质量检查 |
| `04_核心结果/系统运行自检报告.json` | 文件完整性自检；查看 `passed` 字段 |
| `05_图形/` | 区域证据、情景预测和 Pareto 前沿 PNG 图 |

## 项目结构

```text
.
├── README.md
├── DEC-CES_logo.png
├── 02_代码/              # 入口、GUI、分析模块和依赖清单
├── 03_原始数据/          # 九份内置源表及自定义输入
├── 04_核心结果/          # 指数、实证、仿真、报表与自检结果
│   └── simulation_results/
└── 05_图形/              # 生成的图表
```

`.gitignore` 排除了 `03_原始数据/`、`04_核心结果/` 和 `05_图形/`。因此，从仅包含 Git 跟踪文件的副本启动时，需要自行准备源表；运行产生的数据和图表也要单独保存或交接。

## 排查运行问题

- **提示缺少 Python 模块**：确认使用已安装 `02_代码/requirements.txt` 的同一个 Python 环境启动程序。
- **提示源表不存在或读取失败**：运行 `--list-inputs` 核对文件名和位置，再检查首列省份、年份列及 Excel 格式。
- **GUI 无法打开**：确认当前环境支持 Tkinter 和桌面显示；服务器或无图形环境可使用 `--cli`。
- **需要确认本次运行结果**：查看 `04_核心结果/data_integrity_report.json` 与 `04_核心结果/系统运行自检报告.json`，并核对汇总报表的生成时间。
