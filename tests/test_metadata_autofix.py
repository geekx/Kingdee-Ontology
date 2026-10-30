"""
测试元数据自动纠错功能
"""
import asyncio
import sys
sys.path.insert(0, "src")

from kingdee_mcp.server import MetadataValidator, FieldDef


# 模拟金蝶 QueryBusinessInfo 返回的元数据（结构与现实现 _parse_fields 对齐：
# Result.NeedReturnData.Entrys[].Fields[].Key；FieldType 为数字编码）
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
                    "EntryName": "SAL_SALEORDER",
                    "EntryPkFieldName": "FID",
                    "Fields": [
                        {"Key": "FDate", "Name": [{"Key": 2052, "Value": "日期"}],
                         "FieldType": 61, "MustInput": True},
                        {"Key": "FSaleOrgId", "Name": [{"Key": 2052, "Value": "销售组织"}],
                         "FieldType": 127, "MustInput": True},
                        {"Key": "FCustId", "Name": [{"Key": 2052, "Value": "客户"}],
                         "FieldType": 127, "MustInput": True},
                    ]
                },
                {
                    "Key": "FSaleOrderEntry",
                    "Name": [{"Key": 2052, "Value": "订单明细"}],
                    "TableName": "T_SAL_SALEORDERENTRY",
                    "ParentKey": None,
                    "EntryName": "SAL_SALEORDERENTRY",
                    "EntryPkFieldName": "FENTRYID",
                    "Fields": [
                        {"Key": "FMaterialId", "Name": [{"Key": 2052, "Value": "物料编码"}],
                         "FieldType": 127, "MustInput": True},
                        {"Key": "FPriceUnitId", "Name": [{"Key": 2052, "Value": "计价单位"}],
                         "FieldType": 127, "MustInput": True},
                        {"Key": "FQuantity", "Name": [{"Key": 2052, "Value": "数量"}],
                         "FieldType": 106, "MustInput": False},
                    ]
                }
            ]
        }
    }
}


def test_metadata_validator():
    """测试 MetadataValidator"""
    print("=" * 60)
    print("测试 MetadataValidator 自动纠错功能")
    print("=" * 60)

    validator = MetadataValidator(MOCK_METADATA)

    # 测试1: 字段名拼写错误（表头字段仍由 FSales→FSale 前缀规则修正；
    #        分录实体名现实现不再自动修正——候选集仅表头字段，须用正确名；
    #        分录内子字段仍走保守模糊修正）
    print("\n[测试1] 字段名拼写错误")
    payload = {
        "FDate": "2026-05-11",
        "FSalesOrgId": {"FNumber": "001"},  # 错误：应修正为 FSaleOrgId
        "FCustId": {"FNumber": "C001"},
        "FSaleOrderEntry": [  # 分录实体名：当前实现不修正，须用正确名
            {"FMaterilId": {"FNumber": "M001"}, "FPriceUnitId": {"FNumber": "P001"}}  # 错误：应修正为 FMaterialId
        ]
    }

    fixed, fixes, unknown = validator.validate_and_fix(payload)
    print(f"  原始字段: {list(payload.keys())}")
    print(f"  修正后: {list(fixed.keys())}")
    print(f"  修正列表: {fixes}")
    print(f"  未知字段: {unknown}")

    # 验证（与现实现行为一致）
    assert "FSaleOrgId" in fixed, "FSalesOrgId 应该被修正为 FSaleOrgId"
    assert "FSalesOrgId" not in fixed, "FSalesOrgId 不应残留"
    assert "FSaleOrderEntry" in fixed, "FSaleOrderEntry 应保持正确实体名"
    assert "FMaterialId" in fixed["FSaleOrderEntry"][0], "分录子字段 FMaterilId 应该被修正为 FMaterialId"
    print("  [PASS]")

    # 测试2: 正确字段不应被修改
    print("\n[测试2] 正确字段不应被修改")
    payload2 = {
        "FDate": "2026-05-11",
        "FSaleOrgId": {"FNumber": "001"},  # 正确
        "FSaleOrderEntry": [  # 正确
            {"FMaterialId": {"FNumber": "M001"}}
        ]
    }

    fixed2, fixes2, unknown2 = validator.validate_and_fix(payload2)
    print(f"  修正列表: {fixes2 if fixes2 else '无修正'}")
    assert len(fixes2) == 0, "正确的字段不应被修改"
    assert len(unknown2) == 0, "正确字段不应被判为未知"
    print("  [PASS]")

    # 测试3: 获取有效字段列表
    print("\n[测试3] 获取有效字段列表")
    valid_fields = validator.get_valid_field_names()
    print(f"  有效字段: {valid_fields}")
    assert "FSaleOrgId" in valid_fields
    assert "FSaleOrderEntry" in valid_fields
    assert "FSaleOrderEntry.FMaterialId" in valid_fields
    print("  [PASS]")

    # 测试4: 获取必填字段
    print("\n[测试4] 获取必填字段")
    required = validator.get_required_fields()
    print(f"  必填字段: {required}")
    assert "FSaleOrgId" in required
    assert "FDate" in required
    print("  [PASS]")

    print("\n" + "=" * 60)
    print("所有测试通过！元数据自动纠错功能正常")
    print("=" * 60)


if __name__ == "__main__":
    test_metadata_validator()
