#!/usr/bin/env python3
"""提取指定章节的文本到 /tmp/ch<N>.txt，供写总结时阅读。

用法:
    python3 extract_chapter.py <章节号> [结束页]

行为:
  1. 在 PDF 中扫描含 "第X章" 的标题页，确定起始页（1-based）。
  2. 未传结束页 → 自动扫描到下一章标题的前一页；传了则按 1-based 含该页。
  3. 每页文本带 "=== p<n> ===" 页码标记，写入 /tmp/ch<N>.txt。

依赖: pip install pypdf   本脚本只读，不修改项目文件。
"""
import re
import sys
import unicodedata
from pathlib import Path

try:
    from pypdf import PdfReader
except ImportError:
    print("缺少 pypdf，请先 pip install pypdf", file=sys.stderr)
    sys.exit(1)

CN_NUM = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
          "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def cn_to_int(s: str) -> int:
    s = s.strip()
    if s.isdigit():
        return int(s)
    if s == "十":
        return 10
    if s.startswith("十"):
        return 10 + CN_NUM.get(s[1:], 0)
    if "十" in s:
        a, b = s.split("十", 1)
        return CN_NUM.get(a, 1) * 10 + (CN_NUM.get(b, 0) if b else 0)
    return CN_NUM.get(s, -1)


def chapter_at(text: str):
    # PDF 里的数字常是康熙部首（如 ⼗=U+2F17），NFKC 归一化回普通汉字
    head = " ".join(unicodedata.normalize("NFKC", text or "").split())[:80]
    m = re.search(r"第\s*([零一二两三四五六七八九十百\d]+)\s*章", head)
    return cn_to_int(m.group(1)) if m else -1


def main():
    if len(sys.argv) < 2:
        print("用法: python3 extract_chapter.py <章节号> [结束页(1-based 含)]", file=sys.stderr)
        sys.exit(1)

    target = int(sys.argv[1])
    pdf_path = Path(__file__).resolve().parents[4] / "Hello-Agents-V1.0.3-20260717.pdf"
    if not pdf_path.exists():
        pdf_path = Path.cwd() / "Hello-Agents-V1.0.3-20260717.pdf"

    reader = PdfReader(str(pdf_path))
    total = len(reader.pages)
    print(f"PDF 共 {total} 页", file=sys.stderr)

    start_idx = -1
    for i, page in enumerate(reader.pages):
        if chapter_at(page.extract_text()) == target:
            start_idx = i
            break
    if start_idx == -1:
        print(f"未找到第 {target} 章起始页", file=sys.stderr)
        sys.exit(1)

    if len(sys.argv) >= 3:
        end_idx = int(sys.argv[2])  # 1-based 含 -> 作为 exclusive 上界正好
    else:
        end_idx = total
        for i in range(start_idx + 1, total):
            if chapter_at(reader.pages[i].extract_text()) == target + 1:
                end_idx = i
                break

    parts = []
    for i in range(start_idx, end_idx):
        parts.append(f"\n=== p{i + 1} ===\n{reader.pages[i].extract_text() or ''}")

    out = Path(f"/tmp/ch{target}.txt")
    out.write_text("\n".join(parts), encoding="utf-8")
    print(f"OK -> {out}（p{start_idx + 1} ~ p{end_idx}，{len(parts)} 页，{len(out.read_text(encoding='utf-8'))} 字）", file=sys.stderr)


if __name__ == "__main__":
    main()
