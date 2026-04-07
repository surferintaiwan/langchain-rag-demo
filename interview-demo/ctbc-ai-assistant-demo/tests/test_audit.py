from audit import append_audit_log, create_audit_entry


def test_append_audit_log_keeps_required_fields() -> None:
    logs = []
    entry = create_audit_entry(
        question="信用卡帳單怎麼查？",
        route="low-risk",
        has_retrieval=True,
        response_type="rag_answer",
    )

    append_audit_log(logs, entry)

    assert len(logs) == 1
    assert logs[0].question == "信用卡帳單怎麼查？"
    assert logs[0].route == "low-risk"
    assert logs[0].has_retrieval is True
    assert logs[0].response_type == "rag_answer"
