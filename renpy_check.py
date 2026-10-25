#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
renpy_check.py —— Ren'Py 剧本分支自检器

检查 .rpy 文件里 label（定义）与 jump / call（引用）是否对得上。

能查出四类问题：
  断链   jump/call 指向了一个不存在的 label
  孤立   定义了 label，但没有任何 jump/call 指向它（start 等入口除外）
  重复   同一个 label 被定义了两次以上（Ren'Py 会直接报错）
  动态   jump/call expression 这种运行时才决定目标的，静态查不了，只计数

用法：
  python renpy_check.py <项目目录或单个 .rpy>
  python renpy_check.py D:\\daibi --json
  python renpy_check.py D:\\daibi --html report.html
  python renpy_check.py D:\\daibi --ignore s5,credits1

退出码：
  0  干净（没有断链、没有重复定义）
  1  有问题（断链或重复定义）
  2  参数错误、路径不存在、找不到 .rpy
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

# Ren'Py 的剧本标签必须顶格写在文件最外层（缩进 0）。
# screen 语言里也有 label 关键字（如 label _("文本")、label _(message):），
# 它们是缩进的 displayable，不是剧本标签，所以这里不允前导空白。
LABEL_RE = re.compile(
    r'^label\s+([A-Za-z_]\w*)\s*(?:\([^)]*\))?\s*:', re.M)

# jump / call 后面跟标签名；排除 call screen xxx 和 jump expression ...
JUMP_RE = re.compile(
    r'^\s*(jump|call)\s+(?!screen\b|expression\b)([A-Za-z_]\w*)', re.M)

# 运行时才决定目标的跳转，只能计数，无法静态检查
DYNAMIC_RE = re.compile(r'^\s*(?:jump|call)\s+expression\b', re.M)

# Ren'Py 自己会调用的入口标签，不该被报成孤立
ENTRY_LABELS = {
    'start', 'splashscreen', 'before_main_menu', 'main_menu',
    'after_load', 'after_warp', 'quit', 'hide_windows',
}

# 这些目录里的 .rpy 不参与检查（翻译文件、缓存）
SKIP_DIRS = {'tl', 'cache', 'saves'}


def strip_comments(text):
    """去掉整行注释和行尾注释，字符串内的 # 保留。"""
    out = []
    for line in text.splitlines():
        in_str = ''
        cut = len(line)
        i = 0
        while i < len(line):
            ch = line[i]
            if in_str:
                if ch == '\\':
                    i += 2
                    continue
                if ch == in_str:
                    in_str = ''
            else:
                if ch in '"\'':
                    in_str = ch
                elif ch == '#':
                    cut = i
                    break
            i += 1
        out.append(line[:cut])
    return '\n'.join(out)


def find_rpy(target):
    """接受目录或单文件，返回要检查的 .rpy 列表。"""
    if target.is_file():
        return [target] if target.suffix.lower() == '.rpy' else []
    files = []
    for p in target.rglob('*.rpy'):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        files.append(p)
    return sorted(files)


def analyze(files):
    defined = {}   # 标签名 -> [文件:行号]
    used = {}      # 标签名 -> [(文件, 行号, jump/call)]
    dynamic = 0

    for f in files:
        raw = f.read_text(encoding='utf-8', errors='replace')
        text = strip_comments(raw)

        for m in LABEL_RE.finditer(text):
            line = text[:m.start()].count('\n') + 1
            defined.setdefault(m.group(1), []).append(f'{f.name}:{line}')

        for m in JUMP_RE.finditer(text):
            line = text[:m.start()].count('\n') + 1
            used.setdefault(m.group(2), []).append((f.name, line, m.group(1)))

        dynamic += len(DYNAMIC_RE.findall(text))

    return defined, used, dynamic


CSS = """
:root{
  --bg:#f7f6f3; --panel:#ffffff; --ink:#1c1b19; --ink2:#5c5852; --ink3:#8d8880;
  --line:#e6e2da; --accent:#b1462c; --good:#3d7a4e;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font-family:"PingFang SC","Microsoft YaHei","Hiragino Sans GB",system-ui,sans-serif;
  font-size:15px;line-height:1.7;padding:40px 20px;
  -webkit-font-smoothing:antialiased}
.wrap{max-width:900px;margin:0 auto}
h1{font-size:26px;margin:0 0 6px;letter-spacing:-.01em}
.sub{color:var(--ink3);font-size:13px;margin-bottom:24px}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:24px}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.stat b{display:block;font-size:26px;line-height:1.25;font-variant-numeric:tabular-nums}
.stat span{font-size:12px;color:var(--ink3)}
.verdict{border-radius:12px;padding:14px 18px;margin-bottom:24px;font-size:14px}
.ok{background:#eaf3ec;border:1px solid #cfe4d5;color:var(--good)}
.bad{background:#f6e9e4;border:1px solid #edd6cd;color:var(--accent)}
.sec{background:var(--panel);border:1px solid var(--line);border-radius:12px;
  padding:18px 20px;margin-bottom:16px}
.sec h2{font-size:15px;margin:0 0 12px;letter-spacing:.02em}
.sec h2 .n{color:var(--ink3);font-weight:400;font-size:13px}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line)}
th{color:var(--ink3);font-weight:500;font-size:12px}
tr:last-child td{border-bottom:0}
.mono{font-family:ui-monospace,Consolas,"Courier New",monospace;font-size:12.5px}
.empty{color:var(--ink3);font-size:13px}
footer{color:var(--ink3);font-size:12px;margin-top:28px;text-align:center}
@media (max-width:640px){
  .stats{grid-template-columns:repeat(2,1fr)}
}
"""


def esc(s):
    return (str(s).replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;').replace('"', '&quot;'))


def render_html(rep, defined, used, out_path):
    """把检查结果写成一份独立的 HTML 报告（内联样式，无外部依赖）。"""
    stamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    verdict_cls = 'ok' if rep['ok'] else 'bad'
    if rep['ok'] and not rep['orphan']:
        verdict = '干净，没有发现问题。'
    elif rep['ok']:
        verdict = '没有断链和重复定义；孤立标签未必是错，人工看一眼。'
    else:
        verdict = '有问题：先修断链和重复定义。'

    def sec(title, count, body):
        return (f'<section class="sec"><h2>{esc(title)} '
                f'<span class="n">({count})</span></h2>{body}</section>')

    # 断链
    if rep['broken']:
        rows = ''.join(
            f'<tr><td class="mono">{esc(k)}</td>'
            f'<td class="mono">{esc(", ".join(v))}</td></tr>'
            for k, v in rep['broken'].items())
        broken = ('<table><tr><th>目标标签</th><th>从哪跳过来</th></tr>'
                  + rows + '</table>')
    else:
        broken = '<div class="empty">没有断链。</div>'

    # 重复定义
    if rep['duplicate']:
        rows = ''.join(
            f'<tr><td class="mono">{esc(k)}</td>'
            f'<td class="mono">{esc(", ".join(v))}</td></tr>'
            for k, v in rep['duplicate'].items())
        dupe = ('<table><tr><th>标签</th><th>定义位置</th></tr>'
                + rows + '</table>')
    else:
        dupe = '<div class="empty">没有重复定义。</div>'

    # 孤立标签
    if rep['orphan']:
        rows = ''.join(
            f'<tr><td class="mono">{esc(k)}</td>'
            f'<td class="mono">{esc(v[0])}</td></tr>'
            for k, v in rep['orphan'].items())
        orphan = ('<table><tr><th>标签</th><th>定义位置</th></tr>'
                  + rows + '</table>')
    else:
        orphan = '<div class="empty">没有孤立标签。</div>'

    # 全部标签
    rows = ''.join(
        f'<tr><td class="mono">{esc(name)}</td>'
        f'<td class="mono">{esc(defined[name][0])}</td>'
        f'<td>{len(used.get(name, []))}</td></tr>'
        for name in sorted(defined))
    all_labels = ('<table><tr><th>标签</th><th>定义位置</th><th>被引用次数</th></tr>'
                  + rows + '</table>')

    files_list = '、'.join(esc(Path(f).name) for f in rep['files'])

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ren'Py 分支自检报告</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
  <h1>Ren'Py 分支自检报告</h1>
  <div class="sub">扫描路径：{esc(rep['target'])} · 生成时间：{stamp}</div>

  <div class="stats">
    <div class="stat"><b>{len(rep['files'])}</b><span>文件</span></div>
    <div class="stat"><b>{rep['defined_count']}</b><span>标签定义</span></div>
    <div class="stat"><b>{rep['used_count']}</b><span>被引用目标</span></div>
    <div class="stat"><b>{rep['dynamic']}</b><span>动态跳转</span></div>
  </div>

  <div class="verdict {verdict_cls}">{verdict}</div>

  <div class="sub">文件：{files_list}</div>

  {sec('断链', len(rep['broken']), broken)}
  {sec('重复定义', len(rep['duplicate']), dupe)}
  {sec('孤立标签', len(rep['orphan']), orphan)}
  {sec('全部标签', len(defined), all_labels)}

  <footer>由 renpy-checker 生成 · 静态分析，动态跳转与 screen 内跳转不参与检查</footer>
</div>
</body>
</html>
"""

    out_path.write_text(html, encoding='utf-8')
    return out_path


def main():
    ap = argparse.ArgumentParser(
        description="Ren'Py 剧本分支自检器：查断链、孤立标签、重复定义")
    ap.add_argument('target', help="Ren'Py 项目目录，或单个 .rpy 文件")
    ap.add_argument('--json', action='store_true', help='输出 JSON')
    ap.add_argument('--ignore', default='',
                    help='忽略这些标签的孤立警告，逗号分隔')
    ap.add_argument('--html', nargs='?', const='renpy_check_report.html',
                    metavar='输出路径',
                    help='生成一份 HTML 报告（默认 renpy_check_report.html）')
    args = ap.parse_args()

    target = Path(args.target)
    if not target.exists():
        print(f'路径不存在：{target}', file=sys.stderr)
        return 2

    files = find_rpy(target)
    if not files:
        print(f'没找到 .rpy 文件：{target}', file=sys.stderr)
        return 2

    ignore = {x.strip() for x in args.ignore.split(',') if x.strip()}
    defined, used, dynamic = analyze(files)

    broken = sorted(set(used) - set(defined))
    orphan = sorted(set(defined) - set(used) - ENTRY_LABELS - ignore)
    dupes = sorted(k for k, v in defined.items() if len(v) > 1)

    report = {
        'target': str(target),
        'files': [str(f) for f in files],
        'defined_count': len(defined),
        'used_count': len(used),
        'dynamic': dynamic,
        'broken': {k: [f'{fn}:{ln}' for fn, ln, _ in used[k]] for k in broken},
        'orphan': {k: defined[k] for k in orphan},
        'duplicate': {k: defined[k] for k in dupes},
        'ok': not broken and not dupes,
    }

    if args.html:
        out = Path(args.html)
        render_html(report, defined, used, out)
        print(f'HTML 报告已生成：{out.resolve()}')

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report['ok'] else 1

    if args.html:
        return 0 if report['ok'] else 1

    print("=== Ren'Py 分支自检 ===")
    print(f'扫描路径 : {target}')
    print(f'文件数量 : {len(files)}')
    for f in files:
        print(f'           - {f.name}')
    print(f'标签定义 : {len(defined)}')
    print(f'跳转引用 : {len(used)} 个不同目标（另有 {dynamic} 处动态跳转，静态查不了）')
    print()

    if broken:
        print(f'[断链] {len(broken)} 个目标不存在：')
        for name in broken:
            for fn, ln, kind in used[name]:
                print(f'  {fn}:{ln}  {kind} {name}')
        print()

    if dupes:
        print(f'[重复] {len(dupes)} 个标签被定义了多次：')
        for name in dupes:
            print(f'  {name}  <- {", ".join(defined[name])}')
        print()

    if orphan:
        print(f'[孤立] {len(orphan)} 个标签没有任何跳转指向：')
        for name in orphan:
            print(f'  {name}  ({defined[name][0]})')
        print()

    if report['ok'] and not orphan:
        print('结论：干净，没有发现问题。')
    elif report['ok']:
        print('结论：没有断链和重复定义；孤立标签未必是错，人工看一眼。')
    else:
        print('结论：有问题，先修断链和重复定义。')

    return 0 if report['ok'] else 1


if __name__ == '__main__':
    if sys.platform == 'win32':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
        except Exception:
            pass
    sys.exit(main())
