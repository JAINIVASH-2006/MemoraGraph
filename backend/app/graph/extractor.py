"""
MemoraGraph – LLM-Based Entity & Relationship Extractor

Uses the configured LLM to extract structured organizational entities
and relationships from document text chunks.
"""

import json
import logging
import re
import uuid
from typing import Any

from app.graph.schema import VALID_NODE_TYPES, VALID_REL_TYPES

logger = logging.getLogger(__name__)

EXTRACTION_SYSTEM_PROMPT = """You are an expert organizational knowledge extractor.
Extract entities and relationships from the provided text.

ENTITY TYPES (use exactly these labels):
Employee, Department, Project, Meeting, Risk, Decision, Technology, Event, Outcome, Document, Task, Issue

RELATIONSHIP TYPES (use exactly these):
WORKS_IN, MANAGES, PART_OF, INVOLVES, HAS_RISK, APPROVED, DISCUSSED_IN, CAUSED, RESULTED_IN, ASSIGNED_TO, RELATED_TO, DEPENDS_ON, RESOLVED_BY, MENTIONED_IN

OUTPUT FORMAT (return only valid JSON, no markdown):
{
  "entities": [
    {"id": "unique_id", "type": "EntityType", "name": "Entity Name", "properties": {"key": "value"}}
  ],
  "relationships": [
    {"from_id": "id1", "from_type": "TypeA", "rel_type": "REL_TYPE", "to_id": "id2", "to_type": "TypeB", "properties": {}}
  ]
}

RULES:
- Only extract entities explicitly mentioned in the text
- Generate stable IDs by slugifying names (e.g., "project-alpha", "john-smith")
- Do not invent entities not in the text
- If no entities found, return {"entities": [], "relationships": []}
- Return ONLY the JSON object, no other text
"""


def _slugify(name: str) -> str:
    """Create a stable ID from an entity name."""
    slug = re.sub(r"[^a-zA-Z0-9\s-]", "", name.lower())
    slug = re.sub(r"\s+", "-", slug.strip())
    return slug[:64] or str(uuid.uuid4())[:8]


def _validate_and_clean(raw: dict) -> dict:
    """Validate extracted entities/relationships against the strict schema."""
    entities = []
    entity_id_map = {}
    
    # 1. Validate Entities
    for ent in raw.get("entities", []):
        ent_type = ent.get("type")
        ent_name = ent.get("name")
        
        # Enforce valid entity labels
        if ent_type not in VALID_NODE_TYPES:
            logger.debug("Rejections: Unknown entity type '%s'", ent_type)
            continue
        if not ent_name:
            logger.debug("Rejections: Empty entity name")
            continue
            
        # Ensure stable IDs
        ent_id = ent.get("id") or _slugify(ent_name)
        ent["id"] = ent_id
        
        # Clean null values from properties
        ent["properties"] = {
            k: v for k, v in ent.get("properties", {}).items() if v is not None
        }
        
        entities.append(ent)
        entity_id_map[ent_id] = ent_type

    # 2. Validate Relationships
    relationships = []
    for rel in raw.get("relationships", []):
        # Normalize alternative formats
        from_id = rel.get("from_id") or _slugify(rel.get("source", ""))
        to_id = rel.get("to_id") or _slugify(rel.get("target", ""))
        rel_type = rel.get("rel_type") or rel.get("relationship", "")
        
        # Enforce valid relationship types
        if rel_type not in VALID_REL_TYPES:
            logger.debug("Rejections: Unknown relationship type '%s'", rel_type)
            continue
            
        # Enforce source & target existence in this chunk's entity list
        if from_id not in entity_id_map or to_id not in entity_id_map:
            logger.debug("Rejections: Source '%s' or Target '%s' missing from entity set", from_id, to_id)
            continue
            
        rel["from_id"] = from_id
        rel["to_id"] = to_id
        rel["rel_type"] = rel_type
        rel["from_type"] = entity_id_map[from_id]
        rel["to_type"] = entity_id_map[to_id]
        rel["properties"] = {
            k: v for k, v in rel.get("properties", {}).items() if v is not None
        }
        
        relationships.append(rel)

    return {"entities": entities, "relationships": relationships}


def _deterministic_mock_extraction(text: str) -> dict[str, Any]:
    """Deterministic, rule-based extraction for offline development and testing."""
    entities = []
    relationships = []
    
    # 1. Projects: matches "Project <Name>"
    projects = re.findall(r"\bProject\s+([A-Z][a-zA-Z0-9]*)\b", text)
    project_set = set()
    for p in projects:
        p_name = f"Project {p}"
        p_id = _slugify(p_name)
        if p_id not in project_set:
            entities.append({
                "id": p_id,
                "type": "Project",
                "name": p_name,
                "properties": {"status": "Active"}
            })
            project_set.add(p_id)
            
    # 2. Employees: Matches common seeded names or capitalized single words
    common_names = ["Arun", "Karthik", "Priya", "John", "Sarah", "Alex", "David", "Emma"]
    employee_set = set()
    for name in common_names:
        if re.search(r"\b" + re.escape(name) + r"\b", text):
            emp_id = _slugify(name)
            if emp_id not in employee_set:
                role = "Project Manager" if name in ("Arun", "Priya") else "Software Engineer"
                entities.append({
                    "id": emp_id,
                    "type": "Employee",
                    "name": name,
                    "properties": {"role": role}
                })
                employee_set.add(emp_id)

    # 3. Departments: "Engineering", "Design", "HR", "Marketing", "Product", "Operations"
    departments = ["Engineering", "Design", "HR", "Marketing", "Product", "Operations"]
    dept_set = set()
    for dept in departments:
        if re.search(r"\b" + re.escape(dept) + r"\b", text, re.IGNORECASE):
            d_id = _slugify(dept)
            if d_id not in dept_set:
                entities.append({
                    "id": d_id,
                    "type": "Department",
                    "name": f"{dept} Department",
                    "properties": {}
                })
                dept_set.add(d_id)

    # 4. Risks: Matches phrases containing "risk", "leak", "vulnerability", "incident"
    sentences = re.split(r"[.!?\n]", text)
    risk_set = set()
    for s in sentences:
        if any(term in s.lower() for term in ["risk", "leak", "vulnerability", "incident"]):
            match = re.search(r"\b(?:a|an|the)?\s*([a-zA-Z\s\-]{3,30})\s*(?:risk|leak|vulnerability|incident)\b", s, re.IGNORECASE)
            if match:
                risk_name = match.group(1).strip().title() + " Risk"
            else:
                risk_name = "Security Risk"
            
            r_id = _slugify(risk_name)
            if r_id not in risk_set:
                entities.append({
                    "id": r_id,
                    "type": "Risk",
                    "name": risk_name,
                    "properties": {"severity": "High", "description": s.strip()}
                })
                risk_set.add(r_id)

    # 5. Decisions: Matches phrases containing "decided to", "approved", "decision"
    decision_set = set()
    for s in sentences:
        if any(term in s.lower() for term in ["decided to", "approved", "decision"]):
            match = re.search(r"\b(?:decided to|approved|decision to)\s*([a-zA-Z\s\-]{3,35})\b", s, re.IGNORECASE)
            if match:
                dec_name = match.group(1).strip().title() + " Decision"
            else:
                dec_name = "Cloud Migration Decision"
            
            dec_id = _slugify(dec_name)
            if dec_id not in decision_set:
                entities.append({
                    "id": dec_id,
                    "type": "Decision",
                    "name": dec_name,
                    "properties": {"date": "2025-02-25", "description": s.strip()}
                })
                decision_set.add(dec_id)

    # 6. Meetings: Matches phrases containing "meeting", "sync", "standup"
    meeting_set = set()
    for s in sentences:
        if any(term in s.lower() for term in ["meeting", "sync", "standup"]):
            match = re.search(r"\b([a-zA-Z\s\-]{3,25})\s*(?:meeting|sync|standup)\b", s, re.IGNORECASE)
            if match:
                meet_name = match.group(0).strip().title()
            else:
                meet_name = "Align Sync Meeting"
            
            m_id = _slugify(meet_name)
            if m_id not in meeting_set:
                entities.append({
                    "id": m_id,
                    "type": "Meeting",
                    "name": meet_name,
                    "properties": {"date": "2025-02-20"}
                })
                meeting_set.add(m_id)

    # Sentence-level relationship mapping
    entity_by_id = {e["id"]: e for e in entities}
    for s in sentences:
        s_lower = s.lower()
        present_entities = []
        for ent_id, ent in entity_by_id.items():
            if ent["name"].lower() in s_lower or ent["id"] in s_lower:
                present_entities.append(ent)
        
        if len(present_entities) >= 2:
            for i in range(len(present_entities)):
                for j in range(len(present_entities)):
                    if i == j:
                        continue
                    a = present_entities[i]
                    b = present_entities[j]
                    
                    # WORKS_IN: Employee -> Department
                    if a["type"] == "Employee" and b["type"] == "Department":
                        relationships.append({
                            "from_id": a["id"],
                            "from_type": "Employee",
                            "rel_type": "WORKS_IN",
                            "to_id": b["id"],
                            "to_type": "Department",
                            "properties": {}
                        })
                    
                    # MANAGES: Employee -> Project
                    if a["type"] == "Employee" and b["type"] == "Project" and any(w in s_lower for w in ["manage", "lead", "director"]):
                        relationships.append({
                            "from_id": a["id"],
                            "from_type": "Employee",
                            "rel_type": "MANAGES",
                            "to_id": b["id"],
                            "to_type": "Project",
                            "properties": {}
                        })
                    
                    # HAS_RISK: Project -> Risk
                    if a["type"] == "Project" and b["type"] == "Risk":
                        relationships.append({
                            "from_id": a["id"],
                            "from_type": "Project",
                            "rel_type": "HAS_RISK",
                            "to_id": b["id"],
                            "to_type": "Risk",
                            "properties": {}
                        })
                    
                    # RESOLVED_BY: Risk -> Decision
                    if a["type"] == "Risk" and b["type"] == "Decision":
                        relationships.append({
                            "from_id": a["id"],
                            "from_type": "Risk",
                            "rel_type": "RESOLVED_BY",
                            "to_id": b["id"],
                            "to_type": "Decision",
                            "properties": {}
                        })
                    
                    # DISCUSSED_IN: Meeting -> Project
                    if a["type"] == "Meeting" and b["type"] == "Project":
                        relationships.append({
                            "from_id": a["id"],
                            "from_type": "Meeting",
                            "rel_type": "DISCUSSED_IN",
                            "to_id": b["id"],
                            "to_type": "Project",
                            "properties": {}
                        })

    return _validate_and_clean({"entities": entities, "relationships": relationships})


async def extract_entities_and_relationships(
    text: str,
    document_name: str = "",
    llm_client=None,
) -> dict[str, Any]:
    """
    Extract organizational entities and relationships from text using LLM.
    Falls back to a rule-based parser in Mock development environments.
    
    Args:
        text: Document text chunk to extract from
        document_name: Name of the source document
        llm_client: LLM provider instance
    
    Returns:
        {"entities": [...], "relationships": [...]}
    """
    if not text.strip():
        return {"entities": [], "relationships": []}

    if llm_client is None:
        from app.llm.provider import get_llm_provider
        llm_client = get_llm_provider()

    # Rule-based fallback check
    from app.llm.provider import MockLLMProvider
    if isinstance(llm_client, MockLLMProvider):
        logger.debug("Invoking rule-based deterministic extractor (MockLLMProvider active)")
        return _deterministic_mock_extraction(text)

    # Truncate text to avoid context overflow
    text_sample = text[:3000]

    user_message = (
        f"Document: {document_name}\n\n"
        f"Text:\n{text_sample}\n\n"
        f"Extract all organizational entities and relationships from the above text."
    )

    try:
        raw_response = await llm_client.complete(
            system_prompt=EXTRACTION_SYSTEM_PROMPT,
            user_message=user_message,
            temperature=0.0,
            max_tokens=1500,
        )

        # Parse JSON from response
        # Strip markdown code blocks if present
        cleaned = re.sub(r"```(?:json)?\n?", "", raw_response).strip()
        cleaned = cleaned.rstrip("`").strip()

        data = json.loads(cleaned)
        validated = _validate_and_clean(data)
        
        logger.info(
            "Extracted %d entities, %d relationships from '%s'",
            len(validated["entities"]),
            len(validated["relationships"]),
            document_name,
        )
        return validated

    except json.JSONDecodeError as e:
        logger.warning("Failed to parse LLM extraction response as JSON: %s", e)
        return {"entities": [], "relationships": []}
    except Exception as e:
        logger.error("Entity extraction failed: %s", e)
        return {"entities": [], "relationships": []}
