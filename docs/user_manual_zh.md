# VASP SCF-to-cRPA Workflow 用户手册（中文版）

**软件版本：** 1.4.1（候选版本）\
**文档状态：** 待审阅草稿\
**编写日期：** 2026年9月11日\
**适用对象：** 在 Linux 工作站或高性能计算集群上开展 VASP 计算的科研人员\
**软著登记名称、著作权人及开发完成日期：** 待申请人确认

本手册说明当前软件的安装、配置和操作方法，可作为软件著作权登记用户手册的编写基础。正式提交前，应确认软件名称和版本，并补充经确认的实际运行截图及计算结果。本文中的命令、文件名和参数名保留程序中的英文写法。

[English manual / 英文手册](user_manual.md)

## 目录

1. 软件概述
2. 运行环境与安装
3. 计算目录与配置
4. 首次计算操作示例
5. 命令说明
6. 能带、态密度绘图与能带排序
7. Wannier 与 cRPA 计算
8. 批量计算
9. 输入、输出与状态查询
10. 常见问题与恢复操作
11. 物理结果检查与验证范围
12. 软著材料完善说明

## 1. 软件概述

### 1.1 用途

VASP SCF-to-cRPA Workflow 用于组织和管理基于 VASP 的电子结构计算流程，包括可选的结构弛豫、自洽场计算、态密度计算、能带计算、Wannier 构建，以及约束随机相位近似（cRPA）计算。

软件负责生成输入文件和作业脚本、安排阶段之间的数据传递、提交具有依赖关系的 Slurm 作业、查询基于输出文件的计算状态，以及进行轨道投影分析、Wannier 能量窗口选择和能带／态密度绘图。

电子结构计算由用户配置的 VASP 执行。VASPKIT 用于生成部分网格、能带路径、赝势组合及投影数据。使用者需要单独准备这些外部程序及其运行环境。

### 1.2 功能模块

| 功能 | 说明 |
| --- | --- |
| 计算初始化 | 创建独立的材料计算目录和配置文件 |
| 环境检查 | 检查当前终端中可用的工具、Python 环境及部分输入条件 |
| 基础计算准备 | 生成结构弛豫、SCF、DOS 和能带阶段的输入及作业脚本 |
| 执行与提交 | 支持直接顺序执行及 Slurm 依赖作业提交 |
| 状态查询 | 根据阶段登记信息和 OUTCAR 文件报告阶段状态 |
| 投影分析与绘图 | 绘制元素或轨道投影能带与态密度，并支持 Wannier 能带叠加 |
| Wannier 准备 | 根据轨道选择和已有计算数据生成 Wannier 输入及窗口诊断 |
| cRPA 准备 | 根据完成的 Wannier 计算生成 cRPA 输入并检查目标态编号 |
| 批量处理 | 为多个结构创建独立计算目录并逐个准备、运行或提交 |

### 1.3 计算流程

```mermaid
flowchart LR
    A[输入结构 POSCAR] --> B[00_relax 可选结构弛豫]
    A --> C[01_scf 自洽场计算]
    B --> C
    C --> D[02_dos 态密度计算]
    C --> E[03_band 能带计算]
    C --> F[04_wann Wannier 构建]
    D --> F
    D --> G[能带与态密度绘图]
    E --> G
    F --> H[05_crpa 约束随机相位近似计算]
```

执行基础 `submit` 命令时，提交范围为可选弛豫、SCF、DOS 和能带阶段。DOS 与能带均依赖 SCF，二者之间没有先后依赖。Wannier 与 cRPA 需在检查前序结果后分别准备和提交。

## 2. 运行环境与安装

### 2.1 环境要求

| 项目 | 要求或用途 |
| --- | --- |
| 操作系统 | Linux；Windows 用户可在 WSL 内安装运行，或连接远程 Linux 集群 |
| Shell | Bash 4 或更新版本，以及常用 Unix 命令行工具 |
| Python | Python 3.10 或更新版本 |
| 安装组件 | 使用安装脚本时，需要 `venv`，以及 `ensurepip` 或支持 `--python` 选项的已有 pip |
| VASP | 用户自行配置的可运行版本；应具备所需计算功能 |
| VASPKIT | 用户自行配置，并根据需要设置可用的赝势库 |
| Wannier/cRPA 支持 | VASP 构建及相关运行组件应支持拟开展的 Wannier 和 cRPA 计算 |
| Slurm | 使用 `submit` 类命令时需要；直接运行不要求安装 Slurm |
| NumPy、Matplotlib | 绘图功能依赖，可通过 `plot` 安装选项安装 |

软件不提供 VASP 可执行文件或赝势文件。安装工作流不能代替配置外部计算程序。原生 Windows 环境不支持本软件的 Bash 计算执行流程，应在 WSL 或 Linux 环境中执行。

计算所需 CPU、内存和磁盘空间取决于原子数、k 点、能带数及计算方法。应根据实际体系进行资源评估；手册示例中的资源数不代表通用的生产计算配置。

### 2.2 使用安装脚本

解压完整源码发布包，在包含 `install.sh` 的目录中执行：

```bash
bash install.sh "$HOME/.local/share/vasp-workflow/1.4.1"
source "$HOME/.local/share/vasp-workflow/1.4.1/bin/activate"
vasp-workflow --version
```

正常情况下，最后一条命令显示 `vasp-workflow 1.4.1`。安装脚本将软件及绘图依赖安装到指定的 Python 虚拟环境，不需要管理员权限，也不会自动修改 Shell 启动文件。

如果目标目录已存在，安装脚本会拒绝覆盖。升级时建议指定新的安装目录，并保留旧环境，以便已生成的批量计算启动脚本继续使用原有环境。每次打开新终端后，应重新激活环境，或使用安装目录下命令的绝对路径。

### 2.3 在已有 Python 环境中安装

在源码目录中执行：

```bash
python -m pip install '.[plot]'
```

`plot` 选项安装 NumPy 和 Matplotlib。如果只需要准备计算文件，可省略该选项：

```bash
python -m pip install .
```

开发和调试时可使用 `python -m pip install -e '.[plot]'` 安装可编辑版本。普通使用者宜安装明确版本的发布包。

### 2.4 离线安装

在与目标集群的 Python 版本、CPU 架构相匹配的联网 Linux 环境中，从源码目录准备 wheel 文件：

```bash
python -m pip wheel '.[plot]' 'setuptools>=68' -w wheelhouse
```

将 `wheelhouse` 复制到目标集群，在已具备 pip 的 Python 环境中执行：

```bash
python -m pip install --no-index --find-links wheelhouse \
  'vasp-scf-crpa-workflow[plot]==1.4.1'
```

如果集群 Python 缺少安装所需组件，应先选择集群提供的适当 Python 环境。更多说明见[安装指南（英文）](installation.md)。

## 3. 计算目录与配置

### 3.1 创建独立计算目录

软件只需安装一次，不同材料分别使用独立目录：

```bash
vasp-workflow init my-material --poscar /path/to/POSCAR --profile slurm
cd my-material
```

将 `/path/to/POSCAR` 替换为实际输入文件路径。输入结构应采用 VASP 5 风格，元素符号位于第 6 行。创建时会生成 `workflow.conf` 和版本元数据，并在指定 `--poscar` 时复制输入结构。

初始化会拒绝覆盖已有配置、初始化元数据或待写入的 POSCAR。该命令只建立计算目录，不会直接开始 VASP 计算。计算目录无需包含程序源码。

`--profile` 支持两种模式：

| 模式 | 默认执行命令 | 适用场景 |
| --- | --- | --- |
| `slurm` | `srun vasp_std` | 使用 Slurm 的计算集群，也是初始化的默认模式 |
| `local` | `vasp_std` | 在适当计算环境中直接执行；可自行配置 MPI 命令 |

新建 Slurm 配置的节点数和每节点任务数均为 1，分区留空。运行前应根据集群要求调整分区、账户、任务数量及运行环境。

### 3.2 主要配置项

`workflow.conf` 采用 Bash 语法，支持变量、执行命令和完整模板。应使用可信来源的配置文件，并在修改后检查语法和参数。

| 配置项 | 作用 |
| --- | --- |
| `VASPKIT_BIN` | VASPKIT 可执行文件名或绝对路径 |
| `PYTHON_BIN` | 可选的 Python 解释器覆盖设置；通常使用安装环境的解释器 |
| `SUBMIT_COMMAND` | 作业提交命令，默认 `sbatch` |
| `EXECUTION_SETUP` | 直接执行和生成作业时使用的模块加载、环境设置命令 |
| `STAGE_COMMANDS` | 默认执行命令及可选的逐阶段执行命令 |
| `SBATCH_PARTITION` | Slurm 分区 |
| `SBATCH_NODES`、`SBATCH_NTASKS_PER_NODE` | 节点数和每节点任务数 |
| `SBATCH_CPUS_PER_TASK`、`SBATCH_TIME` | 每任务 CPU 数和时间限制 |
| `SBATCH_EXTRA` | 账户、QoS 等附加 Slurm 指令 |
| `CRPA_SBATCH_*`、`CRPA_KPAR` | cRPA 阶段的资源覆盖设置及 KPAR |
| `RUN_RELAX`、`GENERATE_BANDS` | 是否准备结构弛豫和能带阶段 |
| `ENCUT`、`ENCUT_FACTOR` | 固定平面波截断能，或根据 POTCAR 中 ENMAX 自动确定截断能的系数 |
| `KPR_RELAX`、`KPR_SCF`、`KPR_DOS`、`KPR_WANN` | 各阶段生成 k 点网格所用的分辨率参数 |
| `INCAR_*_TEMPLATE`、`SBATCH_TEMPLATE` | 各阶段完整 INCAR 模板和作业头模板 |

准备输入时需要使用的 VASPKIT 等工具应在当前终端可用。`EXECUTION_SETUP` 用于计算执行和作业脚本，不会由 `doctor` 自动执行。

### 3.3 新建计算的主要默认参数

下表对应不指定自定义配置时，由 `init` 生成的配置：

| 参数 | 默认值 |
| --- | --- |
| `ENCUT` | `auto` |
| `ENCUT_FACTOR` | `1.50` |
| `EDIFF`、`EDIFFG` | `1e-6`、`-0.02` |
| `ISIF`、`NSW` | `3`、`200` |
| `KPR_RELAX` | `0.03` |
| `KPR_SCF`、`KPR_DOS` | `0.02`、`0.02` |
| `KPR_WANN` | `0.04` |
| `NEDOS` | `2000` |
| `RUN_RELAX`、`GENERATE_BANDS` | `yes`、`yes` |

`ENCUT=auto` 时，程序取 POTCAR 中最大的 ENMAX，乘以 `ENCUT_FACTOR`，再向上取整到 5 eV 的整数倍。这些默认值沿用当前研究配置的部分选择，使用者仍需为具体体系检查收敛性。

### 3.4 配置选择顺序

一般操作命令依次按以下顺序选择配置文件：

1. 命令行显式指定的 `--config FILE`。
2. 环境变量 `WORKFLOW_CONFIG` 指定的文件。
3. 计算目录中的 `workflow.conf`。

显式指定的文件会替代计算目录配置，不是与它叠加合并。所选配置中的赋值会覆盖同名环境变量；缺失的变量采用后端的历史回退默认值，可能与上表的新建配置不同。

`init` 的行为有所区别：指定全局 `--config FILE` 时原样复制该配置，不再追加 local/slurm 默认配置；未指定时使用随软件提供的默认配置及所选 profile。初始化不从 `WORKFLOW_CONFIG` 获取配置。

## 4. 首次计算操作示例

以下操作从完整源码发布包目录开始，使用随包提供的硅结构 `examples/silicon/POSCAR`。该文件演示输入格式，不是已经验证的收敛基准结果。

```bash
vasp-workflow init silicon --poscar examples/silicon/POSCAR --profile slurm
cd silicon
# 编辑 workflow.conf，设置实际集群环境、资源和计算参数。
vasp-workflow doctor prepare
vasp-workflow prepare --no-relax
vasp-workflow doctor submit
vasp-workflow submit --job-name silicon
vasp-workflow status
```

各步骤的含义如下：

1. `init` 创建计算目录并复制结构文件。
2. 编辑配置，确保执行命令、分区、资源及科学参数适合实际体系。
3. `doctor prepare` 检查当前终端中的准备工具及 POSCAR 是否存在。
4. `prepare --no-relax` 跳过弛豫，生成 SCF、DOS、能带目录及相应输入和作业脚本。
5. `doctor submit` 检查提交命令和基本资源数量设置。
6. `submit` 提交基础作业，并建立 `afterok` 依赖关系。
7. `status` 根据已有文件报告阶段状态；实际排队和运行情况应同时查看 Slurm。

如需结构弛豫，应保持 `RUN_RELAX=yes`，并执行不带 `--no-relax` 的 `prepare`。弛豫后的 CONTCAR 会用于 SCF，SCF 的电荷密度会用于 DOS 和能带计算。

如果准备直接运行，应初始化为 `--profile local`，根据机器配置调整执行命令，然后执行：

```bash
vasp-workflow prepare --no-relax
vasp-workflow run
```

直接运行按顺序执行已准备的基础阶段并占用当前会话。应遵守所在集群对登录节点和计算节点的使用要求。

## 5. 命令说明

### 5.1 全局选项

默认操作当前目录。选择其他计算目录或配置时，全局选项必须位于子命令之前：

```bash
vasp-workflow --root /path/to/case --config /path/to/custom.conf prepare
```

`--root` 表示计算目录，`--config` 表示配置文件；子命令自身的参数放在子命令之后。

### 5.2 命令总览

| 命令 | 功能与主要参数 |
| --- | --- |
| `--help`、`--version` | 显示命令入口帮助或软件版本 |
| `init DIR --poscar FILE --profile slurm` | 初始化计算；profile 也可选 `local` |
| `doctor prepare` | 检查准备计算所需的基本环境；默认检查模式 |
| `doctor plot` | 检查绘图相关工具及 NumPy、Matplotlib |
| `doctor submit` | 检查 Slurm 提交命令和基本资源数量 |
| `doctor run` | 检查直接执行的基础工具并显示配置的执行命令 |
| `prepare [--no-relax] [--force]` | 生成基础计算输入和作业脚本 |
| `run` | 顺序执行已准备的基础阶段 |
| `submit [--job-name PREFIX]` | 提交基础 Slurm 依赖流程 |
| `execute STAGE` | 直接执行指定的已准备阶段，例如 `01_scf` |
| `status` | 查询已登记阶段的文件状态 |
| `postprocess [OPTIONS]` | 绘制投影能带和态密度 |
| `rank-bands --elements E... --orbitals O...` | 根据轨道投影权重排序能带 |
| `prepare-wannier [OPTIONS]` | 准备 `04_wann` |
| `run-wannier`、`submit-wannier` | 直接执行或提交 Wannier 阶段 |
| `prepare-crpa [OPTIONS]` | 准备 `05_crpa` |
| `run-crpa`、`submit-crpa` | 直接执行或提交 cRPA 阶段 |
| `batch [OPTIONS] STRUCTURE_DIR [CALCULATION_DIR]` | 批量准备、运行或提交多个结构 |

`doctor` 不执行 VASP、VASPKIT 或 Slurm 作业，也不执行配置中的环境加载命令。检查通过表示当前终端满足其检查范围，不能据此确认计算节点环境、赝势库或物理结果正确。

### 5.3 提交与独立作业脚本

`submit`、`submit-wannier` 和 `submit-crpa` 支持 `--job-name PREFIX`，也支持 `--job-name=PREFIX`。软件会为名称追加对应阶段标识。

生成的各阶段 `job.sh` 为独立脚本，可在对应目录中直接提交：

```bash
cd 01_scf
sbatch job.sh
```

独立提交时，应自行确认前序数据已准备好，或显式设置调度依赖。修改 `workflow.conf` 不会自动修改已生成的作业脚本；应在适当时机重新生成输入和作业。不要在作业运行过程中替换其输入文件。

## 6. 能带、态密度绘图与能带排序

### 6.1 元素投影绘图

DOS 和能带阶段完成后，可执行：

```bash
vasp-workflow postprocess --elements Si --emin -5 --emax 5
```

`--emin`、`--emax` 设置绘图能量范围，单位为 eV。可以重复指定 `--format` 输出多种格式：

```bash
vasp-workflow postprocess --elements Mn Sb --emin -4 --emax 4 \
  --format png --format pdf --format svg --title "Mn-Sb"
```

请将元素符号替换为实际体系中的元素。默认输出文件基名为 `projected_band_dos`；可使用 `--output` 修改。已有合适的 PBAND/PDOS 数据时，可使用 `--reuse-data` 跳过 VASPKIT 数据生成。

### 6.2 轨道分辨绘图与 Wannier 能带叠加

例如，对含 Ni 的体系选择轨道分量：

```bash
vasp-workflow postprocess --orbital-element Ni --orbitals dz2 dx2-y2
```

完成 Wannier 计算并具备对应能带文件后，可用 `--wannier-bands` 叠加 Wannier 插值能带：

```bash
vasp-workflow postprocess --elements Si --wannier-bands
```

应检查参考能量对齐、插值能带与原始能带的一致性。完整绘图选项可通过 `vasp-workflow postprocess --help` 查看。

### 6.3 能带排序

以下命令读取 SCF 轨道投影，并结合 DOS 阶段能量信息生成排序结果：

```bash
vasp-workflow rank-bands --elements Mn Sb --orbitals d p --csv band_ranking.csv
```

该排序命令会组合选定元素及壳层的投影；它与 `prepare-wannier` 中按位置配对的元素／轨道选择规则不同。可用 `--scf-directory`、`--dos-directory` 指定数据目录，用 `--num-bands` 限制输出的高权重能带数量。详细说明见 `vasp-workflow rank-bands --help`。

## 7. Wannier 与 cRPA 计算

### 7.1 Wannier 输入准备

在 SCF、DOS 以及所需的能带计算完成并检查结果后执行：

```bash
vasp-workflow prepare-wannier --elements Si Si --orbitals s p
```

这里元素和轨道按位置配对，表示 `Si:s` 和 `Si:p`。默认 Wannier 函数数量根据相应元素原子数和壳层简并度推断，其中 `s=1`、`p=3`、`d=5`、`f=7`；可使用 `--num-bands` 覆盖默认数量。目标子空间应根据研究问题确定。

主要窗口选项如下：

| 选项 | 默认值与含义 |
| --- | --- |
| `--window-method` | `adaptive`；可选 `legacy` 使用旧窗口公式 |
| `--search-energy-range MIN MAX` | `-20 20`，相对于 SCF 费米能的搜索区间，单位 eV |
| `--outer-coverage` | `0.8`，外窗口局部投影权重的中心覆盖比例 |
| `--frozen-character-min` | `0.70`，冻结窗口的目标轨道特征阈值 |
| `--frozen-margin` | `0.1` eV，冻结窗口向内缩进的边界余量 |
| `--kpr` | 默认来自 `KPR_WANN`，控制 Wannier 网格生成 |
| `--force` | 有意重新生成已存在的工作流阶段 |

搜索区间必须具有有限且满足 `MIN < MAX` 的端点。窗口不要求包含费米能。如果没有符合条件的冻结窗口，程序可能生成只有外窗口的输入，并在诊断文件中说明原因。

准备后应查看：

```text
04_wann/INCAR
04_wann/wannier_window_diagnostics.json
```

确认目标轨道、函数数量、窗口和输入设置后，再运行或提交：

```bash
vasp-workflow submit-wannier --job-name silicon
# 直接执行环境可改用 vasp-workflow run-wannier。
```

### 7.2 cRPA 输入准备

等待 Wannier 计算完成，检查局域化及插值结果，并确认重启文件齐备后执行：

```bash
vasp-workflow prepare-crpa --target-states 1-8
vasp-workflow submit-crpa --job-name silicon
```

`1-8` 仅用于本手册双原子 Si、s/p 子空间示例中推断出的八个 Wannier 函数。实际目标态范围应根据实际基组和物理问题选择。

不指定 `--target-states` 时，默认选择全部 Wannier 态。参数支持从 1 开始的单个编号和包含端点的编号范围，例如 `1-5 8 10-12`，所选编号必须在实际 Wannier 基组范围内。

| 选项 | 作用 |
| --- | --- |
| `--target-states` | 指定从屏蔽通道中排除的目标 Wannier 态编号 |
| `--nbandsgw` | 覆盖 NBANDSGW；默认使用完成的 Wannier 计算的有效能带数 |
| `--encutgw` | 覆盖响应函数截断能；默认是平面波截断能的三分之二 |
| `--kpar` | 覆盖 cRPA KPAR；工作流默认传入配置中的 `CRPA_KPAR` |
| `--force` | 有意重新生成已存在的 cRPA 阶段 |

`submit-wannier` 和 `submit-crpa` 不会自动添加与前序作业之间的调度依赖，应在前序阶段完成后使用。直接运行时分别使用 `run-wannier`、`run-crpa`。

## 8. 批量计算

### 8.1 输入组织

支持以下结构文件组织形式：

```text
structures/
├── POSCAR_materialA.vasp
└── materialB/
    └── POSCAR
```

程序识别 `POSCAR*`、`*.vasp`、`*.poscar` 等文件，并为每个结构生成独立计算目录。建议先检查输入到输出的目录映射：

```bash
vasp-workflow --config /path/to/workflow.conf batch \
  --dry-run --mode prepare /path/to/structures /path/to/calculations
```

### 8.2 准备与提交

确认映射和配置后，先生成输入用于审阅：

```bash
vasp-workflow --config /path/to/workflow.conf batch \
  --mode prepare /path/to/structures /path/to/calculations
```

批量模式默认是 `submit`，会准备并提交计算；使用 `--mode prepare` 可仅准备文件。`--mode run` 为直接执行，`--no-relax` 可跳过弛豫。

每个计算目录包含 POSCAR、配置副本、版本记录、生成的阶段目录，以及一个调用安装环境的 `workflow.sh` 启动脚本。这个按计算生成的脚本仍然有效，与已归档的旧根目录脚本不同。

已有目录默认跳过。`--force` 用于刷新带有批量工作流标识的已有计算，但输入 POSCAR 已改变或没有批量所有权标识的目录仍会被跳过。批量运行会继续处理其他结构，最后输出成功、跳过和失败数量；只要有失败，命令就返回非零退出码。

如果先采用 `--mode prepare`，审阅后可进入各计算目录执行 `vasp-workflow submit`。再次对相同目录执行默认批量命令会跳过已有计算；使用 `--force` 会涉及重新生成文件，不应仅为提交已有作业而盲目使用。

批量目录的启动脚本指向创建它的安装环境。应保留该环境，或激活其他明确版本后使用 `vasp-workflow --root /path/to/case status` 等命令管理已有计算。

## 9. 输入、输出与状态查询

### 9.1 文件和目录说明

| 位置或文件 | 主要用途 |
| --- | --- |
| `POSCAR` | 输入结构 |
| `POTCAR` | 用户提供或通过 VASPKIT 生成的赝势组合 |
| `workflow.conf` | 本计算的执行环境、资源、科学参数和模板 |
| `.workflow-release.json` | 初始化时的软件版本和配置哈希等元数据 |
| `.workflow-version` | 批量创建时记录的软件版本 |
| `.workflow-stages` | 工作流登记的阶段列表 |
| `00_relax/` | 弛豫输入和输出，CONTCAR 用于后续 SCF |
| `01_scf/` | SCF 输入和输出，包括 CHGCAR、PROCAR、OUTCAR 等 |
| `02_dos/` | DOS 输入和输出，包括 EIGENVAL、DOSCAR 等 |
| `03_band/` | 能带路径、能量及投影数据 |
| `04_wann/` | Wannier 输入、诊断、重启数据和计算输出 |
| `05_crpa/` | cRPA 输入、重启数据和相互作用计算输出 |
| `projected_band_dos.*` | 默认名称的投影能带和态密度图 |

创建时的版本记录不代表之后每一次参数修改或软件切换。保存研究结果时，应同时保留实际使用的配置、输入文件和作业脚本。

### 9.2 状态含义

执行 `vasp-workflow status` 后，已登记阶段可能显示：

| 状态 | 判定依据 |
| --- | --- |
| `prepared` | 阶段已登记，尚未检测到用于判定启动的非空 OUTCAR |
| `started` | 检测到非空 OUTCAR |
| `finished` | OUTCAR 中检测到预期的 VASP 计时／统计结束标记 |

状态查询不会访问 Slurm 队列，也不会验证能量、力、应力或物理结果的收敛性。排队、正在运行和作业失败等情况应结合调度系统、标准输出和错误日志判断。

## 10. 常见问题与恢复操作

| 问题 | 检查与处理方式 |
| --- | --- |
| 找不到 `vasp-workflow` | 激活安装环境，或使用命令的完整路径 |
| 安装提示缺少 venv、ensurepip 或 pip | 选择具备相应组件的集群 Python 环境 |
| 提示缺少 NumPy 或 Matplotlib | 在实际使用的解释器环境中安装 `plot` 依赖 |
| 找不到 POSCAR | 检查 `--root` 和文件位置，确认结构文件非空且格式正确 |
| 找不到 VASPKIT | 在当前终端加载模块，或正确设置 `VASPKIT_BIN` |
| POTCAR 生成失败 | 检查元素符号、赝势库配置及可访问性 |
| Slurm 提交失败 | 检查分区、账户、资源额度、提交命令及错误输出 |
| 缺少前序 CHGCAR 或 CONTCAR | 确认前序阶段完成，并检查其日志和输出 |
| 阶段目录已存在 | 先确认已有计算用途，再选择新目录或有意使用 `--force` |
| Wannier 窗口选择失败 | 检查上游数据、轨道配对、能带数及诊断信息 |
| cRPA 目标态编号不合法 | 使用实际 Wannier 基组范围内的编号 |
| 修改配置后已有作业仍使用旧设置 | 已生成脚本保留生成时的设置；在适当时机重新生成 |
| 批量启动脚本引用的环境已删除 | 激活所需版本，使用 `vasp-workflow --root CASE` 管理计算 |

重新生成前应保留需要的研究结果。软件没有适用于所有失败类型的自动重启或自动收敛恢复功能。应先确定 VASP 失败原因，再依据阶段特性选择合理的重启文件和参数。

旧版本原始代码、集群配置及已移除的根目录文件已保存在本地 `archive/legacy-files-1.4.zip`，新源码发布包不包含该本地备份。日常使用应采用安装后的 `vasp-workflow` 命令。

## 11. 物理结果检查与验证范围

使用者应根据研究任务检查：

1. 结构弛豫是否收敛，力、应力及结构变化是否合理。
2. 电子迭代、平面波截断能和 k 点网格是否达到所需精度。
3. 所选轨道投影及目标子空间是否适合物理问题。
4. Wannier 函数展宽、局域化和能带插值是否可靠。
5. cRPA 的能带数、响应函数截断能及其他参数是否收敛。

窗口准备时的检查针对所提供的 SCF/DOS 网格，不能替代实际 Wannier 网格、局域化、插值质量和 cRPA 收敛检查。作业正常结束也不能单独证明物理结果可靠。

当前候选版本已通过记录在案的 Python 测试、模拟外部程序的 Bash 工作流测试、安装检查及合成数据绘图检查。这些测试没有运行真实 VASP/Wannier/cRPA 生产计算。

随软件提供的硅 POSCAR 用于输入演示；绘图测试数据属于合成测试数据，不应作为真实材料计算结果引用。具体测试环境与范围见[验证记录（英文）](validation.md)，计算原理见[物理说明（英文）](physics_reference.md)。

## 12. 软著材料完善说明

本手册保留“候选版本”和“待审阅草稿”标记。正式申报前，由申请人确认软件的登记全称、著作权人、开发完成日期、最终版本号，以及所在单位的材料格式要求。

建议从一个经确认可公开使用的完整计算案例中补充以下真实运行材料：

| 材料 | 建议展示内容 |
| --- | --- |
| 安装与版本 | 安装完成信息及版本查询输出 |
| 环境与配置 | 实际运行环境、必要软件版本和计算资源 |
| 初始化与准备 | 输入结构、配置和生成的阶段目录 |
| 作业管理 | 提交输出、状态查询及相应日志 |
| 后处理 | 实际投影能带、态密度图及说明 |
| Wannier | 窗口诊断、局域化和插值检查结果 |
| cRPA | 完成标志及与软件功能对应的结果展示 |

截图中的软件名称、版本以及相关叙述应与最终源码和申请材料一致。模拟测试输出须明确标注，不应用于冒充真实生产计算。源程序排版与提交材料准备说明见[软著材料准备说明（英文）](registration.md)。
