"""Check source selection and PDF geometry, then render every page for review."""
from __future__ import annotations
import argparse
import hashlib
import re
import tomllib
import json
from pathlib import Path
import subprocess
from zipfile import ZipFile, ZIP_DEFLATED

import pypdfium2 as pdfium
from pypdf import PdfReader
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/copyright_application"
QA = ROOT / "artifacts/copyright_application_qa"
QA.mkdir(exist_ok=True)

PDF_NAMES = {"01_登记填报信息草稿.pdf", "02_合作开发协议待填写.pdf", "03_用户操作说明书.pdf", "04_源程序鉴别材料.pdf"}
ARCHIVE = ROOT / "artifacts/软件著作权申请材料_草稿.zip"
HASH_FILE = OUT / "核验记录/文件哈希.json"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compact(text):
    return re.sub(r"\s+", "", text)


def body_text(page):
    parts = []
    def visit(text, cm, tm, font, size):
        if 45 < tm[5] < 795:
            parts.append(text)
    page.extract_text(visitor_text=visit)
    return "".join(parts)


def verify_snapshot(zip_path, hashes):
    with ZipFile(zip_path) as z:
        assert len(z.namelist()) == len(set(z.namelist())), "duplicate archive members"
        assert set(z.namelist()) == set(hashes), "snapshot file set mismatch"
        for rel, expected_hash in hashes.items():
            assert digest(ROOT / rel) == expected_hash, f"changed input: {rel}"
            assert hashlib.sha256(z.read(rel)).hexdigest() == expected_hash, rel


def packet_hashes():
    return {p.relative_to(OUT).as_posix(): digest(p) for p in sorted(OUT.rglob("*"))
            if p.is_file() and p != HASH_FILE}


def verify_archive():
    expected = json.loads(HASH_FILE.read_text(encoding="utf-8"))
    assert expected == packet_hashes(), "packet files changed; rebuild after verification"
    with ZipFile(ARCHIVE) as z:
        names = set(expected) | {HASH_FILE.relative_to(OUT).as_posix()}
        assert set(z.namelist()) == names and len(z.namelist()) == len(names), "ZIP membership differs"
        for name in names:
            assert z.read(name) == (OUT / name).read_bytes(), f"ZIP differs: {name}"
    receipt = ARCHIVE.with_suffix(".zip.sha256").read_text(encoding="utf-8").split()[0]
    assert receipt == digest(ARCHIVE), "ZIP hash differs"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-zip", action="store_true", help="After checks pass, refresh packet hashes and the distributable ZIP")
    parser.add_argument("--no-render", action="store_true", help="Check text, geometry, snapshots and ZIP without rerendering")
    args = parser.parse_args()
    evidence = OUT / "核验记录"
    meta = json.loads((evidence / "生成与排版记录.json").read_text(encoding="utf-8"))
    manifests = json.loads((evidence / "源文件清单.json").read_text(encoding="utf-8"))
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert meta["version"] == "V" + project["version"]
    assert re.search(r'__version__ = "' + re.escape(project["version"]) + '"', (ROOT / "src/crpa_workflow/__init__.py").read_text(encoding="utf-8"))
    assert {p.name for p in OUT.glob("*.pdf")} == PDF_NAMES, "required PDF set is incomplete or contains extras"
    expected_sources = {"install.sh"} | {p.relative_to(ROOT).as_posix() for p in (ROOT / "src/crpa_workflow").rglob("*") if p.is_file() and p.suffix in (".py", ".sh", ".conf")}
    assert {m["path"] for m in manifests} == expected_sources
    verify_snapshot(evidence / "源文件快照.zip", {m["path"]: m["sha256_bytes"] for m in manifests})
    verify_snapshot(evidence / "生成输入快照.zip", json.loads((evidence / "生成输入哈希.json").read_text(encoding="utf-8")))
    for m in manifests:
        assert hashlib.sha256((ROOT / m["path"]).read_bytes()).hexdigest() == m["sha256_bytes"]
    records = [line for m in manifests for line in (ROOT / m["path"]).read_text(encoding="utf-8").splitlines() if line.strip()]
    n = meta["source"]["full_pages"]
    assert n == max(1, len(records) // 50)
    selected = list(range(1, n+1)) if n <= 60 else list(range(1,31)) + list(range(n-29,n+1))
    assert meta["source"]["selected_pages"] == selected
    base, extra = divmod(len(records), n)
    full, start = [], 0
    for i in range(n):
        count = base + (i < extra)
        full.append(records[start:start + count]); start += count
    expect = "\n\f\n".join("\n".join(full[i-1]) for i in meta["source"]["selected_pages"])
    assert expect == (evidence / "交存源程序文本.txt").read_text(encoding="utf-8")
    assert full[-1][-1] == records[-1]
    assert all(len(page) >= 50 for page in full)
    source_pages = expect.split("\n\f\n")
    documents = {item["file"]: item for item in meta["documents"]}
    summary = []
    for path in sorted(OUT.glob("*.pdf")):
        reader = PdfReader(path)
        if path.name.startswith("04_"):
            assert len(reader.pages) == len(selected)
            for page, expected in zip(reader.pages, source_pages):
                assert compact(body_text(page)) == compact(expected), "source PDF body differs from source selection"
        else:
            assert len(reader.pages) == documents[path.name]["pages"]
            from build_registration_materials import blocks_from_md
            blocks = blocks_from_md(path.with_suffix(".md").read_text(encoding="utf-8"))
            expected = "".join(line for block in blocks for line in block["lines"])
            assert compact("".join(body_text(page) for page in reader.pages)) == compact(expected), f"document PDF body differs: {path.name}"
        render = pdfium.PdfDocument(path)
        images, page_info = [], []
        directory = QA / path.stem
        directory.mkdir(exist_ok=True)
        for index, page in enumerate(render):
            text_page = page.get_textpage()
            rects = []
            for k in range(text_page.count_chars()):
                box = text_page.get_charbox(k)
                if box[2] > box[0] and box[3] > box[1]:
                    rects.append(box)
            assert rects
            assert min(b[0] for b in rects) >= 40, (path.name, index, "left overflow")
            assert max(b[2] for b in rects) <= 555, (path.name, index, "right overflow")
            assert min(b[1] for b in rects) >= 22, (path.name, index, "bottom overflow")
            assert max(b[3] for b in rects) <= 825, (path.name, index, "top overflow")
            extracted = reader.pages[index].extract_text()
            assert meta["software"] in extracted and meta["version"] in extracted
            assert "\ufffd" not in extracted
            if not args.no_render:
                bitmap = page.render(scale=1.5)
                image = bitmap.to_pil().convert("RGB")
                image.save(directory / f"page-{index+1:02d}.png")
                images.append(image)
            page_info.append({"page":index+1,"characters":len(extracted),"bounds":[min(b[0] for b in rects),min(b[1] for b in rects),max(b[2] for b in rects),max(b[3] for b in rects)]})
        # Every page is included in numbered review sheets.
        for batch in range(0, len(images), 6):
            sheet = Image.new("RGB", (1800, 3*1300), "#dddddd")
            d = ImageDraw.Draw(sheet)
            for j, image in enumerate(images[batch:batch+6]):
                image.thumbnail((890, 1260))
                x,y = (j%2)*900, (j//2)*1300
                d.text((x+8,y+7), f"Page {batch+j+1}", fill="black")
                sheet.paste(image,(x,y+30))
            sheet.save(QA / f"{path.stem[:2]}-review-{batch//6+1:02d}.jpg", quality=90)
        summary.append({"file":path.name,"pages":len(reader.pages),"checks":"page bounds, version headers, Unicode text, all pages rendered", "page_info":page_info})
    if args.build_zip:
        (evidence / "自动核验结果.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
        HASH_FILE.write_text(json.dumps(packet_hashes(), ensure_ascii=False, indent=2), encoding="utf-8")
        with ZipFile(ARCHIVE, "w", ZIP_DEFLATED) as z:
            for path in sorted(OUT.rglob("*")):
                if path.is_file():
                    z.write(path, path.relative_to(OUT).as_posix())
        ARCHIVE.with_suffix(".zip.sha256").write_text(digest(ARCHIVE) + "  " + ARCHIVE.name + "\n", encoding="utf-8")
    verify_archive()
    print(json.dumps([{k:v for k,v in s.items() if k != "page_info"} for s in summary],ensure_ascii=False))

if __name__ == "__main__":
    main()
