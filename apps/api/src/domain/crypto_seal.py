"""Servicio de sellado criptográfico de integridad y no-repudio (SPEC-07)."""

import hashlib
import hmac
import json
from typing import Any


class CryptoSealService:
    """Calcula y verifica hashes SHA-256 canónicos para dictámenes crediticios."""

    @staticmethod
    def compute_canonical_hash(payload: dict[str, Any]) -> str:
        """Serializa de forma canónica (claves ordenadas, separadores) y calcula SHA-256."""
        canonical_json = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            default=str,
        )
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    @staticmethod
    def verify_hash(payload: dict[str, Any], expected_hash: str) -> bool:
        """Compara el hash canónico del payload contra el hash esperado en tiempo constante."""
        calculated = CryptoSealService.compute_canonical_hash(payload)
        return hmac.compare_digest(calculated, expected_hash)
