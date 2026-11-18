---
name: ctc-write
description: Rewrite or review Chinese technical documentation using the Controlled Technical Chinese specification, run its linter, and verify meaning against the source. Use when asked for CTC editing of specifications, interface docs, procedures, or runbooks.
---

# 用 CTC 改写技术文档

以本仓库的 [CTC 规范](../../docs/CTC-Specification.md)为写作依据。用户可以直接指定此文件，或让 Agent 从克隆的仓库读取此文件和规范。保持仓库目录关系，让规范和检查器可在同一版本找到。

1. 保留原稿。找出表达业务规则、操作步骤和参数约束的段落。按规范修改相关正文，保留代码、引用、接口标识和用户要求的格式。原文含义明确时使用合适的 CTC 表达。原文缺少责任人或条件分组依据时，保留可核实的内容并标记待确认。
2. 从仓库根目录运行 `python3 src/ctc_linter.py "改稿路径.md" --json`。按行号和规则编号核实诊断、修改并复跑。返回 1 表示有诊断，返回 2 表示输入错误。保留无法在不改变原意的情况下修复的问题。
3. 对照原文和已有业务依据，核对执行者、动作、对象、条件、义务与权限、数值及单位、时序和例外。对改变过分组的关键条件，用真值表或现有业务测试确认允许和禁止的输入。
4. 交付改稿、最终诊断和待确认项。按用户指定位置保存。用户未指定覆盖时，另存一份。

[前后对照](../../examples/README.md)展示了一组通过检查但业务含义不同的条件。
