# renpy-checker

Ren'Py 剧本分支自检器：检查 `.rpy` 文件里的 label 定义和 jump / call 引用对不对得上。

```bash
python renpy_check.py D:\my-novel
```

一次性输出四类结果：**断链**、**孤立标签**、**重复定义**、**动态跳转计数**。

## 为什么做这个

Ren'Py 项目写到后期，脚本里几十个 label、上百个跳转。改一个段落名，可能弄断三条线，而 Ren'Py 要到**真正运行到那一步**才报错——有时候是玩家做了三个选项之后，才发现某个分支跳进了虚空。

这个工具把这件事提前到命令行：静态扫一遍，五秒钟告诉你哪条线断了、哪段没人用。

## 要求

- Python 3.7 以上（用了 `pathlib`、`f-string`、`sys.stdout.reconfigure`）
- 无第三方依赖，只用标准库

## 安装

```bash
git clone https://github.com/windirs-zxy/renpy-checker.git
cd renpy-checker
```

没有 `pip install`，没有虚拟环境，拷过去就能跑。

## 用法

```bash
# 检查整个项目目录（递归扫所有 .rpy）
python renpy_check.py D:\my-novel

# 只查一个文件
python renpy_check.py D:\my-novel\game\script.rpy

# 输出 JSON，方便接别的工具
python renpy_check.py D:\my-novel --json

# 生成 HTML 报告，双击就能在浏览器里看
python renpy_check.py D:\my-novel --html report.html

# 忽略某些标签的孤立警告（比如用菜单手动跳转的）
python renpy_check.py D:\my-novel --ignore credits1,s5
```

Windows 上也可以把项目文件夹**拖到 `check.bat` 上**松手，它会把路径当参数接住。

## 它怎么工作的

1. 递归找出目标路径下所有 `.rpy`（跳过 `tl/`、`cache/`、`saves/`）
2. 逐行扫描去掉注释——用引号状态机，字符串里的 `#` 不会被误删
3. 正则抓三类东西：`label 名字:`（必须顶格）、`jump 名字`、`call 名字`
4. 两个集合做差集：被引用减已定义 = 断链；已定义减被引用 = 孤立

就这么朴素。没有语法树，没有编译期分析，纯文本匹配。

## 它能查什么

- **断链**：`jump` / `call` 指向一个不存在的 label
- **孤立**：定义了 label，但没有任何 `jump` / `call` 指向它（`start` 等入口标签自动排除）
- **重复**：同一个 label 被定义了两次以上（Ren'Py 会直接报错）
- **动态跳转计数**：`jump expression ...` 这种，静态查不了，只报告数量

## 它查不了什么（重要，别指望它全能）

- `jump expression "s" + str(n)` —— 目标运行时才算出来
- screen 里的 `action Jump("xxx")` —— 那是函数调用，不是 jump 语句
- `python:` 块里的 `renpy.jump("xxx")` —— 同上
- 字符串里出现的 "jump"、"label" 字样，可能造成误判（概率低，但存在）
- 用变量拼接的 label 名，比如 `jump "s%s" % n`

**已知的简化**：去注释用的是"逐行扫描引号状态"的办法，遇到 Ren'Py 的三引号字符串（`"""..."""`）可能判断失准。真实项目里三引号很少直接跟 `jump`/`label` 混在一起，暂时够用。

## 目录结构

```
renpy-checker/
├── renpy_check.py     主程序，单文件，无依赖
├── check.bat          Windows 启动器，可把项目文件夹拖进来
├── samples/
│   └── bad.rpy        故意写坏的测试样本（断链 + 孤立）
├── LICENSE            MIT
└── README.md
```

## 输出示例

干净的项目：

```
=== Ren'Py 分支自检 ===
扫描路径 : D:\my-novel
文件数量 : 4
           - gui.rpy
           - options.rpy
           - screens.rpy
           - script.rpy
标签定义 : 9
跳转引用 : 7 个不同目标（另有 0 处动态跳转，静态查不了）

结论：干净，没有发现问题。
```

有问题的样本：

```
[断链] 1 个目标不存在：
  bad.rpy:7  jump nowhere

[孤立] 1 个标签没有任何跳转指向：
  lonely  (bad.rpy:17)
```

## 退出码

- `0` 干净（没有断链、没有重复定义）
- `1` 有问题（断链或重复定义）
- `2` 参数错误、路径不存在、找不到 `.rpy`

所以它能直接接进流水线：`python renpy_check.py . || exit 1`。

## 开发记录

- **2026-10-25 初版**：能查断链、孤立、重复、动态计数，带 `--json` 和 `--ignore`
- **同日修 bug**：`screens.rpy` 里 `label _(message):` 是 screen 语言的文字控件，被误当成剧本标签，报了个假孤立。修法是不允许 label 前有缩进——Ren'Py 的剧本标签必须顶格，screen 控件必然缩进，用缩进区分最稳
- **测试**：`samples/bad.rpy` 是故意写坏的样本，预期报 `nowhere` 断链和 `lonely` 孤立
- **同日加 `--html`**：生成独立 HTML 报告，内联样式、无外部依赖，配色与作品集一致，可直接挂到网页上

## License

MIT，见 [LICENSE](LICENSE)。
