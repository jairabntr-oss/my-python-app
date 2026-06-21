from PyQt5 import QtWidgets, QtCore

class StyleStep(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(StyleStep, self).__init__(parent)
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Step 2: Style Options")
        self.setGeometry(100, 100, 400, 300)

        layout = QtWidgets.QVBoxLayout()

        self.label = QtWidgets.QLabel("Choose your style options:")
        layout.addWidget(self.label)

        self.style_combo = QtWidgets.QComboBox()
        self.style_combo.addItems(["Default", "Dark", "Light"])
        layout.addWidget(self.style_combo)

        self.apply_button = QtWidgets.QPushButton("Apply Style")
        self.apply_button.clicked.connect(self.apply_style)
        layout.addWidget(self.apply_button)

        self.setLayout(layout)

    def apply_style(self):
        selected_style = self.style_combo.currentText()
        # Logic to apply the selected style would go here
        print(f"Applying {selected_style} style.")

if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    window = StyleStep()
    window.show()
    sys.exit(app.exec_())