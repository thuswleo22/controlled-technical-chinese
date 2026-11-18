# Controlled Technical Chinese

CTC is a writing specification, an agent workflow, and a deterministic linter for Chinese technical documentation.

[中文](README.md) · [Specification](docs/CTC-Specification.md) · [Agent skill](skills/ctc-write/SKILL.md) · [Examples](examples/README.md) · [Validation](docs/Validation.md)

In Chinese technical prose, omitting a recoverable subject can read naturally. When a procedure changes operators, the same omission can leave a reader guessing who acts. Rewriting can also change policy. For example, `(permission OR approval) AND valid ticket` and `permission OR (approval AND valid ticket)` are both clear, but they give different answers when a person has permission and the ticket has expired.

CTC applies controlled writing to Chinese terminology, actor and reference clarity, logic, obligation and permission, quantities, and procedural structure. The agent proposes edits. The linter flags patterns covered by the rules. The editor checks the resulting meaning against the original requirements. The project draws on the controlled-writing approach of [ASD-STE100](https://www.asd-ste100.org/) and defines its own Chinese rules.

## Try it

Use Python 3.9 or newer. The linter uses only the standard library and accepts UTF-8 Markdown or plain text.

```sh
git clone https://github.com/thuswleo22/controlled-technical-chinese.git
cd controlled-technical-chinese
python3 src/ctc_linter.py examples/before.md
python3 src/ctc_linter.py examples/after.md --json
```

The first command reports three findings and exits with status 1. The second prints `[]` and exits with status 0. To edit your own document, give the agent your source, the specification, and the workflow in [skills/ctc-write/SKILL.md](skills/ctc-write/SKILL.md).

```sh
python3 -m unittest discover -s tests -q
python3 experiments/reproduce_public.py
```

For a false positive, missed finding, or rewrite that changes meaning, send a minimal example and describe the expected behavior. See the [contribution guide](CONTRIBUTING.md). Original project material uses the [MIT license](LICENSE).
