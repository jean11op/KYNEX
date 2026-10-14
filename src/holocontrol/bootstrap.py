"""Punto de entrada de la interfaz Kinex."""
import sys
from PySide6.QtWidgets import QApplication
from holocontrol.presentation.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Kinex")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
