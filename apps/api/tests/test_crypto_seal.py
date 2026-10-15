"""Tests unitarios para el sellado criptográfico de integridad (SPEC-07 / TDD Seam 1)."""


from src.domain.crypto_seal import CryptoSealService


def test_compute_canonical_hash_is_deterministic_regardless_of_key_order():
    """El cálculo SHA-256 debe ser idéntico sin importar el orden de las claves."""
    payload_a = {
        "id": "app-1234",
        "associated_id": "ASOC-9988",
        "business_name": "Agroinsumos del Valle",
        "requested_amount_usd": 75000.0,
        "term_months": 24,
        "metrics": {
            "dscr": 1.45,
            "current_ratio": 1.8,
            "runway_months": 8.5,
        },
        "recommendation": "APROBADO",
    }

    # Mismo contenido pero orden reverso de claves
    payload_b = {
        "recommendation": "APROBADO",
        "metrics": {
            "runway_months": 8.5,
            "current_ratio": 1.8,
            "dscr": 1.45,
        },
        "term_months": 24,
        "requested_amount_usd": 75000.0,
        "business_name": "Agroinsumos del Valle",
        "associated_id": "ASOC-9988",
        "id": "app-1234",
    }

    hash_a = CryptoSealService.compute_canonical_hash(payload_a)
    hash_b = CryptoSealService.compute_canonical_hash(payload_b)

    assert len(hash_a) == 64
    assert hash_a == hash_b


def test_verify_hash_detects_tampering():
    """Cualquier alteración en el contenido debe invalidar la verificación de integridad."""
    payload = {
        "id": "app-1234",
        "associated_id": "ASOC-9988",
        "business_name": "Agroinsumos del Valle",
        "requested_amount_usd": 75000.0,
        "term_months": 24,
        "metrics": {"dscr": 1.45},
        "recommendation": "APROBADO",
    }

    valid_hash = CryptoSealService.compute_canonical_hash(payload)
    assert CryptoSealService.verify_hash(payload, valid_hash) is True

    # Alteramos el monto solicitado
    tampered_payload = dict(payload)
    tampered_payload["requested_amount_usd"] = 80000.0
    assert CryptoSealService.verify_hash(tampered_payload, valid_hash) is False

    # Alteramos la recomendación
    tampered_payload_2 = dict(payload)
    tampered_payload_2["recommendation"] = "RECHAZADO"
    assert CryptoSealService.verify_hash(tampered_payload_2, valid_hash) is False
