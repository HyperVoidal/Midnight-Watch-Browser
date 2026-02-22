from PySide6.QtWidgets import *
from PySide6.QtCore import Qt
from functools import partial

class Overlay(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setStyleSheet("background-color: rgba(0, 0, 0, 150);")
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        # Ensure overlay matches the current size of the parent window
        self.setGeometry(parent.rect())

class Dialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_layout = QVBoxLayout(self)
        self.label = QLabel("default text")
        self.main_layout.addWidget(self.label)
        
        # Container for dynamic buttons
        self.button_box = QDialogButtonBox()
        self.main_layout.addWidget(self.button_box)
    
    def handle_click(self, action):
        self.done(action)

    
    def outputPrompt(self, title=str, label=str, button_info=list):
        self.setWindowTitle(title)
        self.label.setText(label)

        #button info = [(a, b), (c, d)]
        #current usage: [("Download Now", QDialog.Accepted), ("No thanks", QDialog.Rejected)]
        
        button_names = []
        button_connections = []
        for i in range(len(button_info)):
            button_names.append(button_info[i][0])
            button_connections.append(button_info[i][1])

        # Clear existing buttons if reusing the dialog
        for btn in self.button_box.buttons():
            self.button_box.removeButton(btn)

        # Dynamically create buttons
        for name in range(len(button_names)):
            btn = self.button_box.addButton(button_names[name], QDialogButtonBox.ActionRole)
            btn.clicked.connect(partial(self.handle_click, button_connections[name]))

