from typing import List

from pydantic import BaseModel


TRANSFER_INFO_KEYWORDS = [
    "手續費",
    "費率",
    "費用",
    "如何計算",
    "怎麼算",
    "怎麼收",
]

HIGH_RISK_RULES = {
    "transfer_or_payment_change": [
        "轉帳",
        "匯款",
        "轉到",
        "轉出",
        "付款給",
        "代轉",
    ],
    "limit_or_credit_adjustment": [
        "額度調整",
        "提高額度",
        "調高額度",
        "信用額度",
        "臨時額度",
        "永久額度",
    ],
    "sensitive_personal_data": [
        "身分證",
        "身份證",
        "帳號",
        "卡號",
        "cvv",
        "安全碼",
        "otp",
        "驗證碼",
        "密碼",
        "出生日期",
        "個資",
    ],
    "complaint_or_dispute": [
        "申訴",
        "客訴",
        "抱怨",
        "爭議款",
        "爭議交易",
        "退款爭議",
    ],
    "card_block_or_loss": [
        "停卡",
        "掛失",
        "卡片遺失",
        "卡片被盜",
        "卡片不見",
    ],
}


class RouteDecision(BaseModel):
    route: str
    matched_rules: List[str]
    reason: str


def route_query(question: str) -> RouteDecision:
    normalized = question.lower().strip()
    matched_rules: List[str] = []

    if "轉帳" in normalized and any(keyword in normalized for keyword in TRANSFER_INFO_KEYWORDS):
        return RouteDecision(
            route="low-risk",
            matched_rules=["transfer_fee_faq_exception"],
            reason="問題是在詢問轉帳手續費或費率資訊，視為低風險 FAQ。",
        )

    for rule_name, keywords in HIGH_RISK_RULES.items():
        for keyword in keywords:
            if keyword.lower() in normalized:
                matched_rules.append(f"{rule_name}:{keyword}")

    if matched_rules:
        return RouteDecision(
            route="high-risk",
            matched_rules=matched_rules,
            reason="問題涉及資金操作、敏感個資、申訴或需身份驗證的情境，PoC 不自動回答。",
        )

    return RouteDecision(
        route="low-risk",
        matched_rules=["default_low_risk_faq"],
        reason="視為 FAQ、產品說明或流程查詢，交由最小 RAG 流程處理。",
    )
