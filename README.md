# 论文降AI味 Skill 📝

> 中文论文 AI 痕迹检测与改写工具，让你的论文更像人类写的。

## 🚀 三步上手

1. 把要润色的段落保存为 `text.txt`
2. 检测 AI 痕迹：`python scripts/check_ai_tells.py --file text.txt`
3. 根据脚本输出的修正建议改写，再跑一次确认归零

详细规则与范文见 [SKILL.md](./SKILL.md)。

## 🎯 覆盖 8 类 AI 痕迹

| # | 类型 | 严重度 |
|:-:|------|:------:|
| 1 | 「了」滥用（研究了/分析了/...） | ⚠️ 高 |
| 2 | 「X 的 Y 与 Z」对偶结构 | 🚨 最高 |
| 3 | 前缀形容词堆砌 | ⚠️ 高 |
| 4 | 「在 xxx 中」重复 | 🔄 中 |
| 5 | 超长句与赘述 | 📏 中 |
| 6 | 句式雷同（对偶排比） | ⚡ 高 |
| 7 | AI 套话（综上所述/值得注意的是/...） | 🚨 最高 |
| 8 | 口语化与模糊表达 | ℹ️ 低 |

## 📂 文件结构

```
.
├── SKILL.md                       # 详细规则（模型加载时读取）
├── README.md                      # 本文件
└── scripts/
    └── check_ai_tells.py          # 自动化检测脚本
```

## 🔧 脚本用法

```bash
# 检测文件
python scripts/check_ai_tells.py --file paper.txt

# 检测字符串
python scripts/check_ai_tells.py --text "本文研究了..."

# JSON 输出
python scripts/check_ai_tells.py --file paper.txt --json

# 只看摘要
python scripts/check_ai_tells.py --file paper.txt --quiet
```

退出码：发现高风险问题时返回 1，可用于 CI/批量校验。

## ⚠️ 检测平台差异

| 平台 | 严格度 |
|------|:------:|
| 知网 AIGC | ⭐⭐⭐ |
| 维普 AIGC | ⭐⭐⭐⭐⭐ |
| PaperPass | ⭐⭐⭐⭐ |

> 🎓 句式变换 > 同义词替换。真正改变句式结构才是降 AI 率的根本方法。
