"""
MemoraGraph – Knowledge Graph Schema

Defines all valid node types and relationship types as Python enums.
These are used throughout the system to enforce schema consistency.
"""

import enum


class NodeType(str, enum.Enum):
    EMPLOYEE = "Employee"
    DEPARTMENT = "Department"
    PROJECT = "Project"
    MEETING = "Meeting"
    RISK = "Risk"
    DECISION = "Decision"
    TECHNOLOGY = "Technology"
    EVENT = "Event"
    OUTCOME = "Outcome"
    DOCUMENT = "Document"
    TASK = "Task"
    ISSUE = "Issue"


class RelationshipType(str, enum.Enum):
    WORKS_IN = "WORKS_IN"
    MANAGES = "MANAGES"
    PART_OF = "PART_OF"
    INVOLVES = "INVOLVES"
    HAS_RISK = "HAS_RISK"
    APPROVED = "APPROVED"
    DISCUSSED_IN = "DISCUSSED_IN"
    CAUSED = "CAUSED"
    RESULTED_IN = "RESULTED_IN"
    ASSIGNED_TO = "ASSIGNED_TO"
    RELATED_TO = "RELATED_TO"
    DEPENDS_ON = "DEPENDS_ON"
    RESOLVED_BY = "RESOLVED_BY"
    MENTIONED_IN = "MENTIONED_IN"


# Valid node types as a set of strings (for validation)
VALID_NODE_TYPES: set[str] = {t.value for t in NodeType}

# Valid relationship types as a set of strings
VALID_REL_TYPES: set[str] = {r.value for r in RelationshipType}

# Relationship directionality guide:
# Employee   --[WORKS_IN]-->    Department
# Employee   --[MANAGES]-->     Project
# Employee   --[MANAGES]-->     Department
# Project    --[HAS_RISK]-->    Risk
# Project    --[INVOLVES]-->    Technology
# Project    --[PART_OF]-->     Department
# Meeting    --[DISCUSSED_IN]-> Project
# Decision   --[APPROVED]-->    Project
# Decision   --[RESULTED_IN]--> Outcome
# Risk       --[CAUSED]-->      Event
# Risk       --[RESOLVED_BY]--> Decision
# Task       --[ASSIGNED_TO]--> Employee
# Task       --[PART_OF]-->     Project
# Issue      --[RELATED_TO]-->  Risk
# Entity     --[MENTIONED_IN]-> Document
