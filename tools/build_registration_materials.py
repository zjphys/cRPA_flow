"""Build a reviewable personal software-registration packet from this checkout."""
from __future__ import annotations

import csv
import hashlib
import html
import json
import os
import tomllib
from datetime import datetime, timezone
import re
import subprocess
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "copyright_application"
OUT.mkdir(parents=True, exist_ok=True)
EVIDENCE = OUT / "核验记录"
EVIDENCE.mkdir(exist_ok=True)
PROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
DETAILS = json.loads((ROOT / "docs/registration_details.json").read_text(encoding="utf-8"))
NAME = DETAILS["official_software_name"] or PROJECT["name"]
VERSION = "V" + PROJECT["version"]
IDENTITY = f"{NAME} {VERSION}"
pdfmetrics.registerFont(TTFont("CN", os.environ.get("REGISTRATION_CN_FONT", "C:/Windows/Fonts/simsun.ttc"), subfontIndex=0))
pdfmetrics.registerFont(TTFont("CNBold", os.environ.get("REGISTRATION_BOLD_FONT", "C:/Windows/Fonts/simhei.ttf")))
pdfmetrics.registerFont(TTFont("Code", os.environ.get("REGISTRATION_CODE_FONT", "C:/Windows/Fonts/consola.ttf")))
W, H = A4
LEFT, RIGHT = 43, W - 43
WIDTH = RIGHT - LEFT


def font_for(ch: str, code=False, bold=False) -> str:
    if bold:
        return "CNBold"
    return "Code" if code and ord(ch) < 128 else "CN"


def width(text: str, size: float, code=False, bold=False) -> float:
    return sum(pdfmetrics.stringWidth(c, font_for(c, code, bold), size) for c in text)


def wrap(text: str, size: float, available=WIDTH, code=False, bold=False):
    result, line, used = [], "", 0
    for ch in text.expandtabs(4):
        cw = pdfmetrics.stringWidth(ch, font_for(ch, code, bold), size)
        if line and used + cw > available:
            if not code and ch in "，。；：！？、）】》”’" and len(line) > 1:
                last = line[-1]
                result.append(line[:-1])
                line = last
                used = pdfmetrics.stringWidth(last, font_for(last, code, bold), size)
            else:
                result.append(line)
                line, used = "", 0
        line += ch
        used += cw
    if line or not result:
        result.append(line)
    return result


def draw(c, text, x, y, size, code=False, bold=False):
    c.setFillColorRGB(0, 0, 0)
    chunks = []
    for ch in text:
        font = font_for(ch, code, bold)
        if chunks and chunks[-1][0] == font:
            chunks[-1][1] += ch
        else:
            chunks.append([font, ch])
    for font, value in chunks:
        c.setFont(font, size)
        c.drawString(x, y, value)
        x += pdfmetrics.stringWidth(value, font, size)


def header(c, page, title, footer=""):
    draw(c, IDENTITY, LEFT, H - 29, 9)
    draw(c, str(page), RIGHT - width(str(page), 9), H - 29, 9)
    draw(c, title, LEFT, 27, 8)
    if footer:
        draw(c, footer, RIGHT - width(footer, 8), 27, 8)


def clean_inline(s):
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
    return s.replace("**", "").replace("`", "").rstrip("\\")


def blocks_from_md(md):
    blocks, code = [], False
    for raw in md.splitlines():
        if raw.startswith("```"):
            code = not code
            continue
        if not raw.strip():
            continue
        if raw.startswith("| ") or raw.startswith("|---"):
            parts = [clean_inline(p.strip()) for p in raw.strip("|").split("|")]
            if all(re.fullmatch(r"[:\- ]+", p or "-") for p in parts):
                continue
            raw = "：".join(parts)
        heading = not code and raw.startswith("#")
        level = len(raw) - len(raw.lstrip("#")) if heading else 0
        text = raw if code else clean_inline(raw.lstrip("# ") if heading else raw)
        if not code:
            text = text.replace("→", "至").replace("—", "-")
        size = 14 if level == 1 else 11.5 if heading else 9 if code else 10.5
        lines = wrap(text, size, code=code, bold=heading)
        blocks.append({"lines": lines, "code": code, "bold": heading, "size": size})
    return blocks


def document(stem, md, min_lines=False):
    (OUT / f"{stem}.md").write_text(md, encoding="utf-8")
    blocks = blocks_from_md(md)
    # Fixed baseline grid: readable A4 text, 40 physical rows per page.
    rows = [dict(text=line, **{k: v for k, v in b.items() if k != "lines"})
            for b in blocks for line in b["lines"]]
    capacity = 52 if stem.startswith("02_") else 40
    baseline = 14.1 if stem.startswith("02_") else 18
    pages = []
    while rows:
        take = min(capacity, len(rows))
        while take > 1 and take < len(rows) and rows[take - 1]["bold"]:
            take -= 1
        pages.append(rows[:take])
        rows = rows[take:]
    if min_lines:
        assert all(len(p) >= 30 for p in pages[:-1])
    c = canvas.Canvas(str(OUT / f"{stem}.pdf"), pagesize=A4)
    c.setTitle(f"{IDENTITY} {stem}")
    c.setAuthor("")
    for number, page in enumerate(pages, 1):
        header(c, number, stem, f"共 {len(pages)} 页")
        for row, item in enumerate(page):
            draw(c, item["text"], LEFT, H - 65 - row * baseline,
                 item["size"], item["code"], item["bold"])
        c.showPage()
    c.save()
    # Browser/Word-readable editable alternative; pagination authority is the PDF.
    body = []
    for b in blocks:
        tag = "h2" if b["bold"] else "pre" if b["code"] else "p"
        body.append(f"<{tag}>" + html.escape("\n".join(b["lines"])) + f"</{tag}>")
    (OUT / f"{stem}.html").write_text(
        '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>' + html.escape(stem) +
        '</title><style>@page{size:A4;margin:20mm}body{font-family:SimSun,serif;max-width:170mm;margin:20mm auto;color:#000;line-height:1.6}h2{font-family:SimHei,sans-serif;font-size:14pt}p{font-size:11pt}pre{white-space:pre-wrap;font-family:Consolas,SimSun,monospace;font-size:9pt}</style><body>' +
        "\n".join(body) + "</body></html>", encoding="utf-8")
    return {"file": f"{stem}.pdf", "pages": len(pages), "body_lines": [len(p) for p in pages]}


def source():
    files = [ROOT / "install.sh"] + sorted(p for p in (ROOT / "src/crpa_workflow").rglob("*")
                                                   if p.is_file() and p.suffix in (".py", ".sh", ".conf"))
    records, manifest = [], []
    with ZipFile(EVIDENCE / "源文件快照.zip", "w", ZIP_DEFLATED) as z:
        for path in files:
            data = path.read_bytes()
            rel = path.relative_to(ROOT).as_posix()
            text = data.decode("utf-8").replace("\r\n", "\n")
            lines = text.splitlines()
            manifest.append({"path": rel, "physical_lines": len(lines), "nonempty_lines": sum(bool(x.strip()) for x in lines),
                             "sha256_bytes": hashlib.sha256(data).hexdigest(), "sha256_lf_utf8": hashlib.sha256(text.encode()).hexdigest()})
            z.writestr(rel, data)
            records.extend({"path": rel, "line": i, "text": line} for i, line in enumerate(lines, 1) if line.strip())
    # Remove blank-only lines for filing layout, preserving every nonempty source line.
    page_count = max(1, len(records) // 50)
    base, extra = divmod(len(records), page_count)
    pages, offset = [], 0
    for i in range(page_count):
        n = base + (i < extra)
        pages.append(records[offset:offset + n])
        offset += n
    assert offset == len(records) and all(len(p) >= 50 for p in pages)
    selected = list(range(page_count)) if page_count <= 60 else list(range(30)) + list(range(page_count - 30, page_count))
    mapping, geometry = [], []
    c = canvas.Canvas(str(OUT / "04_源程序鉴别材料.pdf"), pagesize=A4)
    c.setTitle(f"{IDENTITY} 源程序鉴别材料")
    c.setAuthor("")
    for seq, full_index in enumerate(selected, 1):
        page = pages[full_index]
        size = 8
        visual = [line for r in page for line in wrap(r["text"], size, code=True)]
        while len(visual) > 77 and size > 7:
            size -= .25
            visual = [line for r in page for line in wrap(r["text"], size, code=True)]
        leading = min(13.7, 719 / max(1, len(visual) - 1))
        assert leading >= size + 1
        header(c, seq, "源程序鉴别材料", f"完整排版第 {full_index + 1} 页 共 {page_count} 页")
        for i, line in enumerate(visual):
            draw(c, line, LEFT, H - 59 - i * leading, size, code=True)
        c.showPage()
        mapping.append({"交存页码": seq, "完整排版页码": full_index + 1, "首文件": page[0]["path"], "首行": page[0]["line"],
                        "末文件": page[-1]["path"], "末行": page[-1]["line"], "原始非空行数": len(page), "显示行数": len(visual)})
        geometry.append({"page": seq, "font_size": size, "leading": leading, "body_lines": len(visual)})
    c.save()
    with (EVIDENCE / "源程序页码对应表.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(mapping[0]))
        w.writeheader()
        w.writerows(mapping)
    (EVIDENCE / "源文件清单.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (EVIDENCE / "完整源程序及行号.txt").write_text("\n".join(f"{r['path']}:{r['line']}\t{r['text']}" for r in records), encoding="utf-8")
    (EVIDENCE / "交存源程序文本.txt").write_text("\n\f\n".join("\n".join(r["text"] for r in pages[i]) for i in selected), encoding="utf-8")
    return {"files": len(files), "physical_lines": sum(m["physical_lines"] for m in manifest), "nonempty_lines": len(records),
            "full_pages": page_count, "submitted_pages": len(selected), "selected_pages": [i + 1 for i in selected], "geometry": geometry}


def main():
    stats = source()
    fields = {
        "official_software_name": "正式软件名称",
        "registration_version_confirmed": "登记版本确认",
        "applicants_and_rights_holders": "所有申请人及著作权人（姓名或单位全称、类别及列示顺序）",
        "developers_and_contributions": "开发者及实际贡献",
        "development_mode": "开发方式（独立、合作、委托或其他）",
        "ownership_basis_and_supporting_documents": "权属依据及证明文件",
        "project_origin_and_institutional_relationship": "项目来源及任职、学校、单位关系",
        "rights_acquisition_and_scope": "权利取得方式及范围",
        "original_or_modified_work": "原创或修改作品及授权依据",
        "completion_date": "实际开发完成日期",
        "publication_status_date_and_place": "发表状态、首次发表日期及地点",
        "previous_registration": "既往登记情况及登记号",
        "filing_representative": "登记办理代表",
        "actual_development_environment": "实际开发硬件、操作系统及工具",
        "verified_simulation_environment": "实际验证的计算环境和外部软件版本",
        "identity_documents_locally_prepared": "身份证明是否已由申请人本地备妥",
        "applicable_signatures_completed": "适用文件是否已由当事人实际签署",
    }
    pending = [label for key, label in fields.items() if not DETAILS.get(key)]
    confirmed = "\n".join(f"{label}：{DETAILS.get(key) or '待申请人确认/补齐'}。" for key, label in fields.items())
    information = f"""# 软件著作权登记填报信息草稿
本表用于整理中国计算机软件著作权登记信息，不是官方申请表。姓名、权属、日期及签章均须以申请人确认和真实证明为依据。当前材料状态：待确认，未提交。
## 软件基本信息
技术项目名称：{PROJECT['name']}。本次材料页眉名称：{NAME}。
技术版本：{VERSION}，由 pyproject.toml 自动读取；是否作为登记版本见下方确认项。
软件分类建议：科研计算辅助与工作流管理应用软件，具体选项以登记系统为准。
## 登记事实及证明材料
{confirmed}
联系人姓名、手机号、电子邮箱和地址：由办理人在系统中填写。
国籍、证件号码及证件扫描件：按申请人类别在本地备妥，不纳入源代码仓库。
开发完成日期不能用本次修复、材料生成或 Git 提交日期替代。
合作开发、委托开发、职务开发或个人独立开发均尚未确定；不能仅因导师关系、姓名顺序或 Git 作者推断权属。
## 技术信息建议填报文本
编程语言：Python、Bash。
源程序量：运行相关源文件共 {stats['physical_lines']} 行，含空行和注释；非空行 {stats['nonempty_lines']} 行。统计范围为 install.sh 与 src/crpa_workflow 下的 .py、.sh、.conf 文件，排除测试、文档、历史归档、第三方依赖和生成数据。请按系统字段口径选用，勿把交存节选的行数填成总源程序量。
开发硬件环境：待填写实际使用的 CPU、内存、磁盘等，不能用推荐配置代替实际环境。
运行硬件环境：Linux 工作站或高性能计算集群；CPU、内存、磁盘需求随原子数、k 点及能带数变化，具体已验证配置待填写。
开发操作系统及工具：待填写实际开发环境。历史测试记录包括 Windows 和 Ubuntu/WSL，不据此推定全部开发环境。
运行软件环境：Linux，Bash 4 及以上，Python 3.10 及以上；按功能配置 VASP、VASPKIT；Slurm 用于作业提交；NumPy 和 Matplotlib 用于绘图。
开发目的：减少电子结构计算中重复的输入文件配置、阶段数据传递和作业操作，提高多材料计算流程的一致性与可追溯性。
面向领域：凝聚态物理、计算材料学及电子结构科研计算。
主要功能：创建独立计算目录并检查环境；生成弛豫、自洽场、态密度和能带输入及作业脚本；执行或提交具有依赖关系的基础计算；查询文件状态；准备 Wannier 与 cRPA 输入；完成轨道投影能带排序、窗口选择、绘图和批量计算管理。
技术特点：采用 Python 命令入口与 Bash 作业后端分层组织，软件安装与计算数据分离；通过阶段目录和模板配置组织输入；生成独立作业脚本；提供轨道投影分析、自适应能量窗口选择和目标态编号校验，并记录初始化版本信息。
## 提交前核对
1. 补齐上列事实，核对权属证明、贡献来源及第三方材料边界。
2. 确认名称与登记版本后重新生成全部材料，避免手工改 PDF 造成不一致。
3. 仅在合作开发适用且当事人确认条款时使用 02 协议模板；否则按真实权属依据准备文件。
4. 使用官方系统当次生成的申请表及签章页，由当事人核对并真实签署。
5. 逐项上传对应材料；本草稿、核验记录及完整 ZIP 不替代正式申请表。
6. 按实际办理渠道核对当前文件大小、签章、实名验证等要求，本次未登录登记系统。
7. 验证范围为单元测试、模拟外部工具和安装测试；未实施真实 VASP/Wannier/cRPA 科学计算。
## 规则及资料依据
国家版权局《计算机软件著作权登记办法》第八至十二条：
https://www.ncac.gov.cn/xxfb/flfg/bmgz/202410/t20241015_869486.html
《计算机软件保护条例》第九至十四条：
https://www.cac.gov.cn/2013-02/08/c_12648744.htm
技术依据：pyproject.toml、src/crpa_workflow、docs/user_manual_zh.md、docs/validation.md。
"""
    agreement = f"""# 合作开发协议模板（适用性待确认）
当前尚未确认合作开发事实或著作权人身份。本稿仅供确认为双方合作开发后填写审阅；不适用于直接证明职务、委托或其他权属关系。多人合作时应涵盖全部相关当事人，不得遗漏。
甲方姓名或单位全称：____________________________________________
乙方姓名或单位全称：____________________________________________
身份/主体资格证明及代表权限：___________________________________
## 第一条 软件及真实开发情况
软件名称：{NAME}。版本：{VERSION}（签署前确认与登记材料一致）。
实际开发完成日期：________年____月____日。
项目来源及与任职单位、学校或委托人的关系：_______________________
_______________________________________________________________
甲方实际开发分工及成果：________________________________________
乙方实际开发分工及成果：________________________________________
已有协议、任务书、授权或其他权属证明：___________________________
双方应核对其有权处分的范围；本协议不处分第三方已有权利。
## 第二条 权属与权利行使（由当事人协商填写）
本软件著作权的具体归属及范围：__________________________________
共有方式或份额（如适用）：______________________________________
各方使用、修改及研究发表权限：__________________________________
对外许可、转让、开源发布等事项的决定方式：_______________________
_______________________________________________________________
收益分配及费用承担：____________________________________________
第三方程序、数据及其他作品仍归原权利人，不作为本软件原创源码申报。
## 第三条 登记办理（由当事人确认）
申请人及著作权人完整名单、类别和列示顺序：_______________________
_______________________________________________________________
办理代表及授权范围：____________________________________________
姓名顺序本身不确定贡献、份额或单独处分其他当事人权利的权限。
## 第四条 其他约定及签署
争议处理及其他约定：____________________________________________
_______________________________________________________________
双方逐项核对真实情况和条款后签署；所有空项应填写或标明不适用。
本模板不替代官方申请表、签章页、身份证明或已有权属证明。
甲方签名/盖章：________________ 日期：________年____月____日。
乙方签名/盖章：________________ 日期：________年____月____日。
签署地点：_____________________________________________________
"""
    original = (ROOT / "docs/user_manual_zh.md").read_text(encoding="utf-8")
    # Retain factual user-facing instructions, remove registration packaging section.
    manual = original[original.index("## 1. 软件概述"):original.index("## 12. 软著材料完善说明")]
    manual = re.sub(r"```mermaid.*?```", "计算依赖：POSCAR 至可选弛豫至 SCF；SCF 分别供 DOS 和能带使用；检查 SCF/DOS 结果后准备 Wannier，再在 Wannier 完成并检查后准备 cRPA。", manual, flags=re.S)
    manual = f"# {NAME} 用户操作说明书\n软件版本：{VERSION}。本手册说明 Linux 命令行软件的安装、配置、计算阶段管理和后处理操作。示例命令用于解释操作方法；示例结构与测试数据不代表真实材料的收敛结果。\n" + manual
    summaries = [document("01_登记填报信息草稿", information), document("02_合作开发协议待填写", agreement),
                 document("03_用户操作说明书", manual, min_lines=True)]
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    report = {"software": NAME, "version": VERSION, "git_commit": commit, "identity_status": "项目名和版本用于草稿，最终登记名称待确认",
              "documents": summaries, "source": stats,
              "generated_utc": datetime.now(timezone.utc).isoformat(),
              "git_status": subprocess.check_output(["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=ROOT, text=True),
              "pending_registration_details": pending, "ready_to_submit": False}
    (EVIDENCE / "生成与排版记录.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    readme = f"""# 软件著作权申请材料包

软件为当前项目 {IDENTITY}。申请人、开发方式、权属依据及日期尚待确认；当前不可直接提交。

## 文件用途

- 01 登记填报信息草稿：把技术字段和待填事项整理在一起，不是官方申请表。
- 02 合作开发协议待填写：仅在确认适用合作开发时，按真实当事人及权属情况填写审阅签署。
- 03 用户操作说明书：基于当前代码与既有中文手册整理，完整提交，共 {summaries[2]['pages']} 页。
- 04 源程序鉴别材料：共 {stats['submitted_pages']} 页，取完整排版的前30页和后30页。不是仅对挑选模块进行节选。
- 同名 Markdown 和 HTML：可编辑文本；HTML 可在浏览器或文字处理软件中打开，修改后须重新导出并检查页数。
- 核验记录：原始源文件 ZIP、哈希清单、完整文本、交存文本及页码映射，供本人留存核对，不是默认上传材料。

## 仍需本人完成

1. 确认最终软件全称和登记版本，当前全部 PDF 页眉使用 {IDENTITY}。
2. 补齐全部申请人和开发者姓名或单位全称、实际开发分工、开发完成日期、发表情况、实际开发环境。
3. 补充适用的身份证明，在官方系统完成实名认证及所需验证。
4. 相关当事人确认适用文件的条款后实际签名，不要倒签或代签。
5. 登录中国版权保护中心官网 https://www.ccopyright.com.cn/ ，填报后使用系统当次生成的正式签章页。逐条核对实际声明，按系统要求签署上传。

## 源码口径

共 {stats['files']} 个运行相关文件，{stats['physical_lines']} 个物理行（含空行和注释），{stats['nonempty_lines']} 个非空行。
排版仅省略空白行，非空行内容和缩进保留，长行只作显示换行；完整排版共 {stats['full_pages']} 页，每页至少50个原始非空行。
选取完整页1至30和{stats['full_pages'] - 29}至{stats['full_pages']}，交存页连续编号1至60；精确原文件行号见 CSV。
源文件按现有 export_source.py 的顺序排列，排除测试、第三方包、历史归档与计算数据。相关 .conf 为随软件分发的运行配置和模板。
代码快照来自 Git {commit} 对应工作区内容；哈希以实际文件为准。

## 材料状态

这是供核对和补全的申请准备包，未提交登记。PDF 已排版，尚待个人信息及名称确认。
说明书保留真实功能边界和既有测试范围；没有编造真实 VASP、Wannier 或 cRPA 运行截图和科研结果。
现有环境未提供可用的 Word 渲染器，因此交付 PDF 与可编辑 HTML/Markdown，不附未校验排版的 DOCX。
技术文件中的版本{PROJECT["version"]}目前仍为候选版本；不能从测试或本次材料生成日期推定开发完成日期和公开发表日期。

官方材料要求以登记系统当前页面为准。申请表和签章页、实名认证、身份证明、相关当事人签署均需本人办理。
"""
    (OUT / "先读我.md").write_text(readme, encoding="utf-8")
    (OUT / "登记待确认事项.md").write_text("# 登记待确认事项\n\n" + confirmed + "\n", encoding="utf-8")
    (OUT / "软件名称候选.md").write_text(
        f"# 软件名称候选\n\n当前技术名称：{PROJECT['name']}；版本：{VERSION}。\n"
        "建议中文名称：电子结构与约束随机相位近似计算流程管理软件。\n"
        "正式名称和登记版本仍待申请人确认，确认后须统一重新生成全部材料。\n", encoding="utf-8")
    input_paths = [ROOT / name for name in ("pyproject.toml", "MANIFEST.in", "README.md", "CHANGELOG.md", "install.sh")]
    for directory in ("src/crpa_workflow", "docs", "tools", "tests", "examples"):
        input_paths.extend(p for p in (ROOT / directory).rglob("*") if p.is_file()
                           and "__pycache__" not in p.parts and p.suffix != ".pyc")
    inputs = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(set(input_paths))}
    (EVIDENCE / "生成输入哈希.json").write_text(json.dumps(inputs, ensure_ascii=False, indent=2), encoding="utf-8")
    with ZipFile(EVIDENCE / "生成输入快照.zip", "w", ZIP_DEFLATED) as z:
        for rel in inputs:
            z.write(ROOT / rel, rel)
    (EVIDENCE / "工作区差异.patch").write_bytes(subprocess.check_output(["git", "diff", "HEAD", "--binary"], cwd=ROOT))
    print(json.dumps({"output": str(OUT), "source": {k:v for k,v in stats.items() if k != "geometry"}, "documents": summaries}, ensure_ascii=False))


if __name__ == "__main__":
    main()
