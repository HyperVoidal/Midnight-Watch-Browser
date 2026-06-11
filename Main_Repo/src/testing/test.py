import os
import sys

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLineEdit, QMainWindow, QPushButton, QToolBar, QVBoxLayout, QWidget
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from PySide6.QtWebEngineWidgets import QWebEngineView


class SimpleBrowser(QMainWindow):
    def __init__(self, start_url: str = "https://browseraudit.com"):
        super().__init__()
        self.setWindowTitle("Simple PySide6 Browser")
        self.resize(1200, 800)

        profile_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "browser_data")
        os.makedirs(profile_dir, exist_ok=True)

        self.profile = QWebEngineProfile("SimpleBrowserProfile", self)
        self.profile.setPersistentStoragePath(profile_dir)
        self.profile.setCachePath(os.path.join(profile_dir, "cache"))
        self.profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
        self.profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.DiskHttpCache)

        self.browser = QWebEngineView(self)
        self.browser.setPage(QWebEnginePage(self.profile, self.browser))

        self.url_bar = QLineEdit(self)
        self.url_bar.setPlaceholderText("Enter a URL and press Enter")
        self.url_bar.returnPressed.connect(self.load_url)

        go_button = QPushButton("Go", self)
        go_button.clicked.connect(self.load_url)

        navigation_toolbar = QToolBar("Navigation", self)
        navigation_toolbar.addWidget(self.url_bar)
        navigation_toolbar.addWidget(go_button)
        self.addToolBar(navigation_toolbar)

        central_widget = QWidget(self)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.browser)
        self.setCentralWidget(central_widget)

        self.browser.urlChanged.connect(self.update_url_bar)
        self.load(start_url)

        back_action = QAction("Back", self)
        back_action.triggered.connect(self.browser.back)
        forward_action = QAction("Forward", self)
        forward_action.triggered.connect(self.browser.forward)
        reload_action = QAction("Reload", self)
        reload_action.triggered.connect(self.browser.reload)

        navigation_toolbar.addAction(back_action)
        navigation_toolbar.addAction(forward_action)
        navigation_toolbar.addAction(reload_action)

    def load_url(self) -> None:
        raw_url = self.url_bar.text().strip()
        if not raw_url:
            return

        if not raw_url.startswith(("http://", "https://")):
            raw_url = f"https://{raw_url}"

        self.load(raw_url)

    def load(self, address: str) -> None:
        self.browser.setUrl(QUrl(address))

    def update_url_bar(self, qurl: QUrl) -> None:
        self.url_bar.setText(qurl.toString())


if __name__ == "__main__":
    app = QApplication(sys.argv)
    browser = SimpleBrowser()
    browser.show()
    sys.exit(app.exec())
