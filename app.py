from pathlib import Path

import streamlit as st

from audit import append_audit_log, create_audit_entry
from config import get_settings
from rag import BankRAGService
from router import route_query


PROJECT_ROOT = Path(__file__).parent
KNOWLEDGE_BASE_DIR = PROJECT_ROOT / "knowledge_base"


@st.cache_resource(show_spinner=False)
def get_rag_service() -> BankRAGService:
    return BankRAGService(get_settings(), KNOWLEDGE_BASE_DIR)


def init_session_state() -> None:
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("audit_logs", [])


def render_sidebar(service: BankRAGService) -> None:
    settings = get_settings()
    st.sidebar.header("Demo 狀態")
    st.sidebar.write(f"模式：`{settings.runtime_mode_label}`")
    st.sidebar.write(f"LLM Base URL：`{settings.llm_base_url or 'not-set'}`")
    st.sidebar.write(f"Chat Model：`{settings.llm_chat_model}`")
    st.sidebar.write(f"Embedding Model：`{settings.llm_embedding_model}`")
    st.sidebar.write(f"API Key：`{settings.masked_api_key}`")
    st.sidebar.write(f"知識文件數：`{len(service.documents)}`")
    st.sidebar.write(f"檢索策略：`{service.retrieval_backend_label}`")
    if service.embedding_error:
        st.sidebar.warning("Embedding 發生錯誤，系統已自動切回本地 embedding fallback。")
    if service.chat_error:
        st.sidebar.warning("Chat API 發生錯誤，系統已自動切回 mock response。")

    st.sidebar.divider()
    st.sidebar.caption("此介面僅供 PoC / 面試 demo 使用，不代表正式銀行系統。")


def render_audit_logs() -> None:
    st.subheader("Audit Log")
    if not st.session_state["audit_logs"]:
        st.info("目前還沒有互動紀錄。")
        return

    for entry in st.session_state["audit_logs"]:
        with st.expander(f"{entry.timestamp} | {entry.route} | {entry.response_type}"):
            st.write(f"使用者問題：{entry.question}")
            st.write(f"是否有檢索到文件：{entry.has_retrieval}")


def main() -> None:
    st.set_page_config(
        page_title="銀行 AI 客服 PoC Demo",
        page_icon="🏦",
        layout="wide",
    )
    init_session_state()
    service = get_rag_service()

    st.title("銀行 AI 客服 PoC Demo")
    st.warning(
        "這是一個面試展示用概念驗證 PoC，不是正式銀行產品。"
        "不連接真實帳務系統，也沒有真實身份驗證。"
    )
    st.caption(
        "展示重點：LangChain 最小 RAG、rule-based 風險分流、"
        "以及簡單 audit log。高風險問題會直接要求人工處理。"
    )

    render_sidebar(service)

    left, right = st.columns([2, 1])

    with left:
        st.subheader("客服對話")
        for message in st.session_state["messages"]:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                for source in message.get("sources", []):
                    st.caption(
                        f"來源：{source['source']} | chunk #{source['chunk_id']} | score={source['score']}"
                    )
                    st.code(source["snippet"], language="markdown")

        user_question = st.chat_input("請輸入問題，例如：信用卡帳單怎麼查？")
        if user_question:
            st.session_state["messages"].append(
                {"role": "user", "content": user_question, "sources": []}
            )
            with st.chat_message("user"):
                st.markdown(user_question)

            decision = route_query(user_question)
            if decision.route == "high-risk":
                answer = (
                    "這類問題被判定為高風險情境，PoC 不會自動提供操作或判斷。"
                    "請改由人工客服或完成身份驗證後再處理。"
                )
                response_type = "escalate_to_human"
                sources = []
                has_retrieval = False
            else:
                rag_result = service.answer_low_risk_question(user_question)
                answer = rag_result.answer
                response_type = rag_result.response_type
                sources = rag_result.sources
                has_retrieval = rag_result.has_retrieval

            assistant_message = {
                "role": "assistant",
                "content": f"{answer}\n\n路由說明：{decision.reason}",
                "sources": sources,
            }
            st.session_state["messages"].append(assistant_message)
            append_audit_log(
                st.session_state["audit_logs"],
                create_audit_entry(
                    question=user_question,
                    route=decision.route,
                    has_retrieval=has_retrieval,
                    response_type=response_type,
                ),
            )
            st.rerun()

    with right:
        render_audit_logs()


if __name__ == "__main__":
    main()
