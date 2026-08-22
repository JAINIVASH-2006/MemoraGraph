"""
MemoraGraph – Semantic Intent Classifier

Computes cosine similarity between user query embedding and intent prototype sentence embeddings.
Modular design allows this to be easily replaced by a fine-tuned classifier later.
"""

import logging
from typing import List, Dict, Tuple, Optional

from app.embeddings.encoder import get_encoder, cosine_similarity
from app.retrieval.intent_definitions import INTENT_DEFINITIONS, GENERAL_INFORMATION
from app.schemas.query import IntentResult

logger = logging.getLogger(__name__)


class IntentClassifier:
    """
    Classifies a user query into one of the 11 organizational intents.
    Uses sentence embeddings and cosine similarity against prototype sentences.
    """

    def __init__(self):
        self._encoder = get_encoder()
        self._prototype_embeddings: Dict[str, List[List[float]]] = {}
        self._initialize_prototypes()

    def _initialize_prototypes(self) -> None:
        """Prefetch and cache embeddings for all prototype sentences."""
        logger.info("Initializing Intent Classifier prototypes...")
        
        # Batch encode all prototypes for speed
        all_prototypes = []
        prototype_map = []  # keeps track of (intent, index)

        for intent, info in INTENT_DEFINITIONS.items():
            for p in info["prototypes"]:
                all_prototypes.append(p)
                prototype_map.append(intent)

        # Generate embeddings
        embeddings = self._encoder.encode(all_prototypes)

        # Group embeddings back by intent
        for intent in INTENT_DEFINITIONS:
            self._prototype_embeddings[intent] = []

        for i, emb in enumerate(embeddings):
            intent = prototype_map[i]
            self._prototype_embeddings[intent].append(emb)

        logger.info("Intent Classifier prototypes initialized successfully.")

    def classify(self, query: str, confidence_threshold: Optional[float] = None) -> IntentResult:
        """
        Classifies query based on average similarity to prototype embeddings.
        
        Returns:
            IntentResult with predicted intent, confidence, allowed_relationships,
            and whether fallback was triggered.
        """
        from app.config import settings
        if confidence_threshold is None:
            confidence_threshold = settings.intent_confidence_threshold

        query_emb = self._encoder.encode_single(query)
        if not query_emb:
            return IntentResult(
                intent=GENERAL_INFORMATION,
                confidence=1.0,
                allowed_relationships=[],
                fallback_used=True,
                low_confidence=True,
            )

        best_intent = GENERAL_INFORMATION
        max_similarity = -1.0

        for intent, proto_embs in self._prototype_embeddings.items():
            if not proto_embs:
                continue
            # Calculate similarities to all prototypes of this intent
            sims = [cosine_similarity(query_emb, pe) for pe in proto_embs]
            
            # Use max similarity (best match) or average of top 3
            sims.sort(reverse=True)
            avg_top_sim = sum(sims[:3]) / min(3, len(sims))

            if avg_top_sim > max_similarity:
                max_similarity = avg_top_sim
                best_intent = intent

        # Scale/normalize confidence score slightly to fit [0.0, 1.0] range
        min_expected = 0.35
        max_expected = 0.85
        confidence = (max_similarity - min_expected) / (max_expected - min_expected)
        confidence = max(0.0, min(1.0, confidence))

        allowed_rels = INTENT_DEFINITIONS[best_intent]["allowed_relationships"]
        fallback = False
        low_confidence = False

        # Fallback/Low confidence state
        if confidence < confidence_threshold:
            logger.warning(
                "Low intent classification confidence (%.2f < %.2f) for intent: %s. Flagging LOW_CONFIDENCE.",
                confidence, confidence_threshold, best_intent,
            )
            low_confidence = True
            fallback = True
            # Retain allowed_relationships of best_intent, but set label to LOW_CONFIDENCE
            best_intent = "LOW_CONFIDENCE"

        logger.info(
            "Query Intent: %s (confidence: %.2f, fallback_used: %s, low_confidence: %s)",
            best_intent, confidence, fallback, low_confidence,
        )

        return IntentResult(
            intent=best_intent,
            confidence=round(confidence, 3),
            allowed_relationships=allowed_rels,
            fallback_used=fallback,
            low_confidence=low_confidence,
        )


# Singleton
_classifier = None


def get_intent_classifier() -> IntentClassifier:
    global _classifier
    if _classifier is None:
        _classifier = IntentClassifier()
    return _classifier
