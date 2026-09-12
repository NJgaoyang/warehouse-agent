from app.warehouse_analysis import infer_domain, infer_layer, infer_subject


def test_layer_inference_from_schema_and_table_prefix():
    assert infer_layer("ods.ods_order")[0] == "ODS"
    assert infer_layer("dwd.dwd_trade_order_detail")[0] == "DWD"
    assert infer_layer("dws_trade_city_day")[0] == "DWS"
    assert infer_layer("ads.ads_trade_dashboard")[0] == "ADS"
    assert infer_layer("dim.dim_city")[0] == "DIM"


def test_trade_domain_and_subject_inference():
    context = "数仓研发 交易域订单ETL DWD订单明细 dwd.dwd_trade_order_detail"
    domain_code, domain_name, confidence, _ = infer_domain(context)
    assert domain_code == "trade"
    assert domain_name == "交易域"
    assert confidence >= 0.7

    subject_code, subject_name, subject_confidence, _ = infer_subject(domain_code, context)
    assert subject_code == "order"
    assert subject_name == "订单主题"
    assert subject_confidence >= 0.7


def test_payment_and_refund_subjects():
    assert infer_subject("trade", "dwd_trade_payment_detail 支付明细")[1] == "支付主题"
    assert infer_subject("trade", "dwd_trade_refund_detail 退款明细")[1] == "退款主题"


def test_unknown_classification_is_explicit():
    assert infer_layer("foo.bar_baz")[0] == "UNKNOWN"
    assert infer_domain("foo bar baz")[0] == "unknown"
