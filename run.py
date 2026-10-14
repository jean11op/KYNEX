"""Ejecutar Kinex desde la raíz: python run.py."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from holocontrol.bootstrap import main

if __name__ == "__main__":
    main()
