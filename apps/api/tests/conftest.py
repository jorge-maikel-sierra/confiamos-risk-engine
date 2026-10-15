"""Configuración global de fixtures y entorno para la suite de pruebas de Pytest."""

import os

# Forzar modo testing para evitar llamadas a APIs externas y bases de datos reales
os.environ["TESTING"] = "true"
