import sys

from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("HoloControl Access")
        self.resize(800, 500)

        self.title_label = QLabel("HoloControl Access")
        self.title_label.setStyleSheet(
            "font-size: 28px; font-weight: bold;"
        )

        self.description_label = QLabel(
            "Control accesible de Windows mediante gestos de las manos."
        )

        self.status_label = QLabel("Estado: sistema detenido")

        self.start_button = QPushButton("Iniciar control")
        self.start_button.clicked.connect(self.start_control)

        layout = QVBoxLayout()
        layout.addWidget(self.title_label)
        layout.addWidget(self.description_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self.start_button)
        layout.addStretch()

        central_widget = QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

    def start_control(self):
        self.status_label.setText(
            "Estado: interfaz preparada (control aún no implementado)"
        )


def main():
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
