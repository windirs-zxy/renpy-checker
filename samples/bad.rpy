# 故意写坏的测试样本，用来验证检查器能不能抓到问题。
# 预期结果：断链 nowhere，孤立 lonely。

label start:
    "开始"
    jump s1
    jump nowhere

label s1:
    "第一段"
    call s2

label s2:
    "第二段"
    return

label lonely:
    "没有任何 jump/call 指向这里"
