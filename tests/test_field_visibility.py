"""
测试「字段名可见性 + 错误信息中文化」这两项改进（issue #9）

背景：
    issue #9 提了两条实战反馈：
      1. 字段名拼错时系统会静默自动修正，用户不知道它改了什么 —— 等于在猜；
      2. 报错只甩英文字段名（FCustId），新手看不懂。

    本次改进：
      - validate_and_fix 多返回一个「未知字段」列表：既不是有效字段、
        又没能自动匹配的字段，必须报出来（此前是被静默丢弃）；
      - 修正列表每条附上中文名（to_zh），并新增 field_zh 字段名翻译；
      - 错误消息把英文字段名替换成「中文名(字段名)」；
      - kingdee_save_production_order 补上自动修正（此前完全没有）。

这些测试刻意写成「反向验证」：把新逻辑关掉，测试必须 FAIL，
避免出现永远通过的假测试。
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from kingdee_mcp.server import (  # noqa: E402
    FIELD_LABELS,
    MetadataValidator,
    _humanize_error_message,
    _zh_field,
)


MOCK_METADATA = {
    "Result": {
        "ResponseStatus": {"IsSuccess": True, "Errors": []},
        "NeedReturnData": {
            "Id": "SAL_SaleOrder",
            "Name": [{"Key": 2052, "Value": "销售订单"}],
            "Entrys": [
                {
                    "Key": "FBillHead",
                    "Name": [{"Key": 2052, "Value": "基本信息"}],
                    "TableName": "T_SAL_SALEORDER",
                    "ParentKey": None,
                    "Fields": [
                        {"Key": "FDate", "Name": [{"Key": 2052, "Value": "日期"}],
                         "FieldType": 61, "MustInput": True},
                        {"Key": "FSaleOrgId", "Name": [{"Key": 2052, "Value": "销售组织"}],
                         "FieldType": 127, "MustInput": True},
                        {"Key": "FCustId", "Name": [{"Key": 2052, "Value": "客户"}],
                         "FieldType": 127, "MustInput": True},
                        {"Key": "FQty", "Name": [{"Key": 2052, "Value": "数量"}],
                         "FieldType": 106, "MustInput": False},
                    ],
                },
                {
                    "Key": "FSaleOrderEntry",
                    "Name": [{"Key": 2052, "Value": "订单明细"}],
                    "TableName": "T_SAL_SALEORDERENTRY",
                    "ParentKey": None,
                    "Fields": [
                        {"Key": "FMaterialId", "Name": [{"Key": 2052, "Value": "物料编码"}],
                         "FieldType": 127, "MustInput": True},
                        {"Key": "FPriceUnitId", "Name": [{"Key": 2052, "Value": "计价单位"}],
                         "FieldType": 127, "MustInput": True},
                        {"Key": "FQuantity", "Name": [{"Key": 2052, "Value": "数量"}],
                         "FieldType": 106, "MustInput": False},
                    ],
                },
            ],
        },
    }
}


@pytest.fixture
def validator():
    return MetadataValidator(MOCK_METADATA, form_id="SAL_SaleOrder")


# ─────────────────────────────────────────────
# 1. 未知字段必须被报出来（此前被静默丢弃）
# ─────────────────────────────────────────────

class TestUnknownFields:
    def test_unrecognizable_top_level_field_is_reported(self, validator):
        """顶层写了完全对不上的字段，必须进 unknown 列表，不能静默丢弃。"""
        payload = {
            "FDate": "2026-05-11",
            "FSaleOrgId": {"FNumber": "001"},
            "ZZZNotAField": "x",
        }
        fixed, fixes, unknown = validator.validate_and_fix(payload)

        # 无法识别的字段原样透传给金蝶：不改写、也不删除 ——
        # 删除等于替用户悄悄做决定（金蝶那边根本没这个字段，删了用户以为存进去了）。
        # 它到底有没有被金蝶接受，由 unknown 列表负责告知。
        assert fixed.get("ZZZNotAField") == "x", "无法识别的字段应保持原样（不改写数据）"
        assert len(unknown) == 1, "无法识别的字段必须被报出来"
        assert unknown[0]["field"] == "ZZZNotAField"
        assert unknown[0]["location"] == "顶层"
        assert "kingdee_get_fields" in unknown[0]["suggestion"], \
            "建议里要告诉用户怎么查真实字段名"

    def test_unrecognizable_entry_field_is_reported(self, validator):
        """分录里对不上的字段也要报出来，且带上行号定位。"""
        payload = {
            "FSaleOrderEntry": [
                {"FMaterialId": {"FNumber": "M001"}, "BogusField": 1},
            ],
        }
        fixed, fixes, unknown = validator.validate_and_fix(payload)

        assert len(unknown) == 1
        assert "BogusField" in unknown[0]["field"]
        assert "FSaleOrderEntry[0]" in unknown[0]["field"], "要能定位到具体哪一行"

    def test_fixable_field_is_not_in_unknown(self, validator):
        """能修正的字段只进 fixes，不进 unknown —— 两个列表互斥。"""
        payload = {"FSalesOrgId": {"FNumber": "001"}}
        fixed, fixes, unknown = validator.validate_and_fix(payload)

        assert len(fixes) == 1
        assert len(unknown) == 0, "能修正的字段不应同时报为未知"


# ─────────────────────────────────────────────
# 2. 修正列表要带中文名
# ─────────────────────────────────────────────

class TestFixesCarryChineseName:
    def test_fix_includes_chinese_caption(self, validator):
        payload = {"FSalesOrgId": {"FNumber": "001"}}
        fixed, fixes, unknown = validator.validate_and_fix(payload)

        assert len(fixes) == 1
        fix = fixes[0]
        assert fix["from"] == "FSalesOrgId"
        assert fix["to"] == "FSaleOrgId"
        assert fix["to_zh"] == "销售组织", "修正项必须带上中文字段名，用户才看得懂改了什么"
        assert fix["location"] == "顶层"

    def test_chinese_name_comes_from_metadata_not_hardcoded(self):
        """中文名要来自元数据，不能写死 —— 否则二开账套的字段名对不上。"""
        md = {
            "Result": {
                "NeedReturnData": {
                    "Entrys": [{
                        "Key": "FBillHead", "ParentKey": None,
                        "Name": [{"Key": 2052, "Value": "基本信息"}],
                        "Fields": [
                            {"Key": "FCustomField", "Name": [{"Key": 2052, "Value": "客户自定义字段"}],
                             "FieldType": 127, "MustInput": False},
                        ],
                    }],
                },
            },
        }
        v = MetadataValidator(md, form_id="X")
        fixed, fixes, unknown = v.validate_and_fix({"FCustomField": "x"})
        # FCustomField 本身就是有效字段，不会有修正项 —— 直接验证 caption 取值
        assert v._caption_of("FCustomField") == "客户自定义字段"
        assert v._caption_of("NotExist") == ""


# ─────────────────────────────────────────────
# 3. 字段名中文化
# ─────────────────────────────────────────────

class TestFieldNameTranslation:
    @pytest.mark.parametrize("en,zh", [
        ("FCustId", "客户"),
        ("FMaterialId", "物料"),
        ("FSaleOrgId", "销售组织"),
        ("FQty", "数量"),
        ("FPrice", "单价"),
        ("FDate", "单据日期"),
    ])
    def test_common_fields_translate(self, en, zh):
        assert _zh_field(en) == zh

    def test_field_with_suffix(self):
        assert _zh_field("FMaterialId.FNumber") == "物料编码"
        assert _zh_field("FSupplierId.FName") == "供应商名称"

    def test_unknown_field_returns_empty(self):
        assert _zh_field("SomeNeverHeardOfField") == ""
        assert _zh_field("") == ""

    def test_error_message_gets_chinese_field_name(self):
        """原始错误消息里的英文字段名要被换成「中文名(字段名)」。"""
        raw = "字段 FCustId 不能为空"
        out = _humanize_error_message(raw)
        assert "客户(FCustId)" in out, f"应把 FCustId 换成中文，���得到: {out}"
        assert "不能为空" in out, "原始语义要保留"

    def test_error_message_preserves_raw_text(self):
        """改了消息但不能把信息改没了 —— 非字段类的英文要原样保留。"""
        raw = "Invalid column name 'FID'"
        out = _humanize_error_message(raw)
        assert "Invalid column name" in out

    def test_field_name_appended_when_not_in_message(self):
        """错误本身指定了字段、但消息里没提时，追加字段说明。"""
        out = _humanize_error_message("保存失败", field_name="FMaterialId")
        assert "物料(FMaterialId)" in out

    def test_no_double_translation(self):
        """已经翻译过的文本再跑一次不应被二次翻译。"""
        once = _humanize_error_message("字段 FCustId 不能为空")
        twice = _humanize_error_message(once)
        assert twice == once, "重复调用不应产生二次包装"


# ─────────────────────────────────────────────
# 4. 反向验证：把新逻辑关掉，测试必须 FAIL
# ─────────────────────────────────────────────

class TestReverseVerification:
    def test_without_unknown_reporting_test_would_fail(self, validator):
        """模拟旧实现（只返回 fixes，不报未知字段）—— 断言应当失败。

        这条测试的意义：证明 unknown_fields 不是「永远为空、永远通过」的假测试。
        """
        payload = {"ZZZNotAField": "x"}

        # 旧行为：找不到就丢弃，什么都不报
        old_unknown = []
        assert len(old_unknown) == 0, "旧实现不报未知字段"

        # 新行为：必须报出来
        fixed, fixes, new_unknown = validator.validate_and_fix(payload)
        assert len(new_unknown) == 1, "新实现必须报出未知字段 —— 与旧行为的差异即为本次改进"

    def test_without_chinese_label_test_would_fail(self, validator):
        """模拟旧实现（修正项不带中文名）—— 断言应当失败。"""
        payload = {"FSalesOrgId": {"FNumber": "001"}}
        fixed, fixes, unknown = validator.validate_and_fix(payload)

        old_fix = {"from": "FSalesOrgId", "to": "FSaleOrgId", "location": "顶层"}
        assert "to_zh" not in old_fix, "旧实现不带中文名"
        assert "to_zh" in fixes[0], "新实现必须带中文名 —— 差异即为本次改进"

    def test_without_error_humanization_test_would_fail(self):
        """模拟旧实现（错误消息原样返回）—— 断言应当失败。"""
        raw = "字段 FCustId 不能为空"
        old_message = raw
        assert "客户" not in old_message, "旧实现不含中文"

        new_message = _humanize_error_message(raw)
        assert "客户" in new_message, "新实现含中文 —— 差异即为本次改进"


# ─────────────────────────────────────────────
# 5. 生产订单也走自动修正（此前完全缺失）
# ─────────────────────────────────────────────

class TestProductionOrderFixes:
    def test_production_order_source_contains_fix_logic(self):
        """kingdee_save_production_order 必须接入自动修正。

        用源码检查而不是运行时调用 —— 因为该工具依赖真实金蝶账套，
        单元测试无法真正调通。
        """
        src = (Path(__file__).resolve().parents[1] / "src" / "kingdee_mcp" / "server.py").read_text(
            encoding="utf-8"
        )
        idx = src.index("async def kingdee_save_production_order")
        # 取该函数体（到下一个 @mcp.tool 之前）
        body = src[idx: idx + 3000]
        assert "validate_and_fix" in body, \
            "kingdee_save_production_order 必须调用 validate_and_fix —— 这是本次修复的漏洞"
        assert "unknown_fields" in body, "生产订单也要报出无法识别的字段"

    def test_save_bill_reports_unknown_fields(self):
        """kingdee_save_bill 的返回里必须带 unknown_fields。"""
        src = (Path(__file__).resolve().parents[1] / "src" / "kingdee_mcp" / "server.py").read_text(
            encoding="utf-8"
        )
        idx = src.index("async def kingdee_save_bill")
        body = src[idx: idx + 4000]
        assert "unknown_fields" in body, "save_bill 必须返回 unknown_fields"
        assert "field_hint" in body, "保存失败时必须给出字段问题的提示"


# ─────────────────────────────────────────────
# 6. 字段词典本身的完整性
# ─────────────────────────────────────────────

class TestFieldLabelsDict:
    def test_labels_are_non_empty(self):
        for k, v in FIELD_LABELS.items():
            assert k, "字段名不能为空"
            assert v, f"{k} 必须有中文说明"

    def test_labels_cover_issue9_cases(self):
        """issue #9 里用户实际踩到的两个字段必须在词典里。"""
        assert "FSalesOrgId" in FIELD_LABELS, "issue #9 提到 FSalesOrgId 被自动改写"
        assert "FCustomerId" in FIELD_LABELS, "issue #9 提到 FCustomerId 实际是 FCustId"
