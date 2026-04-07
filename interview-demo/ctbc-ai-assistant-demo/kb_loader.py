from pathlib import Path
from typing import List

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


def load_knowledge_base(path: str | Path) -> List[Document]:
    base_path = Path(path)
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=280,
        chunk_overlap=40,
        separators=["\n## ", "\n### ", "\n", "。", "，", " "],
    )
    documents: List[Document] = []

    for file_path in sorted(base_path.glob("*.md")):
        content = file_path.read_text(encoding="utf-8").strip()
        if not content:
            continue
        source_name = file_path.name
        raw_document = Document(
            page_content=content,
            metadata={"source": source_name, "path": str(file_path)},
        )
        split_documents = splitter.split_documents([raw_document])
        for index, document in enumerate(split_documents, start=1):
            document.metadata["chunk_id"] = index
            documents.append(document)

    return documents
