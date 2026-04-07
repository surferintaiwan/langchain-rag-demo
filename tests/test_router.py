from router import route_query


def test_route_query_flags_high_risk_transfer() -> None:
    decision = route_query("請幫我把 10 萬轉帳到別的帳戶")

    assert decision.route == "high-risk"
    assert any("轉帳" in rule for rule in decision.matched_rules)


def test_route_query_defaults_to_low_risk() -> None:
    decision = route_query("信用卡帳單怎麼查？")

    assert decision.route == "low-risk"
    assert decision.matched_rules == ["default_low_risk_faq"]


def test_route_query_keeps_transfer_fee_faq_low_risk() -> None:
    decision = route_query("跨行轉帳手續費怎麼算？")

    assert decision.route == "low-risk"
    assert decision.matched_rules == ["transfer_fee_faq_exception"]
