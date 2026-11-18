"""Check candidate CTC rules in Markdown or plain text."""

import argparse
from dataclasses import asdict, dataclass
from decimal import Decimal
import json
from operator import and_, or_, xor
from pathlib import Path
import re

FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})(.*)$")
LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
CONDITION_START = re.compile(r"(?:^|[。！？；])[ \t]*(如果|若|当)", re.MULTILINE)
OPERATORS = re.compile(r"异或|或者|并且|或(?!许|然)|(?<!尚)(?<!暂)且")
NORMALIZED = {"并且": "且", "或者": "或"}
APPLY = {"且": and_, "或": or_, "异或": xor}
QUOTED = re.compile(r"《[^》]*》|“[^”]*”|「[^」]*」")
MODAL_LABELS = {"要求": "必须", "禁止": "不得", "建议": "宜", "权限": "有权", "能力": "能够"}
MODAL_LABEL = re.compile(
    r"^[ \t]*(?:\*{2}|__)?(要求|禁止|建议|权限|能力)(?:\*{2}|__)?[：:](?:\*{2}|__)?",
    re.MULTILINE,
)
MODAL_WORD = re.compile(r"不得不|没有权|不能够|不是必须|并非必须|必须|不得|不宜|(?<!适)(?<!便)(?<!相)宜(?!宾|昌|居)|有权(?!威|衡|限)|能够(?!性)|无权|无法|不必|可以|应该|(?<!必)须")
FRAME_LABEL = re.compile(
    r"^[ \t]*(?:\*{2}|__)?(警告|步骤|条件|措施|后果|执行者|动作)(?:\*{2}|__)?[：:](?:\*{2}|__)?",
    re.MULTILINE,
)
FRAME_TYPES = {
    "警告": ("RULE-DOC-01", ("措施", "后果"),
           "分行写出措施和后果。需要限定适用情形时，把条件放在措施之前。"),
    "步骤": ("RULE-REF-01", ("执行者", "动作"),
           "分别写明执行者与动作。需要限定适用情形时，把条件放在执行者之前。"),
}
COPY_OBJECT = re.compile(
    r"^[ \t]*(?:配置|文件|目录|磁盘|镜像|请求|数据|对象|记录|日志|响应|字节|代码|"
    r"参数|内容|凭据|文本|快照|备份|密钥|元数据|(?:一|两|[1-9][0-9]*)(?:份|套|个)|这些|该|此|名为|[`“「])"
)
COPY_CONTEXT = re.compile(
    r"(?:动作[：:]|请|先|再|然后|随后|必须|应当|应该|需要|可以|能够|有权|已|来|"
    r"管理员|操作员|值班员|客户端|服务器|处理器|脚本|系统|程序|工具|用户|代理)[ \t]*$"
)
COPY_DESTINATION = re.compile(r"^[ \t]*(?:到|至)")
WEAK_ENCODE = re.compile(
    r"(?<![针面相应比核校绝乐反])对(?P<object>[^对，,。！？；;\n]+?)进行[ \t]*编码"
    r"(?![ \t]*(?:[费器库]|模块|模式|错误|转换|过?的))"
)
MODAL_END = re.compile(r"[。！？；!?;]")
DISPOSAL_RELATIVE = re.compile(rf"(?:把|将)(?=[ \t]*(?:{MODAL_WORD.pattern}))[^，,。！？；]*?的")
COMPLEMENT_HEAD = re.compile(r"(?:建议|要求|认为|指出|说明|通知|确认)([^，,。！？；]*)$")
NEXT_ACTION = re.compile(r"[，,]\s*(?:然后|随后|接着)")
INLINE_CODE = re.compile(r"(`+)([^\n]*?)\1")

REFERENCE_FIELD = re.compile(r"^[ \t]*(?:\*\*|__)?(?:动作|措施)(?:\*\*|__)?[：:](?:\*\*|__)?", re.MULTILINE)
DANGLING_REFERENCE = re.compile(r"(?<!应)(?:该|上述)(?=[ \t]*(?:[，,。！？；;]|$))")
RANGE_FIELD = re.compile(r"^[ \t]*(?:\*\*|__)?(?:范围|阈值)(?:\*\*|__)?[：:](?:\*\*|__)?(?P<body>[^\n]*)", re.MULTILINE)
RELATION = r"(?:大于或等于|小于或等于|大于等于|小于等于|大于|小于|>=|<=|>|<|≥|≤)"
BOUND = re.compile(rf"(?P<relation>{RELATION})[ \t]*(?P<value>[+-]?(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+))[ \t]*(?P<unit>(?!(?:AND|and)(?![A-Za-z]))[A-Za-zμ℃%°/]+|摄氏度|毫秒|秒|字节|伏|个)?")
LOWER = {"大于", "大于等于", "大于或等于", ">", ">=", "≥"}
OPEN = {"大于", "小于", ">", "<"}
SPEC_SECTION = re.compile(r"^### (RULE-[A-Z]+-[0-9]+) [^\n]+\n(.*?)(?=^#{1,3} |\Z)", re.MULTILINE | re.DOTALL)
SPEC_EXAMPLE = re.compile(r"^\x60{3}text\n(.*?)^\x60{3}$", re.MULTILINE | re.DOTALL)


@dataclass(frozen=True)
class Diagnostic:
    line: int
    rule_id: str
    detail: str
    suggestion: str


def mixed_group_requires_scope(text):
    if re.search(r"[()（）《》“”「」]", text):
        return True
    atoms = [part.strip() for part in OPERATORS.split(text)]
    operators = [NORMALIZED.get(hit[0], hit[0]) for hit in OPERATORS.finditer(text)]
    if len(atoms) == 3 and all(atoms):
        # Each bit represents one assignment to three independent variables.
        masks = dict(zip(dict.fromkeys(atoms), (0b11110000, 0b11001100, 0b10101010)))
        a, b, c = (masks[atom] for atom in atoms)
        first, second = (APPLY[operator] for operator in operators)
        return second(first(a, b), c) != first(a, second(b, c))
    return not (all(atoms) and len(set(atoms)) == 1 and "异或" not in operators)


def condition_scope(text, start):
    """Return the condition's end and mixed-operator flag, if well formed."""
    if text.startswith("且仅当", start):
        start += len("且仅当")
    scopes = [(start, set())]
    expected = []
    mixed = False
    index = start
    while index < len(text):
        literal = QUOTED.match(text, index)
        if literal:
            index = literal.end()
            continue
        char = text[index]
        if char in "（(":
            expected.append("）" if char == "（" else ")")
            scopes.append((index + 1, set()))
        elif char in "）)":
            if not expected or expected.pop() != char:
                return None
            group_start, operators = scopes.pop()
            if len(operators) > 1 and not mixed:
                mixed = mixed_group_requires_scope(text[group_start:index])
        elif char in "，," and not expected:
            return index, mixed or (len(scopes[0][1]) > 1 and
                                    mixed_group_requires_scope(text[start:index]))
        elif char in "。！？；":
            return None
        else:
            operator = OPERATORS.match(text, index)
            if operator:
                scopes[-1][1].add(NORMALIZED.get(operator[0], operator[0]))
                index = operator.end()
                continue
        index += 1
    return None


def paragraphs(text):
    fence = None
    block = []
    for number, line in enumerate(text.splitlines(), 1):
        marker = FENCE.match(line)
        if fence:
            if (marker and marker[1][0] == fence[0] and
                    len(marker[1]) >= len(fence) and not marker[2].strip()):
                fence = None
            continue
        boundary = not line.strip() or marker or line.lstrip().startswith(("#", "|", ">"))
        item = LIST_ITEM.match(line)
        if block and (boundary or item):
            yield block
            block = []
        if marker:
            fence = marker[1]
        if not boundary:
            block.append((number, line))
    if block:
        yield block


def mask_quotes(prose):
    prose = INLINE_CODE.sub(lambda match: " " * len(match[0]), prose)
    return QUOTED.sub(lambda match: re.sub(r"[^\n]", " ", match[0]), prose)


def strip_list_markers(block):
    return "\n".join(LIST_ITEM.sub("", line, count=1) for _, line in block)


def main_modal_marker(body):
    relative = DISPOSAL_RELATIVE.search(body)
    for hit in MODAL_WORD.finditer(body):
        if relative is not None and relative.start() <= hit.start() < relative.end():
            continue
        complement = COMPLEMENT_HEAD.search(body[:hit.start()])
        if complement and not complement[1].rstrip().endswith(("后", "之前", "时", "期间")):
            continue
        return hit
    return None


def check_modal_labels(prose, visible, block):
    headings = list(MODAL_LABEL.finditer(visible))
    for index, heading in enumerate(headings):
        stop = headings[index + 1].start() if index + 1 < len(headings) else len(visible)
        end = MODAL_END.search(visible, heading.end(), stop)
        body = visible[heading.end():end.start() if end else stop].lstrip()
        guard = re.match(r"(?:如果|若|当)", body)
        if guard:
            condition = condition_scope(body, guard.end())
            if condition:
                body = body[condition[0] + 1:]
        sequence = NEXT_ACTION.search(body)
        if sequence:
            body = body[:sequence.start()]
        expected = MODAL_LABELS[heading[1]]
        marker = main_modal_marker(body)
        if marker and marker[0] == expected:
            continue
        line_number = block[prose.count("\n", 0, heading.start())][0]
        found = f"检测到「{marker[0]}」" if marker else "未检测到约定的模态词"
        yield Diagnostic(
            line_number, "RULE-MOD-01",
            f"「{heading[1]}」条款的主句应使用「{expected}」。{found}。",
            f"核对条款的实际强度。需要保留该标签时，在主句使用「{expected}」。",
        )


def framed_blocks(prose, visible):
    header = None
    fields = []
    for label in [*FRAME_LABEL.finditer(visible), None]:
        if label is not None and label[1] not in FRAME_TYPES:
            if header is not None:
                end = prose.find("\n", label.end())
                value = prose[label.end():end if end >= 0 else len(prose)].strip()
                fields.append((label[1], value))
            continue
        if header is not None:
            yield header, fields
        header = label
        fields = []


def frame_problems(required, fields):
    names = [name for name, _ in fields]
    empty = [name for name, value in fields if not value]
    missing = [name for name in required if name not in names]
    counts = {name: names.count(name) for name in dict.fromkeys(names)}
    repeated = [name for name, count in counts.items() if count > 1]
    problems = [
        f"{title}{'、'.join(values)}"
        for title, values in (("缺少", missing), ("为空", empty), ("重复", repeated))
        if values
    ]
    if not problems and tuple(names) not in (required, ("条件", *required)):
        problems.append("字段顺序错误")
    return problems


def check_frames(prose, visible, block):
    for header, fields in framed_blocks(prose, visible):
        rule, required, suggestion = FRAME_TYPES[header[1]]
        problems = frame_problems(required, fields)
        if problems:
            line_number = block[prose.count("\n", 0, header.start())][0]
            yield Diagnostic(line_number, rule, f"{header[1]}块{'，'.join(problems)}。", suggestion)


def check_word_forms(prose, visible, block):
    for hit in re.finditer("拷贝", visible):
        line_index = prose.count("\n", 0, hit.start())
        start = visible.rfind("\n", 0, hit.start()) + 1
        leading = visible[start:hit.start()]
        following = prose[hit.end():]
        list_command = LIST_ITEM.match(block[line_index][1]) and not leading.strip()
        labeled_or_explicit = COPY_CONTEXT.search(leading) or list_command
        if COPY_DESTINATION.match(following) or (labeled_or_explicit and COPY_OBJECT.match(following)):
            yield Diagnostic(block[line_index][0], "RULE-LEX-01", "「拷贝」出现在复制动作的位置。",
                             "用「复制」表示生成副本的动作。")
    for hit in WEAK_ENCODE.finditer(visible):
        target = prose[hit.start("object"):hit.end("object")].strip()
        if not target:
            continue
        line_number = block[prose.count("\n", 0, hit.start())][0]
        yield Diagnostic(line_number, "RULE-LEX-02", "「对……进行编码」将编码动作放在虚化谓词后。",
                         "用「编码」作谓词。核对对象、格式和条件后再改写。")


def check_references(prose, visible, block):
    for field in REFERENCE_FIELD.finditer(visible):
        end = visible.find("\n", field.end())
        body = visible[field.end():end if end >= 0 else len(visible)]
        for hit in DANGLING_REFERENCE.finditer(body):
            raw_tail = prose[field.end() + hit.end():].lstrip(" \t")
            if raw_tail.startswith(("`", "“", "「", "《")):
                continue
            term = hit[0]
            line = block[prose.count("\n", 0, field.start())][0]
            yield Diagnostic(line, "RULE-REF-02", f"「{term}」后直接是标点或行末。",
                             "按原文补出被指对象。核对指向后再改写。")


def empty_interval(body):
    bounds = list(BOUND.finditer(body))
    if len(bounds) != 2:
        return False
    first, second = bounds
    subject = body[:first.start()].strip()
    # Restrict the grammar to one scalar and an AND-linked second bound.
    if not re.fullmatch(r"[A-Za-z0-9_\u3400-\u9fff \t]*", subject):
        return False
    between = body[first.end():second.start()].strip()
    if between not in {"且", "并且", "AND", "and", "且" + subject, "并且" + subject}:
        return False
    if body[second.end():].strip() not in {"", "。", ".", "；", ";"}:
        return False
    if first["unit"] != second["unit"]:
        return False
    first_lower, second_lower = (item["relation"] in LOWER for item in bounds)
    if first_lower == second_lower:
        return False
    lower, upper = (first, second) if first_lower else (second, first)
    lo, hi = Decimal(lower["value"]), Decimal(upper["value"])
    return lo > hi or (lo == hi and (lower["relation"] in OPEN or upper["relation"] in OPEN))


def check_ranges(prose, visible, block):
    for field in RANGE_FIELD.finditer(visible):
        if empty_interval(field["body"]):
            line = block[prose.count("\n", 0, field.start())][0]
            yield Diagnostic(line, "RULE-QNT-01", "同一量的上下界构成空区间。",
                             "核对上下界及端点是否包含。按原始要求修正数值或比较符。")


def condition_bracket_error(text, start):
    expected = []
    for index in range(start, len(text)):
        char = text[index]
        if char in "。！？；":
            break
        if char in "（(":
            expected.append("）" if char == "（" else ")")
        elif char in "）)":
            if not expected or expected.pop() != char:
                return True
        elif char in "]}】" and expected:
            return True
        elif char in "，," and not expected:
            return False
    return bool(expected)


def check_grouping(prose, visible, block):
    for condition in CONDITION_START.finditer(visible):
        if condition_bracket_error(visible, condition.end()):
            line = block[prose.count("\n", 0, condition.start(1))][0]
            yield Diagnostic(line, "RULE-LOG-02", "条件的圆括号缺失或类型不配对。",
                             "核对分组含义，再补全同类型的圆括号。")



def check(text):
    for block in paragraphs(text):
        prose = strip_list_markers(block)
        visible = mask_quotes(prose)
        yield from check_modal_labels(prose, visible, block)
        yield from check_frames(prose, visible, block)
        yield from check_word_forms(prose, visible, block)
        yield from check_references(prose, visible, block)
        yield from check_ranges(prose, visible, block)
        yield from check_grouping(prose, visible, block)
        prose = INLINE_CODE.sub(lambda match: "《" + match[2] + "》", prose)
        quotes = iter(QUOTED.finditer(prose))
        quote = next(quotes, None)
        for match in CONDITION_START.finditer(prose):
            offset = match.start(1)
            while quote is not None and quote.end() <= offset:
                quote = next(quotes, None)
            if quote is not None and quote.start() <= offset:
                continue
            scope = condition_scope(prose, match.end())
            if scope is None:
                continue
            end, mixed = scope
            if not mixed:
                continue
            condition = prose[match.end():end]
            line_number = block[prose.count("\n", 0, offset)][0]
            yield Diagnostic(
                line_number, "RULE-LOG-01",
                f"条件在同一层使用多类逻辑连接词：{' '.join(condition.split())}",
                "核对预期条件。用括号标出逻辑连接词的组合范围。",
            )


def bootstrap(text):
    rules = []
    seen = set()
    for section in SPEC_SECTION.finditer(text):
        rule, body = section.groups()
        examples = SPEC_EXAMPLE.findall(body)
        valid = rule not in seen and len(examples) == 2
        seen.add(rule)
        bad_codes, good_codes = set(), set()
        if valid:
            bad_codes = {item.rule_id for item in check(examples[0])}
            good_codes = {item.rule_id for item in check(examples[1])}
        passed = valid and rule in bad_codes and not good_codes
        rules.append({"rule": rule, "passed": passed,
                      "bad_example_codes": sorted(bad_codes), "good_example_codes": sorted(good_codes)})
    findings = [asdict(item) for item in check(text)]
    return {"passed": bool(rules) and all(row["passed"] for row in rules) and not findings,
            "rule_count": len(rules), "rules": rules, "diagnostics": findings}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--json", action="store_true", help="Write a machine-readable diagnostic list")
    parser.add_argument("--bootstrap-check", action="store_true", help="Check specification prose and its rule examples")
    args = parser.parse_args()
    try:
        text = args.path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as error:
        if args.json:
            print(json.dumps({"error": str(error), "path": str(args.path)}, ensure_ascii=False))
            return 2
        parser.error(str(error))
    if args.bootstrap_check:
        result = bootstrap(text)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"CTC self-check {'passed' if result['passed'] else 'failed'}: {result['rule_count']} rules, {len(result['diagnostics'])} prose diagnostics")
        return int(not result["passed"])
    findings = list(check(text))
    if args.json:
        print(json.dumps([{"path": str(args.path), **asdict(item)} for item in findings],
                         ensure_ascii=False, indent=2))
    else:
        for finding in findings:
            print(f"{args.path}:{finding.line}: [{finding.rule_id}] {finding.detail} {finding.suggestion}")
    return int(bool(findings))


if __name__ == "__main__":
    raise SystemExit(main())
