from pathlib import Path

from config import Settings
from rag import BankRAGService


PROJECT_ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_BASE_DIR = PROJECT_ROOT / "knowledge_base"


def test_rag_returns_answer_for_supported_question() -> None:
    service = BankRAGService(Settings(), KNOWLEDGE_BASE_DIR)

    result = service.answer_low_risk_question("信用卡帳單怎麼查？")

    assert result.response_type == "rag_answer"
    assert result.has_retrieval is True
    assert result.sources


def test_rag_falls_back_for_unknown_question() -> None:
    service = BankRAGService(Settings(), KNOWLEDGE_BASE_DIR)

    result = service.answer_low_risk_question("你們的企業信託海外稅務方案細節是什麼？")

    assert result.response_type == "fallback"
    assert result.has_retrieval is False
