"""
MemoraGraph – Intent Definitions

Defines semantic query intents, prototype queries for similarity matching,
and the mapping to allowed Neo4j relationship types.
"""

from typing import List, Dict

# Intent names
PERSON_PROJECT = "PERSON_PROJECT"
PROJECT_RISK = "PROJECT_RISK"
PROJECT_DECISION = "PROJECT_DECISION"
DECISION_REASON = "DECISION_REASON"
DECISION_OUTCOME = "DECISION_OUTCOME"
EMPLOYEE_DEPARTMENT = "EMPLOYEE_DEPARTMENT"
PROJECT_TIMELINE = "PROJECT_TIMELINE"
RISK_CAUSE = "RISK_CAUSE"
RISK_RESOLUTION = "RISK_RESOLUTION"
CROSS_PROJECT = "CROSS_PROJECT"
GENERAL_INFORMATION = "GENERAL_INFORMATION"

INTENT_DEFINITIONS: Dict[str, Dict] = {
    PERSON_PROJECT: {
        "description": "Queries about who is working on, managing, or owning which projects or components.",
        "allowed_relationships": ["<MANAGES", "MANAGES>", "<ASSIGNED_TO", "ASSIGNED_TO>", "<OWNS", "OWNS>"],
        "prototypes": [
            "Who is working on Project Alpha?",
            "Who is the project manager for Project Beta?",
            "Who managed Project Alpha?",
            "Who managed Project Atlas?",
            "List all people assigned to Project Gamma.",
            "What projects is Priya managing?",
            "Who is the lead on the security project?",
            "Who owns Project Atlas?",
            "Who owns the React dashboard?",
            "Who is the owner of Project Atlas?",
            "Who is responsible for Project Atlas?",
            "Who is responsible for the React dashboard?",
            "Who manages Project Atlas?",
            "Who manages Project Alpha?",
            "Who manages the React dashboard?",
            "Which person owns this project?",
            "Who is assigned responsibility for this project?",
        ]
    },
    PROJECT_RISK: {
        "description": "Queries about risks, issues, and hazards associated with projects.",
        "allowed_relationships": ["<HAS_RISK", "HAS_RISK>", "RELATED_TO", "<CAUSED", "CAUSED>"],
        "prototypes": [
            "What risks are identified for Project Alpha?",
            "Are there any open risks in Project Beta?",
            "List all security risks for the cloud migration project.",
            "What issues are affecting our main projects?",
            "Is there any risk regarding project timeline?",
        ]
    },
    PROJECT_DECISION: {
        "description": "Queries about decisions made within projects.",
        "allowed_relationships": ["<APPROVED", "APPROVED>", "<DISCUSSED_IN", "DISCUSSED_IN>", "<INVOLVES", "INVOLVES>", "<RESULTED_IN", "RESULTED_IN>"],
        "prototypes": [
            "What decisions have been approved for Project Alpha?",
            "What was decided in the Project Beta meeting?",
            "Who approved the cloud migration decision?",
            "List all major project decisions.",
            "Was a decision made regarding security upgrades?",
        ]
    },
    DECISION_REASON: {
        "description": "Queries regarding why a decision was made, its causes or context.",
        "allowed_relationships": ["<CAUSED", "CAUSED>", "<DISCUSSED_IN", "DISCUSSED_IN>", "RELATED_TO", "<INVOLVES", "INVOLVES>"],
        "prototypes": [
            "Why did we decide to migrate to the cloud?",
            "What caused the security upgrade decision?",
            "What was the reason behind the budget cut?",
            "What security incidents led to the migration?",
            "Why was this migration plan approved?",
        ]
    },
    DECISION_OUTCOME: {
        "description": "Queries about outcomes, impacts, or results of decisions.",
        "allowed_relationships": ["<RESULTED_IN", "RESULTED_IN>", "<RESOLVED_BY", "RESOLVED_BY>", "<APPROVED", "APPROVED>"],
        "prototypes": [
            "What was the outcome of the security upgrade decision?",
            "What resulted from the cloud migration decision?",
            "Did the migration resolve the budget issues?",
            "What happened after the team approved the new technology?",
            "What outcome did the migration lead to?",
        ]
    },
    EMPLOYEE_DEPARTMENT: {
        "description": "Queries about employee assignments to departments.",
        "allowed_relationships": ["<WORKS_IN", "WORKS_IN>", "<MANAGES", "MANAGES>", "<PART_OF", "PART_OF>"],
        "prototypes": [
            "Which department does Arun work in?",
            "Who works in the Engineering department?",
            "Who manages the Security department?",
            "Which team does Priya belong to?",
            "List all employees in HR.",
            "Which department is responsible for Project Atlas?",
        ]
    },
    PROJECT_TIMELINE: {
        "description": "Queries about timelines, events, and schedules of projects.",
        "allowed_relationships": ["<PART_OF", "PART_OF>", "<DISCUSSED_IN", "DISCUSSED_IN>", "<RESULTED_IN", "RESULTED_IN>"],
        "prototypes": [
            "What events have happened in Project Alpha?",
            "When did Project Beta start?",
            "Timeline of events for the security incident.",
            "Show me the schedule of Project Gamma.",
            "What was discussed in the last project meeting?",
        ]
    },
    RISK_CAUSE: {
        "description": "Queries about the causes of risks, incidents, or issues.",
        "allowed_relationships": ["<CAUSED", "CAUSED>", "RELATED_TO", "<HAS_RISK", "HAS_RISK>"],
        "prototypes": [
            "What caused the security risk in Project Alpha?",
            "Why did the security incident happen?",
            "What was the root cause of the budget deficit?",
            "How did this risk occur?",
            "What factors led to the schedule delay?",
        ]
    },
    RISK_RESOLUTION: {
        "description": "Queries about how risks were resolved or mitigated.",
        "allowed_relationships": ["<RESOLVED_BY", "RESOLVED_BY>", "<APPROVED", "APPROVED>", "RELATED_TO"],
        "prototypes": [
            "How was the security risk in Project Alpha resolved?",
            "Who resolved the budget deficit?",
            "What decision resolved the schedule risk?",
            "Are there mitigations for the cloud migration risk?",
            "What is the resolution plan for the outage?",
        ]
    },
    CROSS_PROJECT: {
        "description": "Queries comparing multiple projects or exploring dependencies between them.",
        "allowed_relationships": ["<DEPENDS_ON", "DEPENDS_ON>", "RELATED_TO", "<PART_OF", "PART_OF>", "<INVOLVES", "INVOLVES>"],
        "prototypes": [
            "What is the relationship between Project Aurora and Identity Gateway?",
            "What is the relationship between Project Alpha and Project Beta?",
            "Does Project Alpha depend on Project Beta?",
            "How are Project Alpha and Project Gamma related?",
            "Are there dependencies between migration and security?",
            "Compare the risks of Project Alpha and Beta.",
            "What is the relation between these projects?",
        ]
    },
    GENERAL_INFORMATION: {
        "description": "Broad or factual query with no specific relational pattern constraint.",
        "allowed_relationships": [],  # Empty means traverse all semantic relationships (excluding MENTIONED_IN)
        "prototypes": [
            "What is Project Alpha?",
            "What is Project Aurora?",
            "What is Project Atlas?",
            "What is Project Beta?",
            "Tell me about Project Atlas.",
            "Describe this project.",
            "What is this project about?",
            "What is the overall status of the company?",
            "Summary of recent reports.",
            "General summary of organizational changes.",
            "What did the meeting notes say?",
        ]
    }
}
