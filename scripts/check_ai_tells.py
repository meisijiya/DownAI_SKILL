#!/usr/bin/env python3
"""
check_ai_tells.py — 中文论文 AI 痕迹检测工具

检测 8 类典型中文 AI 写作痕迹，输出问题位置与建议。

用法：
    python check_ai_tells.py --file <path>
    python check_ai_tells.py --text "待检测文本"
    echo "文本" | python check_ai_tells.py

依赖：仅 Python 标准库（无第三方依赖）。
"""
import argparse
import json
import re
import sys
from typing import List, Dict, Any


# 8 类问题的检测器定义
# 每条规则：(规则ID, 描述, 正则模式, 严重级别, 建议)
RULES = [
    (
        "le_overuse",
        "「了」滥用（如「研究了」「分析了」「探讨了」「发现了」「得到了」）",
        re.compile(r"(研究|分析|探讨|发现|得到|取得|实现|提出|构建|建立|设计|验证|证明|表明|展示|呈现|揭示|提出|完成|开展|进行|推动|促进|带动|提升|降低|减少|增加|扩大|缩小|完善|优化|解决|突破|创新|改进|改善|应用|采用|使用|利用|结合|整合|融合|联动|协同|推进|引导|实现)(了)"),
        "high",
        "删除「了」改为「a研究b」结构；或改用「对……进行」「展开」「得以」等不同句式。",
    ),
    (
        "de_x_yu_z",
        "「X的Y与Z」对偶结构（高度 AI 痕迹）",
        re.compile(r"[\u4e00-\u9fa5]{1,8}的[\u4e00-\u9fa5]{1,8}与[\u4e00-\u9fa5]{1,8}(?:的[\u4e00-\u9fa5]{1,8})?"),
        "high",
        "拆成两句，或删除其中一个修饰词，或改用「及」「以及」「和」。",
    ),
    (
        "de_stacking",
        "前缀形容词堆砌（单句 3+ 个「的」结构）",
        None,  # 特殊处理：按句统计
        "medium",
        "删除冗余的「的」，保留必要定语。",
    ),
    (
        "zai_xxx_zhong",
        "「在xxx中」重复使用",
        None,  # 特殊处理：按段统计
        "medium",
        "改为「就……而言」「关于」「……方面」，或调整语序到句末。",
    ),
    (
        "long_sentence",
        "超长句（>40 字）",
        None,  # 特殊处理：按句字数
        "medium",
        "拆句或精简修饰。",
    ),
    (
        "parallel_structure",
        "句式雷同（连续多句「动词了」开头）",
        None,  # 特殊处理：句首模式
        "high",
        "打乱顺序，变换动词，合并或拆分句子。",
    ),
    (
        "ai_cliche",
        "AI 套话（综上所述/值得注意的是/不难发现/首先...其次...最后）",
        re.compile(r"(综上所述|值得注意的是|不难发现|毋庸置疑|显而易见|不可否认|不言而喻|首先.{0,5}，其次.{0,5}，最后|总而言之|总体而言|在当今社会|在当前背景下|基于此|据此|由此可见)"),
        "high",
        "删除套话直接进入实质论述；或用具体数据/事实替代。",
    ),
    (
        "colloquial",
        "口语化表达（其实/就是/挺/蛮/差不多/可能/应该）",
        re.compile(r"(其实|就是|挺|蛮|蛮好|差不多|可能也|应该是|一般来说|一般来说)"),
        "low",
        "改用正式书面语：可删除，或换用「实际上」「即为」「较为」「大致」等。",
    ),
]


def split_sentences(text: str) -> List[str]:
    """按中文标点切句。"""
    # 在 。！？；\n 后切分，保留标点
    parts = re.split(r"([。！？；\n]+)", text)
    sentences = []
    buf = ""
    for p in parts:
        if not p:
            continue
        buf += p
        if re.match(r"[。！？；\n]+", p):
            sentences.append(buf.strip())
            buf = ""
    if buf.strip():
        sentences.append(buf.strip())
    return [s for s in sentences if s]


def split_paragraphs(text: str) -> List[str]:
    """按段落切分。"""
    paras = re.split(r"\n\s*\n", text)
    return [p.strip() for p in paras if p.strip()]


def check_le_overuse(text: str) -> List[Dict[str, Any]]:
    issues = []
    rule = RULES[0]
    for m in rule[2].finditer(text):
        issues.append({
            "rule_id": rule[0],
            "rule_desc": rule[1],
            "severity": rule[3],
            "suggestion": rule[4],
            "match": m.group(0),
            "offset": m.start(),
        })
    return issues


def check_de_x_yu_z(text: str) -> List[Dict[str, Any]]:
    issues = []
    rule = RULES[1]
    matches = list(rule[2].finditer(text))
    # 阈值：单段出现 2+ 次视为高风险
    if len(matches) >= 2:
        for m in matches:
            issues.append({
                "rule_id": rule[0],
                "rule_desc": rule[1] + f"（本段出现 {len(matches)} 次）",
                "severity": rule[3],
                "suggestion": rule[4],
                "match": m.group(0),
                "offset": m.start(),
            })
    elif len(matches) == 1:
        # 单次出现仅做提示
        m = matches[0]
        issues.append({
            "rule_id": rule[0],
            "rule_desc": rule[1] + "（单次出现，需留意）",
            "severity": "low",
            "suggestion": rule[4],
            "match": m.group(0),
            "offset": m.start(),
        })
    return issues


def check_de_stacking(text: str) -> List[Dict[str, Any]]:
    issues = []
    rule = RULES[2]
    sentences = split_sentences(text)
    for sent in sentences:
        # 统计「的」数量（不算句尾）
        de_count = sent.count("的")
        if de_count >= 3:
            issues.append({
                "rule_id": rule[0],
                "rule_desc": rule[1] + f"（本句 {de_count} 个「的」）",
                "severity": rule[3] if de_count >= 4 else "low",
                "suggestion": rule[4],
                "match": sent,
                "offset": 0,
            })
    return issues


def check_zai_zhong(text: str) -> List[Dict[str, Any]]:
    issues = []
    rule = RULES[3]
    pattern = re.compile(r"在[\u4e00-\u9fa5]{1,15}中[，,。；]?")
    paragraphs = split_paragraphs(text)
    offset = 0
    for para in paragraphs:
        matches = list(pattern.finditer(para))
        if len(matches) >= 2:
            for m in matches:
                issues.append({
                    "rule_id": rule[0],
                    "rule_desc": rule[1] + f"（本段 {len(matches)} 次）",
                    "severity": rule[3],
                    "suggestion": rule[4],
                    "match": m.group(0),
                    "offset": offset + m.start(),
                })
        offset += len(para) + 2
    return issues


def check_long_sentence(text: str) -> List[Dict[str, Any]]:
    issues = []
    rule = RULES[4]
    sentences = split_sentences(text)
    for sent in sentences:
        # 去掉标点再算字数
        clean = re.sub(r"[，。！？；：、\s]", "", sent)
        n = len(clean)
        if n > 40:
            issues.append({
                "rule_id": rule[0],
                "rule_desc": rule[1] + f"（{n} 字）",
                "severity": "high",
                "suggestion": rule[4],
                "match": sent,
                "offset": 0,
            })
        elif n > 25:
            issues.append({
                "rule_id": rule[0],
                "rule_desc": rule[1] + f"（{n} 字，建议检查）",
                "severity": "low",
                "suggestion": rule[4],
                "match": sent,
                "offset": 0,
            })
    return issues


def check_parallel(text: str) -> List[Dict[str, Any]]:
    issues = []
    rule = RULES[5]
    sentences = split_sentences(text)
    # 检测连续多句以「首先/其次/再次/最后/第一/第二」开头
    seq_markers = re.compile(r"^(首先|其次|再次|最后|第一|第二|第三|第四|一方面|另一方面|与此同时|此外|不仅.{0,3}而且)")
    count = 0
    for sent in sentences:
        if seq_markers.match(sent):
            count += 1
        else:
            if count >= 3:
                issues.append({
                    "rule_id": rule[0],
                    "rule_desc": rule[1] + f"（连续 {count} 句排比）",
                    "severity": rule[3],
                    "suggestion": rule[4],
                    "match": "(见原文)",
                    "offset": 0,
                })
            count = 0
    if count >= 3:
        issues.append({
            "rule_id": rule[0],
            "rule_desc": rule[1] + f"（连续 {count} 句排比）",
            "severity": rule[3],
            "suggestion": rule[4],
            "match": "(见原文)",
            "offset": 0,
        })
    return issues


def check_ai_cliche(text: str) -> List[Dict[str, Any]]:
    issues = []
    rule = RULES[6]
    for m in rule[2].finditer(text):
        issues.append({
            "rule_id": rule[0],
            "rule_desc": rule[1],
            "severity": rule[3],
            "suggestion": rule[4],
            "match": m.group(0),
            "offset": m.start(),
        })
    return issues


def check_colloquial(text: str) -> List[Dict[str, Any]]:
    issues = []
    rule = RULES[7]
    for m in rule[2].finditer(text):
        issues.append({
            "rule_id": rule[0],
            "rule_desc": rule[1],
            "severity": rule[3],
            "suggestion": rule[4],
            "match": m.group(0),
            "offset": m.start(),
        })
    return issues


CHECKERS = [
    check_le_overuse,
    check_de_x_yu_z,
    check_de_stacking,
    check_zai_zhong,
    check_long_sentence,
    check_parallel,
    check_ai_cliche,
    check_colloquial,
]


def check_text(text: str) -> Dict[str, Any]:
    """对输入文本执行所有检测器，返回结构化结果。"""
    all_issues = []
    for checker in CHECKERS:
        all_issues.extend(checker(text))

    # 统计
    by_severity = {"high": 0, "medium": 0, "low": 0}
    by_rule = {}
    for issue in all_issues:
        by_severity[issue["severity"]] = by_severity.get(issue["severity"], 0) + 1
        by_rule[issue["rule_id"]] = by_rule.get(issue["rule_id"], 0) + 1

    # AI 浓度估算（粗略）：每 100 字的 high 严重度问题数
    text_len = max(len(re.sub(r"\s", "", text)), 1)
    high_per_100 = round(by_severity["high"] * 100 / text_len, 2)

    return {
        "text_length": text_len,
        "total_issues": len(all_issues),
        "by_severity": by_severity,
        "by_rule": by_rule,
        "high_per_100_chars": high_per_100,
        "issues": all_issues,
    }


def format_human(result: Dict[str, Any]) -> str:
    """格式化人类可读输出。"""
    lines = []
    lines.append("=" * 60)
    lines.append("中文论文 AI 痕迹检测报告")
    lines.append("=" * 60)
    lines.append(f"文本长度: {result['text_length']} 字")
    lines.append(f"问题总数: {result['total_issues']}")
    lines.append(f"  高风险: {result['by_severity'].get('high', 0)}")
    lines.append(f"  中风险: {result['by_severity'].get('medium', 0)}")
    lines.append(f"  低风险: {result['by_severity'].get('low', 0)}")
    lines.append(f"AI 浓度估算: {result['high_per_100_chars']} (高风险 / 100字)")
    lines.append("")

    if result["issues"]:
        lines.append("-" * 60)
        lines.append("详细问题:")
        lines.append("-" * 60)
        for i, issue in enumerate(result["issues"], 1):
            sev_mark = {"high": "[高]", "medium": "[中]", "low": "[低]"}.get(issue["severity"], "[?]")
            match_preview = issue["match"][:50] + ("..." if len(issue["match"]) > 50 else "")
            lines.append(f"{i}. {sev_mark} {issue['rule_desc']}")
            lines.append(f"   匹配: {match_preview}")
            lines.append(f"   建议: {issue['suggestion']}")
            lines.append("")
    else:
        lines.append("✓ 未发现明显 AI 痕迹。")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="中文论文 AI 痕迹检测工具")
    parser.add_argument("--file", help="要检测的文件路径")
    parser.add_argument("--text", help="要检测的文本字符串")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    parser.add_argument("--quiet", action="store_true", help="只输出摘要")
    args = parser.parse_args()

    if args.file:
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                text = f.read()
        except Exception as e:
            print(f"读取文件失败: {e}", file=sys.stderr)
            sys.exit(1)
    elif args.text:
        text = args.text
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    else:
        parser.print_help()
        sys.exit(1)

    result = check_text(text)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.quiet:
        print(json.dumps({
            "total": result["total_issues"],
            "high": result["by_severity"].get("high", 0),
            "medium": result["by_severity"].get("medium", 0),
            "low": result["by_severity"].get("low", 0),
            "density": result["high_per_100_chars"],
        }, ensure_ascii=False))
    else:
        print(format_human(result))

    # 退出码：发现 high 严重度问题时返回 1
    sys.exit(1 if result["by_severity"].get("high", 0) > 0 else 0)


if __name__ == "__main__":
    main()
