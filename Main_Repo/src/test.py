import sys
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtGui import QAction

class MenuWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PySide6 Menu Example")
        
        # 1. Access the menu bar
        menu_bar = self.menuBar()
        
        # 2. Create menus
        file_menu = menu_bar.addMenu("&File")
        
        # 3. Create actions
        exit_action = QAction("&Exit", self)
        exit_action.triggered.connect(self.close)
        
        # 4. Add actions to menus
        file_menu.addAction(exit_action)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MenuWindow()
    window.show()
    sys.exit(app.exec())
