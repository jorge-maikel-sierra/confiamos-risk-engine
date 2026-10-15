"""Adaptador de infraestructura para generación de embeddings (SPEC-05).

Integra el modelo 'text-embedding-004' de Google GenAI con fallback a Mock determinístico.
"""

import os
from typing import Any

from src.domain.vector_search import IEmbeddingGenerator, MockEmbeddingGenerator


class GeminiEmbeddingGenerator:
    """Generador de embeddings de producción usando Google GenAI 'text-embedding-004'."""

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = "text-embedding-004",
    ) -> None:
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model_name = model_name
        from google import genai

        self.client = genai.Client(api_key=self.api_key)

    async def generate_embedding(self, text: str) -> list[float]:
        """Invoca la API de Google GenAI para generar el vector denso de 768 dimensiones."""
        try:
            response: Any = self.client.models.embed_content(
                model=self.model_name,
                contents=text,
            )

            if hasattr(response, "embeddings") and response.embeddings:
                values = response.embeddings[0].values
                return list(values)
        except Exception:
            # Fallback en caso de fallos de red o API no disponible
            mock = MockEmbeddingGenerator()
            return await mock.generate_embedding(text)

        raise ValueError("No se recibieron embeddings en la respuesta de Google GenAI")


def get_embedding_generator() -> IEmbeddingGenerator:
    """Factoría que resuelve el generador según la configuración y entorno."""
    if os.getenv("TESTING") == "true":
        return MockEmbeddingGenerator()

    api_key = os.getenv("GEMINI_API_KEY")
    if api_key and api_key != "your_gemini_api_key_here":
        try:
            return GeminiEmbeddingGenerator(api_key=api_key)
        except Exception:
            return MockEmbeddingGenerator()

    return MockEmbeddingGenerator()
