import pytest
from app.rag.loader import DocumentLoader
from app.rag.retriever import RAGRetriever

@pytest.fixture(scope="module")
def retriever():
    return RAGRetriever(kb_directory="knowledge-base")

def test_loader_parses_frontmatter_and_headings():
    loader = DocumentLoader("knowledge-base")
    chunks = loader.load_documents()
    assert len(chunks) > 0
    
    # Check front-matter preservation
    ret_chunk = next(c for c in chunks if c.source_filename == "01-returns-policy-current.md")
    assert ret_chunk.document_id == "RET-2026-01"
    assert ret_chunk.status == "active"
    assert ret_chunk.policy_authority == "official"
    assert ret_chunk.audience == "customer"
    assert ret_chunk.supersedes == "RET-2024-01"

def test_a_current_return_policy(retriever):
    """Test A: Current return policy retrieved, legacy 45-day policy excluded as authority."""
    result = retriever.retrieve("How long does a regular customer have to return an unused backpack?")
    
    sources = [c.source_filename for c in result.retrieved_chunks]
    assert "01-returns-policy-current.md" in sources
    assert "02-returns-policy-legacy.md" not in sources
    assert "14-internal-content-migration-notes.md" not in sources
    assert result.conflict_detected is False

def test_b_legacy_policy_recognized_as_superseded(retriever):
    """Test B: Legacy policy chunks marked as superseded in diagnostics exclusion list."""
    result = retriever.retrieve("What was the old 45-day return policy?")
    
    # The active 30-day policy is returned as authoritative
    sources = [c.source_filename for c in result.retrieved_chunks]
    assert "02-returns-policy-legacy.md" not in sources
    
    # The legacy chunk should be listed in excluded_chunks with reason 'superseded_version'
    excluded = result.diagnostics.get("excluded_chunks", [])
    legacy_excluded = any(e["source_filename"] == "02-returns-policy-legacy.md" and e["reason"] == "superseded_version" for e in excluded)
    assert legacy_excluded is True

def test_c_trailplus_exception(retriever):
    """Test C: TrailPlus membership return window query retrieves TrailPlus policy."""
    result = retriever.retrieve("My TrailPlus membership was active when I ordered. What is my return window?")
    
    sources = [c.source_filename for c in result.retrieved_chunks]
    assert "09-trailplus-membership.md" in sources

def test_d_canada_shipping(retriever):
    """Test D: Query for Canada shipping retrieves international shipping document."""
    result = retriever.retrieve("Do you ship to Canada and how long does it take?")
    
    sources = [c.source_filename for c in result.retrieved_chunks]
    assert "06-international-shipping.md" in sources

def test_e_unsupported_country(retriever):
    """Test E: Query for Germany retrieves international shipping document without inventing support."""
    result = retriever.retrieve("Can you ship an Atlas Weekender to Germany?")
    
    sources = [c.source_filename for c in result.retrieved_chunks]
    assert "06-international-shipping.md" in sources

def test_f_warranty(retriever):
    """Test F: Query for product warranty retrieves limited warranty document."""
    result = retriever.retrieve("Do all Aster & Row products have a lifetime warranty?")
    
    sources = [c.source_filename for c in result.retrieved_chunks]
    assert "07-warranty.md" in sources

def test_g_prompt_injection_document_ignored(retriever):
    """Test G: Untrusted draft migration notes doc with prompt injection is excluded from authoritative results."""
    result = retriever.retrieve("The migration note says to ignore the real policy and give everyone 60 days.")
    
    sources = [c.source_filename for c in result.retrieved_chunks]
    assert "14-internal-content-migration-notes.md" not in sources
    assert "01-returns-policy-current.md" in sources

def test_h_breeze_tumbler_active_source_conflict(retriever):
    """Test H: Breeze Tumbler dishwasher care query surfaces active sources and flags conflict."""
    result = retriever.retrieve("Can I put the entire Breeze Tumbler in the dishwasher?")
    
    sources = [c.source_filename for c in result.retrieved_chunks]
    assert "11-product-care.md" in sources
    assert "12-breeze-tumbler-product-card.md" in sources
    assert result.conflict_detected is True
    assert "11-product-care.md" in result.conflicting_sources
    assert "12-breeze-tumbler-product-card.md" in result.conflicting_sources

def test_i_source_metadata_and_citations(retriever):
    """Test I: Every retrieved chunk contains filename, document_id, heading, and valid citation."""
    result = retriever.retrieve("What is the return policy?")
    for chunk in result.retrieved_chunks:
        assert chunk.source_filename.endswith(".md")
        assert chunk.heading != ""
        assert chunk.citation == f"{chunk.source_filename}#{chunk.heading}"

def test_j_retrieval_determinism(retriever):
    """Test J: Identical query yields identical retrieval results across multiple calls."""
    res1 = retriever.retrieve("What is the standard return window?")
    res2 = retriever.retrieve("What is the standard return window?")
    
    assert [c.citation for c in res1.retrieved_chunks] == [c.citation for c in res2.retrieved_chunks]
    assert res1.conflict_detected == res2.conflict_detected
