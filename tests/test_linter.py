import json
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ctc_linter import bootstrap, check


class ConditionTests(unittest.TestCase):
    def test_biconditional_prefix_is_not_conjunction(self):
        self.assertEqual(list(check("如果且仅当证书有效或设备受信任，允许登录。")), [])

    def test_unscoped_condition(self):
        findings = list(check("操作步骤\n1. 如果压力稳定或旁路打开且急停可用，启动设备。"))
        self.assertEqual([(item.line, item.rule_id) for item in findings], [(2, "RULE-LOG-01")])

    def test_explicit_scopes(self):
        self.assertEqual(list(check("如果（压力稳定或旁路打开）且急停可用，启动设备。")), [])

    def test_fenced_and_inline_code(self):
        example = "如果压力稳定或旁路打开且急停可用，启动设备。"
        self.assertEqual(list(check(f"~~~txt\n{example}\n~~~\n`{example}`")), [])

    def test_mixed_inside_group(self):
        self.assertEqual(len(list(check("如果（甲或乙且丙）且丁，继续。"))), 1)

    def test_multiline_condition_points_to_opening_line(self):
        text = "前文。\n\n如果压力稳定或者旁路打开\n并且急停可用，启动设备。"
        self.assertEqual([item.line for item in check(text)], [3])

    def test_nested_comma_does_not_end_condition(self):
        text = "如果模式为（远程，限流）或旁路打开且急停可用，启动设备。"
        self.assertEqual([item.line for item in check(text)], [1])

    def test_repeated_atoms_have_one_truth_function(self):
        self.assertEqual(list(check("如果按键A且按键A或按键A，继续。")), [])

    def test_quoted_operators_are_not_connectives(self):
        self.assertEqual(list(check("如果标签为“或”且状态正常，继续。")), [])

    def test_next_list_item_is_not_condition_continuation(self):
        self.assertEqual(list(check("1. 如果甲或乙\n2. 且丙，继续。")), [])

    def test_condition_after_previous_sentence(self):
        self.assertEqual([item.line for item in check("检查设备。\n如果甲或乙且丙，继续。")], [2])

    def test_modal_adverb_containing_or_is_not_connective(self):
        text = "如果故障或许只是暂时现象且服务仍可访问，继续观察。"
        self.assertEqual(list(check(text)), [])

    def test_condition_after_unpunctuated_text_line(self):
        text = "确认环境\n如果认证失败且令牌失效或权限不足，拒绝请求。"
        self.assertEqual([item.line for item in check(text)], [2])

    def test_entire_quoted_example_is_ignored(self):
        text = "“例如。如果认证失败且令牌失效或权限不足，拒绝请求。”"
        self.assertEqual(list(check(text)), [])

    def test_absorption_for_three_atoms_with_same_endpoints(self):
        for condition in ("甲有效且乙有效或甲有效", "甲有效或乙有效且甲有效"):
            self.assertEqual(list(check(f"如果{condition}，继续。")), [])

    def test_adjacent_repeated_atoms_can_still_be_ambiguous(self):
        self.assertEqual(len(list(check("如果甲有效且甲有效或乙有效，继续。"))), 1)

    def test_absorption_applies_inside_groups(self):
        example = "如果（甲有效且乙有效或甲有效）且丁有效，继续。"
        self.assertEqual(list(check(example)), [])

    def test_xor_with_or_is_mixed(self):
        self.assertEqual(len(list(check("如果甲有效异或乙有效或丙有效，继续。"))), 1)

    def test_all_xor_is_associative(self):
        self.assertEqual(list(check("如果甲有效异或乙有效异或丙有效，继续。")), [])

    def test_repeated_atom_does_not_hide_xor_ambiguity(self):
        self.assertEqual(len(list(check("如果甲有效异或乙有效或甲有效，继续。"))), 1)


class ModalTests(unittest.TestCase):
    def modal(self, text):
        return [finding for finding in check(text) if finding.rule_id == "RULE-MOD-01"]

    def test_explicit_requirements(self):
        text = "要求：管理员必须确认备份。\n禁止：管理员不得删除原件。"
        self.assertEqual(self.modal(text), [])

    def test_weakened_requirement_points_to_label(self):
        text = "前文。\n\n- 要求：管理员宜确认备份。"
        self.assertEqual([item.line for item in self.modal(text)], [3])

    def test_precondition_marker_does_not_satisfy_main_clause(self):
        text = "要求：如果工单必须经审批，操作员宜通知管理员。"
        self.assertEqual(len(self.modal(text)), 1)

    def test_parenthesized_comma_in_condition(self):
        text = "权限：如果策略（必须审批，必须记录）已生效，审计员有权导出。"
        self.assertEqual(self.modal(text), [])

    def test_legacy_default_does_not_hide_conflict(self):
        text = "禁止：管理员不得不重启服务。"
        self.assertEqual(len(self.modal(text)), 1)

    def test_known_lexical_lookalikes(self):
        for text in ("建议：宜宾机房启用备用链路。", "权限：缓存中有权威数据。",
                     "能力：检查能够性的词条。"):
            self.assertEqual(len(self.modal(text)), 1)

    def test_quote_and_fence_do_not_set_marker(self):
        self.assertEqual(len(self.modal("要求：读取标签「必须」并保存。")), 1)
        self.assertEqual(self.modal("~~~txt\n要求：读取标签并保存。\n~~~"), [])

    def test_negated_permission_does_not_satisfy_label(self):
        self.assertEqual(len(self.modal("权限：访客没有权读取日志。")), 1)

    def test_later_action_cannot_satisfy_first_action(self):
        self.assertEqual(len(self.modal("要求：客户端启动，然后必须检查连接。")), 1)

    def test_introductory_clause_can_precede_action(self):
        self.assertEqual(self.modal("要求：维护窗口内，管理员必须完成备份。"), [])

    def test_modal_in_disposal_modifier_does_not_satisfy_label(self):
        self.assertEqual(len(self.modal("要求：把必须校验通过的节点加入队列。")), 1)
        self.assertEqual(self.modal("要求：操作员必须把校验通过的节点加入队列。"), [])

    def test_modal_in_relative_or_complement_is_not_main_clause(self):
        texts = (
            "要求：系统将必须更新的任务加入队列。",
            "要求：操作员建议设备必须断电。",
        )
        for text in texts:
            self.assertEqual(len(self.modal(text)), 1)
        self.assertEqual(self.modal("要求：操作员确认设备状态后必须断电。"), [])

    def test_handle_is_not_a_disposal_marker(self):
        self.assertEqual(self.modal("要求：把手必须装在窗口的上方。"), [])

    def test_livable_area_is_not_recommendation(self):
        self.assertEqual(len(self.modal("建议：控制台显示宜居区域的温度。")), 1)

    def test_next_labeled_clause_cannot_satisfy_previous(self):
        text = "要求：复核记录\n要求：管理员必须确认备份"
        self.assertEqual([item.line for item in self.modal(text)], [1])


class WarningTests(unittest.TestCase):
    def warning(self, text):
        return [finding for finding in check(text) if finding.rule_id == "RULE-DOC-01"]

    def test_complete_warning(self):
        text = "**警告：** 热表面。\n条件：设备正在加热。\n措施：保持防护罩闭合。\n后果：裸露表面可造成烫伤。"
        self.assertEqual(self.warning(text), [])

    def test_action_may_be_code(self):
        text = "警告：集群可能处理生产流量。\n措施：`kubectl get pods`\n后果：可能误判环境。"
        self.assertEqual(self.warning(text), [])

    def test_consequence_after_blank_line_does_not_count(self):
        text = "警告：热表面。\n措施：保持防护罩闭合。\n\n后果：触碰时可能烫伤。"
        findings = self.warning(text)
        self.assertEqual([item.line for item in findings], [1])
        self.assertIn("缺少后果", findings[0].detail)

    def test_empty_and_repeated_fields(self):
        text = "警告：热表面。\n措施：\n措施：保持防护罩闭合。\n后果：触碰时可能烫伤。"
        findings = self.warning(text)
        self.assertEqual(len(findings), 1)
        self.assertIn("为空措施", findings[0].detail)
        self.assertIn("重复措施", findings[0].detail)

    def test_order_and_quoted_block(self):
        text = "警告：热表面。\n后果：触碰时可能烫伤。\n措施：保持防护罩闭合。"
        self.assertEqual(len(self.warning(text)), 1)
        self.assertEqual(self.warning("“警告：这是示例。”"), [])


class LanguageTests(unittest.TestCase):
    def test_lexical_nominal_and_verbal_contrast(self):
        self.assertEqual(list(check("接口返回该对象的拷贝。")), [])
        findings = list(check("- 拷贝配置文件。"))
        self.assertEqual([(item.line, item.rule_id) for item in findings], [(1, "RULE-LEX-01")])

    def test_copy_of_one_file_is_a_verb_in_an_imperative_list_item(self):
        text = "2. 拷贝一份配置模板文件。"
        self.assertEqual([(item.line, item.rule_id) for item in check(text)], [(1, "RULE-LEX-01")])
        self.assertEqual(list(check("接口返回一份拷贝。")), [])

    def test_encoding_compound_is_not_the_encoding_predicate(self):
        text = "监测器对失败请求进行编码错误分类。"
        self.assertEqual(list(check(text)), [])
        self.assertEqual(len(list(check("服务器对响应进行编码。"))), 1)

    def test_literal_as_object_preserves_diagnostic_context(self):
        findings = list(check("操作员拷贝 `config.yaml`。\n服务器对 `payload` 进行编码。"))
        self.assertEqual([(item.line, item.rule_id) for item in findings],
                         [(1, "RULE-LEX-01"), (2, "RULE-LEX-02")])

    def test_nested_procedure_and_warning_keep_separate_field_sets(self):
        text = "步骤：执行检查\n执行者：系统\n警告：可能影响流量\n措施：等待窗口\n后果：连接重置"
        self.assertEqual([(item.line, item.rule_id) for item in check(text)], [(1, "RULE-REF-01")])

    def test_all_labeled_language_fixtures(self):
        for filename in ("lex_morph_cases.json", "step_frame_cases.json", "language_lint_holdout.json"):
            cases = json.loads((ROOT / "corpus" / filename).read_text(encoding="utf-8"))
            for case in cases:
                with self.subTest(case=case["id"]):
                    actual = any(item.rule_id == case["rule"] for item in check(case["text"]))
                    self.assertEqual(actual, case["expect"])

    def test_cli_diagnostic_on_txt_and_markdown(self):
        tool = ROOT / "src/ctc_linter.py"
        with TemporaryDirectory() as directory:
            for extension in ("txt", "md"):
                path = Path(directory) / f"example.{extension}"
                path.write_text("概述。\n\n步骤：开始检查。\n动作：检查节点。\n", encoding="utf-8-sig")
                result = subprocess.run([sys.executable, str(tool), str(path)],
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 1)
                self.assertIn(":3: [RULE-REF-01]", result.stdout)


class MergeTests(unittest.TestCase):
    def test_independent_merge_cases(self):
        cases = json.loads((ROOT / "corpus/merge_cases.json").read_text(encoding="utf-8"))
        for case in cases:
            with self.subTest(case=case["id"]):
                found = any(item.rule_id == case["rule"] for item in check(case["text"]))
                self.assertEqual(found, case["expect"])

    def test_interval_enumeration(self):
        sys.path.insert(0, str(ROOT / "experiments"))
        from merge_validation import interval_cases
        for case in interval_cases():
            with self.subTest(text=case["text"]):
                found = any(item.rule_id == "RULE-QNT-01" for item in check(case["text"]))
                self.assertEqual(found, case["expect"])

    def test_reference_to_a_code_or_quoted_object(self):
        for text in ("动作：保存该 `request`。", "措施：保存上述“记录”。"):
            self.assertFalse(any(item.rule_id == "RULE-REF-02" for item in check(text)))

    def test_unitless_english_interval_connectors(self):
        for connector in ("AND", "and"):
            text = f"范围：数量大于 5 {connector} 小于 3。"
            self.assertTrue(any(item.rule_id == "RULE-QNT-01" for item in check(text)))

    def test_all_condition_forms_preserve_main_modality(self):
        for condition in ("如果工单必须经审批", "若工单必须经审批", "当工单必须经审批时"):
            text = f"要求：{condition}，则操作员宜通知管理员。"
            self.assertTrue(any(item.rule_id == "RULE-MOD-01" for item in check(text)))

    def test_decimal_precision(self):
        text = "范围：电压>0.1000000000000000001V且<=0.1V。"
        self.assertTrue(any(item.rule_id == "RULE-QNT-01" for item in check(text)))

    def test_bootstrap_checks_prose_and_both_examples(self):
        path = ROOT / "docs/CTC-Specification.md"
        text = path.read_text(encoding="utf-8")
        result = bootstrap(text)
        self.assertTrue(result["passed"])
        self.assertEqual(result["rule_count"], 9)
        self.assertFalse(bootstrap(text.replace("动作：保存该。", "动作：保存该请求。", 1))["passed"])
        self.assertFalse(bootstrap(text + "\n动作：保存该。\n")["passed"])

    def test_bootstrap_rejects_empty_document(self):
        self.assertFalse(bootstrap("普通说明。")["passed"])

    def test_json_cli_modes_and_missing_file(self):
        tool = ROOT / "src/ctc_linter.py"
        with TemporaryDirectory() as directory:
            path = Path(directory) / "sample.md"
            path.write_text("动作：保存上述。", encoding="utf-8")
            result = subprocess.run([sys.executable, str(tool), str(path), "--json"],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(json.loads(result.stdout)[0]["rule_id"], "RULE-REF-02")
            path.write_text("动作：保存上述记录。", encoding="utf-8")
            result = subprocess.run([sys.executable, str(tool), str(path), "--json"],
                                    capture_output=True, text=True)
            self.assertEqual((result.returncode, json.loads(result.stdout)), (0, []))
            missing = path.with_name("missing.md")
            result = subprocess.run([sys.executable, str(tool), str(missing), "--json"],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn("error", json.loads(result.stdout))

    def test_bootstrap_cli(self):
        result = subprocess.run([sys.executable, str(ROOT / "src/ctc_linter.py"),
                                 str(ROOT / "docs/CTC-Specification.md"),
                                 "--bootstrap-check", "--json"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertTrue(json.loads(result.stdout)["passed"])


if __name__ == "__main__":
    unittest.main()
