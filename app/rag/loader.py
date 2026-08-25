import re
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

class DocumentChunk:
    """Represents a single parsed chunk of a Markdown document with front-matter metadata."""
    def __init__(
        self,
        source_filename: str,
        document_id: Optional[str],
        title: Optional[str],
        heading: str,
        text: str,
        status: str,
        policy_authority: str,
        audience: str,
        effective_date: Optional[Any] = None,
        last_reviewed: Optional[Any] = None,
        supersedes: Optional[Any] = None,
        customer_answering: bool = True
    ):
        self.source_filename = source_filename
        self.document_id = str(document_id) if document_id is not None else None
        self.title = str(title) if title is not None else None
        self.heading = heading
        self.text = text.strip()
        self.status = str(status)
        self.policy_authority = str(policy_authority)
        self.audience = str(audience)
        self.effective_date = str(effective_date) if effective_date is not None else None
        self.last_reviewed = str(last_reviewed) if last_reviewed is not None else None
        self.supersedes = str(supersedes) if supersedes is not None else None
        self.customer_answering = bool(customer_answering)

class DocumentLoader:
    """Discovers and parses Markdown files under the knowledge base directory."""
    def __init__(self, kb_directory: str | Path):
        self.kb_directory = Path(kb_directory)

    def load_documents(self) -> List[DocumentChunk]:
        """Loads and parses all Markdown documents in the knowledge base directory."""
        if not self.kb_directory.exists():
            raise FileNotFoundError(f"Knowledge base directory not found: {self.kb_directory}")

        chunks: List[DocumentChunk] = []
        for file_path in sorted(self.kb_directory.glob("*.md")):
            chunks.extend(self._parse_file(file_path))
        return chunks

    def _parse_file(self, file_path: Path) -> List[DocumentChunk]:
        content = file_path.read_text(encoding="utf-8")
        filename = file_path.name

        # Parse YAML front matter
        metadata: Dict[str, Any] = {}
        body = content
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                try:
                    parsed = yaml.safe_load(parts[1])
                    if isinstance(parsed, dict):
                        metadata = parsed
                except Exception:
                    metadata = {}
                body = parts[2]

        document_id = metadata.get("document_id")
        title = metadata.get("title")
        status = metadata.get("status", "unknown")
        policy_authority = metadata.get("policy_authority", "official")
        audience = metadata.get("audience", "customer")
        effective_date = metadata.get("effective_date")
        last_reviewed = metadata.get("last_reviewed")
        supersedes = metadata.get("supersedes")
        customer_answering = metadata.get("customer_answering", True)

        # Parse Markdown body into chunks based on headings
        file_chunks: List[DocumentChunk] = []
        lines = body.split("\n")

        current_heading = title or filename
        current_lines: List[str] = []

        for line in lines:
            heading_match = re.match(r"^(#{1,6})\s+(.+)$", line.strip())
            if heading_match:
                text_block = "\n".join(current_lines).strip()
                if text_block:
                    file_chunks.append(
                        DocumentChunk(
                            source_filename=filename,
                            document_id=document_id,
                            title=title,
                            heading=current_heading,
                            text=text_block,
                            status=status,
                            policy_authority=policy_authority,
                            audience=audience,
                            effective_date=effective_date,
                            last_reviewed=last_reviewed,
                            supersedes=supersedes,
                            customer_answering=customer_answering
                        )
                    )
                current_heading = heading_match.group(2).strip()
                current_lines = []
            else:
                current_lines.append(line)

        text_block = "\n".join(current_lines).strip()
        if text_block:
            file_chunks.append(
                DocumentChunk(
                    source_filename=filename,
                    document_id=document_id,
                    title=title,
                    heading=current_heading,
                    text=text_block,
                    status=status,
                    policy_authority=policy_authority,
                    audience=audience,
                    effective_date=effective_date,
                    last_reviewed=last_reviewed,
                    supersedes=supersedes,
                    customer_answering=customer_answering
                )
            )

        return file_chunks
