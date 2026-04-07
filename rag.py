import hashlib
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from config import Settings
from kb_loader import load_knowledge_base
from llm_client import build_chat_model, build_embeddings


MIN_RELEVANCE_SCORE = 0.12
LOCAL_EMBEDDING_DIM = 256


class RAGResult:
    def __init__(
        self,
        answer: str,
        response_type: str,
        has_retrieval: bool,
        sources: List[dict],
        retrieval_mode: str,
    ) -> None:
        self.answer = answer
        self.response_type = response_type
        self.has_retrieval = has_retrieval
        self.sources = sources
        self.retrieval_mode = retrieval_mode


@dataclass
class RetrievedChunk:
    document: Document
    score: float


class BankRAGService:
    def __init__(self, settings: Settings, knowledge_base_dir: str | Path) -> None:
        self.settings = settings
        self.knowledge_base_dir = Path(knowledge_base_dir)
        self.documents = load_knowledge_base(self.knowledge_base_dir)
        self.chat_model = build_chat_model(settings)
        self.remote_embeddings = build_embeddings(settings)
        self.embedding_ready = False
        self.embedding_error: Optional[str] = None
        self.chat_error: Optional[str] = None
        self.document_vectors: List[List[float]] = []
        self.local_document_vectors: List[List[float]] = []
        self.keyword_terms = [self._to_search_terms(doc.page_content) for doc in self.documents]
        self.retrieval_backend_label = "keyword retrieval"

        if self.remote_embeddings:
            self._prepare_remote_embeddings()

        if not self.embedding_ready:
            self._prepare_local_embeddings()

    def answer_low_risk_question(self, question: str) -> RAGResult:
        retrieved_chunks, retrieval_mode = self._retrieve(question, top_k=3)
        has_retrieval = bool(retrieved_chunks)

        if not has_retrieval:
            return RAGResult(
                answer=(
                    "目前無法根據這個 PoC 的本地知識庫確認答案。"
                    "為避免提供不準確的銀行資訊，建議改由人工客服協助。"
                ),
                response_type="fallback",
                has_retrieval=False,
                sources=[],
                retrieval_mode=retrieval_mode,
            )

        retrieved_documents = [chunk.document for chunk in retrieved_chunks]
        sources = [
            {
                "source": chunk.document.metadata.get("source", "unknown"),
                "chunk_id": chunk.document.metadata.get("chunk_id"),
                "snippet": self._build_snippet(chunk.document.page_content),
                "score": round(chunk.score, 3),
            }
            for chunk in retrieved_chunks
        ]

        if self.chat_model:
            try:
                answer = self._generate_live_answer(question, retrieved_documents)
            except Exception as exc:
                self.chat_error = str(exc)
                answer = self._generate_mock_answer(question, retrieved_documents)
        else:
            answer = self._generate_mock_answer(question, retrieved_documents)

        return RAGResult(
            answer=answer,
            response_type="rag_answer",
            has_retrieval=True,
            sources=sources,
            retrieval_mode=retrieval_mode,
        )

    def _prepare_remote_embeddings(self) -> None:
        try:
            self.document_vectors = self.remote_embeddings.embed_documents(
                [doc.page_content for doc in self.documents]
            )
            self.embedding_ready = True
            self.retrieval_backend_label = "remote embedding retrieval"
        except Exception as exc:
            self.embedding_ready = False
            self.embedding_error = str(exc)
            self.document_vectors = []

    def _prepare_local_embeddings(self) -> None:
        self.local_document_vectors = [
            self._local_embed_text(doc.page_content) for doc in self.documents
        ]
        self.embedding_ready = True
        if self.embedding_error:
            self.retrieval_backend_label = "local embedding fallback"
        else:
            self.retrieval_backend_label = "local embedding retrieval"

    def _retrieve(self, question: str, top_k: int = 3) -> Tuple[List[RetrievedChunk], str]:
        if self.remote_embeddings and self.document_vectors:
            try:
                query_vector = self.remote_embeddings.embed_query(question)
                ranked = []
                for vector, document in zip(self.document_vectors, self.documents):
                    score = self._cosine_similarity(query_vector, vector)
                    ranked.append(RetrievedChunk(document=document, score=score))
                ranked.sort(key=lambda item: item.score, reverse=True)
                filtered = [item for item in ranked if item.score >= MIN_RELEVANCE_SCORE]
                return filtered[:top_k], "embedding"
            except Exception as exc:
                self.embedding_error = str(exc)
                self.document_vectors = []
                self._prepare_local_embeddings()

        if self.local_document_vectors:
            query_vector = self._local_embed_text(question)
            ranked = []
            for vector, document in zip(self.local_document_vectors, self.documents):
                score = self._cosine_similarity(query_vector, vector)
                ranked.append(RetrievedChunk(document=document, score=score))
            ranked.sort(key=lambda item: item.score, reverse=True)
            filtered = [item for item in ranked if item.score >= MIN_RELEVANCE_SCORE]
            if filtered:
                return filtered[:top_k], "local_embedding"
            self.retrieval_backend_label = "keyword retrieval fallback"

        ranked = []
        query_terms = self._to_search_terms(question)
        for terms, document in zip(self.keyword_terms, self.documents):
            score = self._keyword_score(question, query_terms, document.page_content, terms)
            ranked.append(RetrievedChunk(document=document, score=score))
        ranked.sort(key=lambda item: item.score, reverse=True)
        filtered = [item for item in ranked if item.score >= MIN_RELEVANCE_SCORE]
        self.embedding_ready = False
        return filtered[:top_k], "keyword"

    def _generate_live_answer(self, question: str, documents: Sequence[Document]) -> str:
        context = "\n\n".join(
            f"[來源 {index}] {doc.metadata.get('source')}：{doc.page_content}"
            for index, doc in enumerate(documents, start=1)
        )
        prompt = ChatPromptTemplate.from_template(
            """
你是銀行 AI 客服 PoC 的保守型回答助手。
只能依據提供的 FAQ 內容回答，不能編造不存在的銀行政策、費率或個資流程。
如果資訊不足，請明確說明「目前無法確認」，並建議人工客服協助。
回答請使用繁體中文，保持簡潔。

使用者問題：
{question}

可用知識：
{context}
"""
        )
        chain = prompt | self.chat_model | StrOutputParser()
        answer = chain.invoke({"question": question, "context": context}).strip()
        if "無法確認" not in answer and "建議" not in answer:
            answer = f"{answer}\n\n若需進一步確認最新規則，建議仍以人工客服或正式公告為準。"
        return answer

    def _generate_mock_answer(self, question: str, documents: Sequence[Document]) -> str:
        lead = documents[0]
        return (
            f"這是 mock mode 的整理結果。根據 `{lead.metadata.get('source', 'unknown')}` "
            f"與相關 FAQ，本題可先參考：\n\n{self._build_snippet(lead.page_content, limit=160)}\n\n"
            "這個回答僅依據本地知識文件整理，若涉及最新費率、資格或例外情況，"
            "建議再由人工客服確認。"
        )

    @staticmethod
    def _cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
        numerator = sum(a * b for a, b in zip(left, right))
        left_norm = math.sqrt(sum(a * a for a in left))
        right_norm = math.sqrt(sum(b * b for b in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return numerator / (left_norm * right_norm)

    @staticmethod
    def _build_snippet(text: str, limit: int = 120) -> str:
        compact = " ".join(text.split())
        if len(compact) <= limit:
            return compact
        return f"{compact[:limit].rstrip()}..."

    def _local_embed_text(self, text: str) -> List[float]:
        vector = [0.0] * LOCAL_EMBEDDING_DIM
        for term in self._to_search_terms(text):
            digest = hashlib.md5(term.encode("utf-8")).digest()
            index = int.from_bytes(digest[:2], "big") % LOCAL_EMBEDDING_DIM
            sign = 1.0 if digest[2] % 2 == 0 else -1.0
            weight = 1.0 + min(len(term), 4) * 0.2
            vector[index] += sign * weight
        return vector

    @staticmethod
    def _to_search_terms(text: str) -> set[str]:
        normalized = re.sub(r"\s+", "", text.lower())
        chinese_only = re.sub(r"[^\u4e00-\u9fff]", "", normalized)
        english_terms = set(re.findall(r"[a-z0-9]{2,}", normalized))
        bigrams = {
            chinese_only[index : index + 2]
            for index in range(max(len(chinese_only) - 1, 0))
            if len(chinese_only[index : index + 2]) == 2
        }
        return bigrams | english_terms

    def _keyword_score(
        self,
        question: str,
        query_terms: set[str],
        content: str,
        content_terms: set[str],
    ) -> float:
        if not query_terms:
            return 0.0
        overlap = len(query_terms & content_terms)
        coverage = overlap / max(len(query_terms), 1)
        direct_hit_bonus = 0.0
        compact_question = re.sub(r"\s+", "", question.lower())
        compact_content = re.sub(r"\s+", "", content.lower())
        if compact_question and compact_question in compact_content:
            direct_hit_bonus += 0.4
        key_phrases = [term for term in query_terms if len(term) >= 2]
        phrase_hits = sum(1 for phrase in key_phrases if phrase in compact_content)
        phrase_bonus = min(phrase_hits * 0.04, 0.3)
        return coverage + direct_hit_bonus + phrase_bonus
