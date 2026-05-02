from __future__ import annotations

import hashlib
import math
import re
from typing import Iterable

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9+#./-]{1,}")


class HashingEmbeddingService:
    """Small, dependency-free embedding service.

    This is intentionally lightweight for local/AWS student deployment while still
    separating embedding generation from ranking rules. It behaves like a service
    boundary the rest of the AI layer can depend on.
    """

    def __init__(self, dimensions: int = 192):
        self.dimensions = max(32, int(dimensions))

    def tokenize(self, text: str | None) -> list[str]:
        return [token.lower() for token in _TOKEN_RE.findall(text or "")]

    def embed_tokens(self, tokens: Iterable[str]) -> list[float]:
        vector = [0.0] * self.dimensions
        seen = 0
        for token in tokens:
            if not token:
                continue
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            weight = 1.0 + min(len(token), 12) / 12.0
            vector[bucket] += sign * weight
            seen += 1
        if seen == 0:
            return vector
        norm = math.sqrt(sum(value * value for value in vector))
        if norm <= 1e-12:
            return vector
        return [value / norm for value in vector]

    def embed_text(self, text: str | None) -> list[float]:
        return self.embed_tokens(self.tokenize(text))

    def cosine_similarity(self, left: list[float], right: list[float]) -> float:
        if not left or not right:
            return 0.0
        length = min(len(left), len(right))
        return max(-1.0, min(1.0, sum(left[i] * right[i] for i in range(length))))

    def similarity(self, left_text: str | None, right_text: str | None) -> float:
        return self.cosine_similarity(self.embed_text(left_text), self.embed_text(right_text))
