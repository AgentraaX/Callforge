"""Text splitter for streaming TTS -- splits long agent responses into
chunks sized for gap-free playback.

Each chunk's playback duration covers the next chunk's synthesis time.
First chunk is ~75 chars to minimize time-to-first-audio.
"""
from __future__ import annotations
import re

_SENT_SPLIT = re.compile(r"(?<=[.!?…])\s+")


def split_for_speech(text: str) -> list[str]:
    """Split text into TTS-friendly chunks.
    
    Budget shrinks per chunk so playback of earlier chunks masks
    synthesis latency of later ones.
    """
    parts = [p.strip() for p in _SENT_SPLIT.split(text) if p.strip()]
    if not parts:
        return [text]
    
    budgets = [75, 60, 48, 40, 34, 30]  # then 30 forever
    chunks: list[str] = []
    cur = ""
    bi = 0
    
    for p in parts:
        budget = budgets[min(bi, len(budgets) - 1)]
        candidate = (cur + " " + p).strip()
        if cur and len(candidate) > budget:
            chunks.append(cur)
            bi += 1
            cur = p
        else:
            cur = candidate
        
        # Split very long sentences at commas
        budget = budgets[min(bi, len(budgets) - 1)]
        while len(cur) > budget + 35:
            cut = max(
                cur.rfind(", ", 25, budget + 35),
                cur.rfind(" -- ", 25, budget + 35),
                cur.rfind(" ", 25, budget + 35),
            )
            if cut < 0:
                break
            chunks.append(cur[:cut + 1].strip())
            bi += 1
            cur = cur[cut + 1:].strip()
            budget = budgets[min(bi, len(budgets) - 1)]
    
    if cur and chunks and len(cur) < 18:
        chunks[-1] += " " + cur
    elif cur:
        chunks.append(cur)
    
    return chunks or [text]
