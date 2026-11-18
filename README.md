# CTC 受控技术中文

给接口文档、操作手册和运维规程用的中文写作规范。让 Agent 按规范改写，用 Python 检查器定位可判定的问题，再用原文和业务依据核对技术含义。

[English](README.en.md) · [中文规范](docs/CTC-Specification.md) · [Agent skill](skills/ctc-write/SKILL.md) · [正反例](examples/README.md) · [验证](docs/Validation.md)

## 一对括号，两个授权规则

工单必须有效。满足「值班员有权」或「审计员已批准」中的至少一项即可导出。

| 文档中的条件 | 工单无效，值班员有权，审计员未批准 |
| --- | --- |
| 值班员有权或审计员批准且工单有效 | 组合范围不明确 |
| （值班员有权或审计员批准）且工单有效 | 禁止导出 |
| 值班员有权或（审计员批准且工单有效） | 允许导出 |

检查器会提示第一句补足分组。后两句都能通过形式检查，含义不同。用原始业务规则或工程测试确定正确的分组。

## 快速开始

需要 Python 3.9 或更高版本。检查 Markdown 或 TXT 时只用 Python 标准库。输入采用 UTF-8。

```sh
git clone https://github.com/thuswleo22/controlled-technical-chinese.git
cd controlled-technical-chinese
python3 src/ctc_linter.py examples/before.md
python3 src/ctc_linter.py examples/after.md --json
```

第一条检查预期报告三项，涉及条件分组、执行者和回指对象。第二条预期输出 `[]`。有诊断时退出码为 `1`，无诊断为 `0`，输入错误为 `2`。以 `--json` 获取行号、规则编号、说明和改写建议。

## 为什么需要 CTC

技术文档要让读者执行同一条指令。中文允许承前省略主语，同一个词也能随语境承担不同的语法功能。这些写法在解释性文本中常常清楚，在权限条件、交接步骤和上下界约束中却可能留出不同解释。Agent 能让文档更流畅，也可能补出原文没有提供的责任人或悄悄改变条件。

CTC 借鉴 ASD-STE100 的受控写作思路，为中文规定可核查的写法。规则按词汇、角色与指代、逻辑、指令强度、数量、操作呈现六类组织。每个编号都有正反例和可执行检查。166 个经编辑复审的词典义项提供术语参考，按义项和上下文使用。检查器只执行规则明示的检测范围。[设计取舍](docs/Design.md)

## 让 Agent 改写自己的文档

把原稿、[CTC 规范](docs/CTC-Specification.md) 和 [ctc-write skill](skills/ctc-write/SKILL.md) 交给 Agent。可以直接用这段提示词。

> 按 CTC 规范改写这份文档并另存。保留原意和 Markdown 结构。运行检查器，核实诊断、修改并复跑。对照原文核对角色、动作、对象、条件、指令强度、数值和时序。列出需要业务负责人确认的内容。交付改稿和最终诊断。

```sh
python3 src/ctc_linter.py "文档.ctc.md" --json
```

## 复跑与贡献

```sh
python3 -m unittest discover -s tests -q
python3 experiments/reproduce_public.py
```

[验证说明](docs/Validation.md) 列出每项证据的范围。[来源说明](docs/Sources.md) 提供研究语料的固定版本和许可证。欢迎用一对最小正反例报告误报、漏报或语义偏移，并说明原句允许哪些解释。[贡献指南](CONTRIBUTING.md)

项目原创内容采用 [MIT 许可证](LICENSE)。
