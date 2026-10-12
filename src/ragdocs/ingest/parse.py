"""Document parsing and Markdown/MDX cleaning for LangGraph documentation."""

import re
from dataclasses import dataclass
from pathlib import Path

import frontmatter


@dataclass(frozen=True)
class ParsedDocument:
    """A parsed and cleaned documentation document."""

    doc_path: str
    title: str
    public_url: str
    body: str


def clean_markdown_body(raw_text: str) -> tuple[str, str]:
    """Clean frontmatter, MDX constructs, conditionals, images, and links.

    Returns:
        (title, cleaned_body): Extracted title and cleaned Markdown content.
    """
    post = frontmatter.loads(raw_text)
    frontmatter_title = post.get("title")
    title = str(frontmatter_title).strip() if frontmatter_title else ""
    content = post.content

    # Remove MDX import and export lines
    lines = content.splitlines()
    filtered_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("import ") and ("from " in stripped or ";" in stripped):
            continue
        if stripped.startswith("export "):
            continue
        filtered_lines.append(line)
    content = "\n".join(filtered_lines)

    # If title not found in frontmatter, find the first H1
    if not title:
        for line in filtered_lines:
            if line.startswith("# "):
                title = line[2:].strip()
                break

    # Strip :::js and :::javascript blocks (must end with ::: on its own line)
    content = re.sub(
        r"(?m)^[ \t]*:::(?:js|javascript)\b[\s\S]*?^[ \t]*:::[ \t]*$\n?",
        "",
        content,
    )

    # Unwrap :::python blocks (keep content without :::python and ::: markers)
    content = re.sub(
        r"(?m)^[ \t]*:::python\b[ \t]*\n?([\s\S]*?)^[ \t]*:::[ \t]*$\n?",
        r"\1",
        content,
    )

    # Protect code fences before removing JSX components, images, and links
    code_blocks: list[str] = []

    def save_code_block(match: re.Match[str]) -> str:
        code_blocks.append(match.group(0))
        return f"__DOCS_CODE_BLOCK_{len(code_blocks) - 1}__"

    content = re.sub(r"(```[\s\S]*?```)", save_code_block, content)

    # Remove Markdown images: ![alt](url)
    content = re.sub(r"!\[.*?\]\(.*?\)", "", content)

    # Convert Markdown links to plain text: [anchor text](url) -> anchor text
    content = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", content)

    # Remove self-closing JSX components: <Icon ... /> or <ConnectDocsMcpPrompt />
    content = re.sub(r"<[A-Za-z0-9._]+\b[^>]*\/>", "", content)

    # Remove JSX wrapper tags but keep inner text: <CodeGroup>, </CodeGroup>, etc.
    content = re.sub(r"<\/?[A-Za-z0-9._]+(?:\s+[^>]*)?>", "", content)

    # Restore code fences verbatim
    for i, cb in enumerate(code_blocks):
        content = content.replace(f"__DOCS_CODE_BLOCK_{i}__", cb)

    return title, content.strip()


def parse_file(file_path: Path, docs_root: Path, base_url: str) -> ParsedDocument:
    """Parse a single Markdown or MDX file into a ParsedDocument."""
    p = Path(file_path).resolve()
    root = Path(docs_root).resolve()
    rel_path = p.relative_to(root).as_posix()

    doc_stem = rel_path.rsplit(".", 1)[0]
    public_url = f"{base_url.rstrip('/')}/{doc_stem}"

    raw_text = p.read_text(encoding="utf-8")
    title, body = clean_markdown_body(raw_text)

    return ParsedDocument(
        doc_path=rel_path,
        title=title,
        public_url=public_url,
        body=body,
    )


def list_in_scope_files(docs_root: Path) -> list[Path]:
    """Find all in-scope Markdown/MDX documentation files under docs_root."""
    root = Path(docs_root).resolve()
    all_files = sorted(list(root.rglob("*.mdx")) + list(root.rglob("*.md")))
    in_scope: list[Path] = []
    for f in all_files:
        name_lower = f.name.lower()
        if "changelog" in name_lower:
            continue
        in_scope.append(f)
    return in_scope
