from app.code_index import extract_sql_lineage


def test_from_alias_is_not_part_of_physical_table_name():
    sql = """
    INSERT INTO dwd.dwd_order_detail
    SELECT o.order_id, u.user_name
    FROM ods.yzl_order_info AS o
    LEFT JOIN ods.yzl_user u ON o.user_id = u.id
    """
    result = extract_sql_lineage(sql)
    assert result["writes"] == ["dwd.dwd_order_detail"]
    assert "ods.yzl_order_info" in result["reads"]
    assert "ods.yzl_user" in result["reads"]
    assert all(" AS " not in name.upper() for name in result["reads"] + result["writes"])


def test_insert_column_list_is_not_part_of_target_table_name():
    sql = """
    INSERT INTO ads.ads_order_detail_di (
        order_no,
        payment_dt,
        service_order_no,
        package_order_no,
        phone_num,
        order_amount
    )
    SELECT
        order_no,
        payment_dt,
        service_order_no,
        package_order_no,
        phone_num,
        order_amount
    FROM dws.dws_order_detail_di
    """
    result = extract_sql_lineage(sql)
    assert result["writes"] == ["ads.ads_order_detail_di"]
    assert result["reads"] == ["dws.dws_order_detail_di"]
    assert "(" not in result["writes"][0]
