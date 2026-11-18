# CTC 受控技术中文

给接口文档、操作手册和运维规程用的中文写作规范。让 Agent 按规范改写，用 Python 检查器定位可判定的问题，再用原文和业务依据核对技术含义。

[English](README.en.md) · [中文规范](docs/CTC-Specification.md) · [Agent skill](skills/ctc-write/SKILL.md) · [正反例](examples/README.md) · [验证](docs/Validation.md)

## 工单过期了，还能导出故障日志吗？

假设公司规定，导出故障日志必须同时满足两个条件。

1. 工单有效。
2. 值班员有导出权限，或审计员已批准本次导出。

现在，值班员有导出权限，但工单已过期，审计员也没有批准。按公司规定，值班员不能导出。可是操作手册上只写了这一句。

> 如果值班员有权导出日志或审计员批准且工单有效，导出故障日志。

读者可能把「工单有效」理解为只在审计员批准时才要求。CTC 检查器会提示这句话需要明确分组。

- **（有权限或已批准）且工单有效**。两种情况下都要求工单有效。符合公司规定。
- **有权限或（已批准且工单有效）**。有权限就能导出，即使工单已过期。改变了公司规定。

两种分组都能通过检查。核对改写是否正确时，用同一个过期工单场景验证它们是否给出公司规定的结果。

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
