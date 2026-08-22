"""
MemoraGraph – Document Metadata Extraction

Enriches extracted file metadata with heuristic content analysis
to identify department, project, author, date, and document type.
"""

import logging
import re
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# Heuristic department keywords
DEPARTMENT_PATTERNS = {
    "Engineering": [r"\bengineer\b", r"\btechnical\b", r"\bdevops\b", r"\bsoftware\b", r"\barchitecture\b"],
    "Finance": [r"\bfinance\b", r"\bbudget\b", r"\bcost\b", r"\bexpenditure\b", r"\baccounting\b"],
    "HR": [r"\bhuman resources\b", r"\bhr\b", r"\brecruit\b", r"\bonboard\b", r"\bemployee\b"],
    "Management": [r"\bmanagement\b", r"\bleadership\b", r"\bexecutive\b", r"\bstrategy\b"],
    "Security": [r"\bsecurity\b", r"\bcybersecurity\b", r"\bincident\b", r"\bvulnerability\b"],
    "Operations": [r"\boperations\b", r"\binfrastructure\b", r"\bdeployment\b", r"\bproduction\b"],
    "Legal": [r"\blegal\b", r"\bcompliance\b", r"\baudit\b", r"\bregulatory\b"],
    "Marketing": [r"\bmarketing\b", r"\bcampaign\b", r"\bbrand\b", r"\bcustomer\b"],
}

# Document type detection patterns
DOC_TYPE_PATTERNS = {
    "Meeting Notes": [r"\bmeeting\b", r"\bminutes\b", r"\bagenda\b", r"\battendees\b"],
    "Project Report": [r"\bproject report\b", r"\bprogress report\b", r"\bstatus report\b"],
    "Risk Assessment": [r"\brisk\b", r"\bassessment\b", r"\bmitigation\b", r"\bimpact\b"],
    "Decision Record": [r"\bdecision\b", r"\bapproved\b", r"\bresolution\b", r"\bapproval\b"],
    "Technical Specification": [r"\bspecification\b", r"\barchitecture\b", r"\bdesign doc\b", r"\bspec\b"],
    "Incident Report": [r"\bincident\b", r"\boutage\b", r"\bpostmortem\b", r"\broot cause\b"],
    "Policy": [r"\bpolicy\b", r"\bprocedure\b", r"\bguideline\b", r"\bcompliance\b"],
}

# Date patterns
DATE_PATTERNS = [
    r"\b(\d{4}-\d{2}-\d{2})\b",
    r"\b(\d{1,2}/\d{1,2}/\d{4})\b",
    r"\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})\b",
    r"\b(?:Date|dated|on)[:.]?\s*([A-Z][a-z]+\s+\d{1,2},?\s*\d{4})\b",
]

# Project name patterns
PROJECT_PATTERNS = [
    r"\bProject\s+([A-Z][A-Za-z0-9\s]+?)(?:\s*[-:]|\s*\n|\s*\.|$)",
    r"\b(?:for|regarding|re:)\s+([A-Z][A-Za-z0-9\s]+?)\s+[Pp]roject\b",
]


def enrich_metadata(
    filename: str,
    extracted_metadata: dict,
    text_sample: str,
) -> dict:
    """
    Merge file-level metadata with content-inferred metadata.
    
    Args:
        filename: Original filename
        extracted_metadata: Metadata from extractor (author, title, etc.)
        text_sample: First ~2000 chars of document text for heuristics
    
    Returns:
        Enriched metadata dict
    """
    sample = text_sample[:2000].lower()
    sample_raw = text_sample[:2000]

    result = dict(extracted_metadata)

    # Fill in from filename if not present
    if not result.get("title"):
        stem = re.sub(r"[_\-]+", " ", filename.rsplit(".", 1)[0]).title()
        result["title"] = stem

    # Detect department
    if not result.get("department"):
        result["department"] = _detect_department(sample)

    # Detect document type
    if not result.get("doc_type"):
        result["doc_type"] = _detect_doc_type(sample)

    # Detect date
    if not result.get("doc_date"):
        result["doc_date"] = _detect_date(sample_raw)

    # Detect project
    if not result.get("project"):
        result["project"] = _detect_project(sample_raw)

    result["filename"] = filename
    return {k: v for k, v in result.items() if v}


def _detect_department(text_lower: str) -> Optional[str]:
    for dept, patterns in DEPARTMENT_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return dept
    return None


def _detect_doc_type(text_lower: str) -> Optional[str]:
    for doc_type, patterns in DOC_TYPE_PATTERNS.items():
        matches = sum(1 for p in patterns if re.search(p, text_lower, re.IGNORECASE))
        if matches >= 2:  # require at least 2 pattern matches for confidence
            return doc_type
    return "Document"


def _detect_date(text: str) -> Optional[str]:
    for pattern in DATE_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def _detect_project(text: str) -> Optional[str]:
    for pattern in PROJECT_PATTERNS:
        match = re.search(pattern, text)
        if match:
            name = match.group(1).strip()
            if 2 < len(name) < 100:
                return name
    return None
