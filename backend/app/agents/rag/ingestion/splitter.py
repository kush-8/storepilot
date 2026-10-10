"""Structure-first Markdown splitting with bounded, overlapping section chunks."""

import re
from collections.abc import Sequence

from langchain_core.documents import BaseDocumentTransformer, Document
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter


class PolicySectionSplitter(BaseDocumentTransformer):
    chunk_size = 1000
    chunk_overlap = 150
    fingerprint = "langchain-markdown-h2-recursive-chars-1000-overlap-150-v2"

    def transform_documents(self, documents: Sequence[Document], **kwargs) -> list[Document]:
        splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[("##", "heading")],
            strip_headers=False,
        )
        sections: list[Document] = []
        seen: set[str] = set()
        for document in documents:
            lines = document.page_content.splitlines()
            source = re.search(r"^Source ID:\s*(\S+)", document.page_content, re.MULTILINE)
            title = next((line[2:].strip() for line in lines if line.startswith("# ")), None)
            chunks = [
                chunk
                for chunk in splitter.split_text(document.page_content)
                if "heading" in chunk.metadata
            ]
            if not source or not title or not chunks:
                raise ValueError(
                    "Policy requires a title, Source ID and ## sections: "
                    + document.metadata["filename"]
                )
            # Source offsets are not emitted by MarkdownHeaderTextSplitter. Resolve its
            # headings to the original text so citation excerpts preserve whitespace.
            starts: dict[str, int] = {}
            fence: str | None = None
            for number, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith(("```", "~~~")):
                    marker = stripped[:3]
                    fence = None if fence == marker else marker if fence is None else fence
                if fence is None and line.startswith("## "):
                    heading = line[3:].strip()
                    if heading in starts:
                        raise ValueError(f"Empty or duplicate policy section: {heading}")
                    starts[heading] = number
            boundaries = sorted(starts.values()) + [len(lines)]
            for chunk in chunks:
                heading = chunk.metadata["heading"]
                start = starts[heading]
                end = boundaries[boundaries.index(start) + 1]
                body = "\n".join(lines[start + 1 : end]).strip()
                slug = re.sub(r"[^a-z0-9]+", "-", heading.lower()).strip("-")
                section_id = f"{source[1]}:{slug}"
                if not slug or not body or section_id in seen:
                    raise ValueError(f"Empty or duplicate policy section: {section_id}")
                seen.add(section_id)
                sections.append(
                    Document(
                        id=section_id,
                        page_content=body,
                        metadata={
                            **document.metadata,
                            "section_id": section_id,
                            "source_id": source[1],
                            "title": title,
                            "heading": heading,
                            "heading_slug": slug,
                            "line_start": start + 1,
                            "line_end": end,
                        },
                    )
                )
        # Split each heading group independently: overlap never crosses policy sections.
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", " ", ""],
            add_start_index=True,
        )
        results: list[Document] = []
        for section in sections:
            chunks = text_splitter.split_documents([section])
            for index, chunk in enumerate(chunks):
                parent_id = section.metadata["section_id"]
                chunk_id = parent_id if len(chunks) == 1 else f"{parent_id}:chunk-{index + 1}"
                start_index = chunk.metadata.pop("start_index")
                if start_index < 0:
                    raise ValueError(f"Cannot resolve chunk to source section: {parent_id}")
                results.append(
                    Document(
                        id=chunk_id,
                        page_content=chunk.page_content,
                        metadata={
                            **chunk.metadata,
                            "section_id": chunk_id,
                            "parent_section_id": parent_id,
                            "chunk_index": index,
                            "chunk_count": len(chunks),
                            "chunk_start": start_index,
                            "chunk_end": start_index + len(chunk.page_content),
                        },
                    )
                )
        return results
