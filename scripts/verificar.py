"""Ejecuta las pruebas del núcleo sin instalar librerías de cámara ni UI."""
import sys
import unittest
from pathlib import Path

raiz = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(raiz / "src"), str(raiz)]
conjunto_pruebas = unittest.defaultTestLoader.discover(str(raiz / "tests/unit"), "test_member2_*.py")
resultado = unittest.TextTestRunner(verbosity=2).run(conjunto_pruebas)
sys.exit(0 if resultado.wasSuccessful() else 1)
