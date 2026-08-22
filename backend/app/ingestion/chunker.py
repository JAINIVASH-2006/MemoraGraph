"""
MemoraGraph – Semantic Text Chunker

Splits documents into overlapping chunks suitable for embedding.
Uses sentence-aware splitting to avoid breaking mid-sentence.
"""

import logging
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_CHUNK_SIZE = 500      # target tokens (approx characters / 4)
DEFAULT_CHUNK_OVERLAP = 100   # overlap tokens


@dataclass
class Chunk:
    text: str
    chunk_index: int
    char_start: int
    char_end: int
    token_count: int
    metadata: dict


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    doc_metadata: Optional[dict] = None,
) -> list[Chunk]:
    """
    Split text into overlapping semantic chunks.
    
    Strategy:
    1. Split into sentences
    2. Greedily pack sentences into chunks of ~chunk_size tokens
    3. Add overlap by including preceding sentences
    
    Args:
        text: Raw document text
        chunk_size: Target size per chunk in approximate tokens
        chunk_overlap: Number of tokens to overlap between chunks
        doc_metadata: Additional metadata to attach to each chunk
    
    Returns:
        List of Chunk objects
    """
    if not text or not text.strip():
        return []

    sentences = _split_into_sentences(text)
    if not sentences:
        return []

    chunks: list[Chunk] = []
    current_sentences: list[str] = []
    current_tokens = 0
    char_cursor = 0

    # Build sentence positions in original text
    sentence_positions = _find_sentence_positions(text, sentences)

    i = 0
    while i < len(sentences):
        sent = sentences[i]
        sent_tokens = _estimate_tokens(sent)

        # If adding this sentence would exceed limit, flush current chunk
        if current_tokens + sent_tokens > chunk_size and current_sentences:
            chunk_text_val = " ".join(current_sentences)
            start_char = sentence_positions[i - len(current_sentences)][0]
            end_char = sentence_positions[i - 1][1]
            
            chunks.append(Chunk(
                text=chunk_text_val,
                chunk_index=len(chunks),
                char_start=start_char,
                char_end=end_char,
                token_count=current_tokens,
                metadata=doc_metadata or {},
            ))

            # Build overlap: roll back until we've accumulated overlap_tokens
            overlap_sentences: list[str] = []
            overlap_tokens = 0
            j = len(current_sentences) - 1
            while j >= 0 and overlap_tokens < chunk_overlap:
                overlap_sentences.insert(0, current_sentences[j])
                overlap_tokens += _estimate_tokens(current_sentences[j])
                j -= 1
            
            current_sentences = overlap_sentences
            current_tokens = overlap_tokens
        else:
            current_sentences.append(sent)
            current_tokens += sent_tokens
            i += 1

    # Flush remaining
    if current_sentences:
        chunk_text_val = " ".join(current_sentences)
        start_idx = len(sentences) - len(current_sentences)
        start_char = sentence_positions[max(start_idx, 0)][0] if sentence_positions else 0
        end_char = sentence_positions[-1][1] if sentence_positions else len(text)
        
        chunks.append(Chunk(
            text=chunk_text_val,
            chunk_index=len(chunks),
            char_start=start_char,
            char_end=end_char,
            token_count=current_tokens,
            metadata=doc_metadata or {},
        ))

    logger.debug("Chunked text into %d chunks (target_size=%d, overlap=%d)", 
                 len(chunks), chunk_size, chunk_overlap)
    return chunks


def _split_into_sentences(text: str) -> list[str]:
    """Split text into sentences using regex heuristics."""
    # Split on sentence boundaries: period/!/? followed by space + capital
    pattern = r'(?<=[.!?])\s+(?=[A-Z])'
    raw_sentences = re.split(pattern, text)
    
    sentences = []
    for sent in raw_sentences:
        sent = sent.strip()
        if len(sent) < 5:  # skip tiny fragments
            continue
        # Further split very long sentences on newlines
        if "\n" in sent and len(sent) > 1000:
            sub = [s.strip() for s in sent.split("\n") if s.strip()]
            sentences.extend(sub)
        else:
            sentences.append(sent)
    
    return sentences if sentences else [text.strip()]


def _find_sentence_positions(text: str, sentences: list[str]) -> list[tuple[int, int]]:
    """Find approximate character positions for each sentence in original text."""
    positions = []
    cursor = 0
    for sent in sentences:
        start = text.find(sent[:50], cursor)
        if start == -1:
            start = cursor
        end = start + len(sent)
        positions.append((start, end))
        cursor = end
    return positions


def _estimate_tokens(text: str) -> int:
    """Approximate token count: ~4 characters per token (GPT tokenization heuristic)."""
    return max(1, len(text) // 4)
