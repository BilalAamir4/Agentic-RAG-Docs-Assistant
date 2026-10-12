"""Chunking logic for LangGraph documentation pages."""

import hashlib
import math
import re
from dataclasses import dataclass

from ragdocs.ingest.parse import ParsedDocument
from ragdocs.schemas import Chunk


def count_tokens(text: str) -> int:
    """Calculate token count approximation using ceil(len(text) / 4).

    This approximation estimates 1 token per 4 characters of UTF-8 text,
    providing a fast and deterministic token metric without external tokenizer overhead.
    """
    return math.ceil(len(text) / 4)


def slugify_heading(text: str) -> str:
    """Generate anchor slug matching the Mintlify documentation convention."""
    cleaned = re.sub(r"<[^>]+>", "", text).lower()
    cleaned = re.sub(r"[^\w\s-]", "", cleaned)
    return re.sub(r"[\s_]+", "-", cleaned).strip("-")


@dataclass
class RawSection:
    """An unchunked section of a documentation page."""

    heading_path: list[str]
    anchor: str
    text: str
    parent_heading: str | None


def split_page_into_sections(cleaned_body: str) -> list[RawSection]:
    """Split cleaned page Markdown into raw sections along H2 and H3 headings."""
    lines = cleaned_body.splitlines()
    sections: list[RawSection] = []
    current_h2: str | None = None
    current_heading_path: list[str] = []
    current_lines: list[str] = []
    in_code_fence = False
    slug_counts: dict[str, int] = {}

    def compute_anchor(h_text: str) -> str:
        base_slug = slugify_heading(h_text)
        count = slug_counts.get(base_slug, 0) + 1
        slug_counts[base_slug] = count
        return base_slug if count == 1 else f"{base_slug}-{count}"

    current_anchor = ""
    current_parent: str | None = None

    for line in lines:
        if line.strip().startswith("```"):
            in_code_fence = not in_code_fence
            current_lines.append(line)
            continue

        if not in_code_fence:
            if line.startswith("## "):
                prev_text = "\n".join(current_lines).strip()
                if prev_text or current_heading_path:
                    sections.append(
                        RawSection(
                            current_heading_path,
                            current_anchor,
                            prev_text,
                            current_parent,
                        )
                    )
                h2_text = line[3:].strip()
                current_h2 = h2_text
                current_heading_path = [h2_text]
                current_anchor = compute_anchor(h2_text)
                current_parent = None
                current_lines = []
                continue
            if line.startswith("### "):
                prev_text = "\n".join(current_lines).strip()
                if prev_text or current_heading_path:
                    sections.append(
                        RawSection(
                            current_heading_path,
                            current_anchor,
                            prev_text,
                            current_parent,
                        )
                    )
                h3_text = line[4:].strip()
                current_heading_path = [current_h2, h3_text] if current_h2 else [h3_text]
                current_anchor = compute_anchor(h3_text)
                current_parent = current_h2
                current_lines = []
                continue

        current_lines.append(line)

    final_text = "\n".join(current_lines).strip()
    if final_text or current_heading_path:
        sections.append(
            RawSection(current_heading_path, current_anchor, final_text, current_parent)
        )

    return [s for s in sections if s.text]


def merge_tiny_sections(sections: list[RawSection]) -> list[RawSection]:
    """Merge sections under 80 tokens into adjacent sections per rule d."""
    i = 0
    while i < len(sections):
        if count_tokens(sections[i].text) < 80:
            following_idx = None
            for j in range(i + 1, len(sections)):
                if sections[j].parent_heading == sections[i].parent_heading:
                    following_idx = j
                    break

            if following_idx is not None and following_idx == i + 1:
                sections[i + 1].text = sections[i].text + "\n\n" + sections[i + 1].text
                sections.pop(i)
                continue
            if i > 0:
                sections[i - 1].text = sections[i - 1].text + "\n\n" + sections[i].text
                sections.pop(i)
                continue
            if following_idx is not None:
                combined_text = sections[i].text + "\n\n" + sections[following_idx].text
                sections[following_idx].text = combined_text
                sections.pop(i)
                continue
            if len(sections) > 1 and i == 0:
                sections[1].text = sections[0].text + "\n\n" + sections[1].text
                sections.pop(0)
                continue
            i += 1
        else:
            i += 1
    return sections


def split_section_paragraphs(text: str) -> list[str]:
    """Split section text into paragraphs without breaking inside code fences."""
    lines = text.splitlines()
    paragraphs: list[str] = []
    current_lines: list[str] = []
    in_code = False

    for line in lines:
        if line.strip().startswith("```"):
            if not in_code:
                if current_lines:
                    paragraphs.append("\n".join(current_lines))
                    current_lines = []
                in_code = True
                current_lines.append(line)
            else:
                in_code = False
                current_lines.append(line)
                paragraphs.append("\n".join(current_lines))
                current_lines = []
            continue

        if in_code:
            current_lines.append(line)
        else:
            if not line.strip():
                if current_lines:
                    paragraphs.append("\n".join(current_lines))
                    current_lines = []
            else:
                current_lines.append(line)

    if current_lines:
        paragraphs.append("\n".join(current_lines))

    return [p.strip() for p in paragraphs if p.strip()]


def split_into_pieces(section: RawSection) -> list[str]:
    """Split a section over 450 tokens at paragraph boundaries."""
    if count_tokens(section.text) <= 450:
        return [section.text]

    paragraphs = split_section_paragraphs(section.text)
    pieces: list[str] = []
    current_piece: list[str] = []

    for p in paragraphs:
        p_tok = count_tokens(p)
        if p.startswith("```") and p_tok > 450:
            if current_piece:
                pieces.append("\n\n".join(current_piece))
                current_piece = []
            pieces.append(p)
            continue

        if current_piece:
            combined = "\n\n".join(current_piece + [p])
            if count_tokens(combined) > 450:
                pieces.append("\n\n".join(current_piece))
                current_piece = [p]
            else:
                current_piece.append(p)
        else:
            current_piece.append(p)

    if current_piece:
        pieces.append("\n\n".join(current_piece))

    return pieces


def chunk_document(doc: ParsedDocument, source_commit: str) -> list[Chunk]:
    """Split a parsed document into structured Chunks."""
    raw_sections = split_page_into_sections(doc.body)
    merged_sections = merge_tiny_sections(raw_sections)

    chunks: list[Chunk] = []
    for sec in merged_sections:
        pieces = split_into_pieces(sec)
        for ordinal, piece_text in enumerate(pieces):
            key = f"{doc.doc_path}#{sec.anchor}#{ordinal}"
            chunk_id = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]

            if sec.heading_path:
                heading_line = " > ".join(sec.heading_path)
                embed_text = f"{doc.title} > {heading_line}\n\n{piece_text}"
            else:
                embed_text = f"{doc.title}\n\n{piece_text}"

            chunk_url = f"{doc.public_url}#{sec.anchor}" if sec.anchor else doc.public_url
            tok_count = count_tokens(piece_text)
            has_code = "```" in piece_text

            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    doc_path=doc.doc_path,
                    url=chunk_url,
                    title=doc.title,
                    heading_path=sec.heading_path,
                    anchor=sec.anchor,
                    text=piece_text,
                    embed_text=embed_text,
                    n_tokens=tok_count,
                    has_code=has_code,
                    source_commit=source_commit,
                )
            )

    return chunks
