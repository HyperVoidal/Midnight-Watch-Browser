import PySide6
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from PySide6.QtGui import *
import requests
from notifypy import Notify
from pathlib import Path
import re
import time
from collections import deque
import platform
import os
import json
from path_utils import resolve_source_dir


OPERATING_SYSTEM = platform.system()

srcSourceDir = resolve_source_dir(__file__)

class NotificationWidget(QFrame):
    
    clicked = Signal()
    closed = Signal()

    def __init__(self, parent=None, timeout=5000, title="", message="", icon=None):
        super().__init__(parent)
        self.timeout = timeout
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.setStyleSheet("""
            QFrame#card {
                background: rgba(38, 42, 50, 220);
                border: 1px solid rgba(80, 145, 255, 180);
                border-radius: 12px;
            }

            QLabel#title {
                color: #FFFFFF;
                font-size: 13px;
                font-weight: 600;
            }

            QLabel#message {
                color: #FFFFFF;
                font-size: 12px;
                opacity: 0.95;
            }

            QLabel#iconLabel {
                margin-right: 8px;
            }

            QPushButton#closeButton {
                background: rgba(255,255,255,0.06);
                color: #FFFFFF;
                border: none;
                border-radius: 13px;
                font-weight: 700;
                min-width: 26px;
                min-height: 26px;
            }

            QPushButton#closeButton:hover {
                background: rgba(255,255,255,0.12);
                color: #ff6b6b;
            }
        """)

        self.resize(350, 150)

        outerLayout = QVBoxLayout(self)
        outerLayout.setContentsMargins(8, 8, 8, 8)

        card = QFrame()
        card.setObjectName("card")

        outerLayout.addWidget(card)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        # Combined row: icon | (title + message) | close
        row = QHBoxLayout()
        row.setSpacing(10)

        # Icon
        iconLabel = QLabel()
        iconLabel.setObjectName("iconLabel")
        iconLabel.setFixedSize(40, 40)
        iconLabel.setAlignment(Qt.AlignCenter)
        if icon:
            try:
                if isinstance(icon, QIcon):
                    pix = icon.pixmap(32, 32)
                else:
                    pix = QPixmap(str(icon))
                pix = pix.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                iconLabel.setPixmap(pix)
            except Exception:
                iconLabel.setPixmap(QApplication.style().standardIcon(QStyle.SP_MessageBoxInformation).pixmap(32, 32))
        else:
            iconLabel.setPixmap(QApplication.style().standardIcon(QStyle.SP_MessageBoxInformation).pixmap(32, 32))

        # Content (title + message)
        content = QVBoxLayout()
        content.setSpacing(4)
        titleLabel = QLabel(title)
        titleLabel.setObjectName("title")
        body = QLabel(message)
        body.setObjectName("message")
        body.setWordWrap(True)
        content.addWidget(titleLabel)
        content.addWidget(body)

        # Close button
        closeButton = QPushButton("✕")
        closeButton.setObjectName("closeButton")
        closeButton.setFixedSize(26, 26)
        closeButton.clicked.connect(self.closeAnimated)

        row.addWidget(iconLabel)
        row.addLayout(content, 1)
        row.addWidget(closeButton)

        layout.addLayout(row)

        # subtle shadow to lift the notification off background
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(16)
        shadow.setColor(QColor(0, 0, 0, 150))
        shadow.setOffset(0, 6)
        card.setGraphicsEffect(shadow)

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.closeAnimated)
    
    def showAnimated(self):
        screen = QGuiApplication.primaryScreen().availableGeometry()
        final_x = screen.right() - self.width() - 20
        final_y = screen.bottom() - self.height() - 20
        start_x = final_x + self.width() + 20

        self.move(start_x, final_y)
        self.show()
        self.timer.start(self.timeout)

        self.slide_animation = QPropertyAnimation(self, b"pos")
        self.slide_animation.setDuration(500)
        self.slide_animation.setStartValue(QPoint(start_x, final_y))
        self.slide_animation.setEndValue(QPoint(final_x, final_y))
        self.slide_animation.start()

    def closeAnimated(self):
        self.timer.stop()

        end_x = self.x() + self.width() + 20
        self.slide_animation = QPropertyAnimation(self, b"pos")
        self.slide_animation.setDuration(500)
        self.slide_animation.setStartValue(self.pos())
        self.slide_animation.setEndValue(QPoint(end_x, self.y()))
        self.slide_animation.finished.connect(self.close)
        self.slide_animation.start()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()

        super().mousePressEvent(event)


class NotificationManager(QObject):

    def __init__(self):
        super().__init__()
        self.activeNotifications = []

    def showNotification(self, title, message):
        notif = NotificationWidget(
            timeout=5000,
            title=title,
            message=message
        )

        self.activeNotifications.append(notif)

        notif.destroyed.connect(
            lambda: self.activeNotifications.remove(notif)
        )

        notif.showAnimated()
        return notif


class NotificationClickDialog(QDialog):
    def __init__(self, title, message, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Expanded Notification Info")
        self.setWindowIcon(QIcon(f"{srcSourceDir}/ui/icon_cache/tightlyCroppedIcon.png"))
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setStyleSheet("""
            QDialog {
                background-color: rgb(45, 45, 60);
            }
            QLabel#dialogTitle {
                color: white;
                font-size: 18px;
                font-weight: bold;
            }
            QLabel#dialogMessage {
                color: white;
                font-size: 13px;
            }
            QPushButton#okButton {
                background-color: rgb(60, 60, 75);
                color: white;
                border: 2px solid rgb(63, 129, 255);
                border-radius: 18px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton#okButton:hover {
                background-color: rgb(70, 70, 85);
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        title_label = QLabel(title)
        title_label.setObjectName("dialogTitle")
        main_layout.addWidget(title_label, alignment=Qt.AlignmentFlag.AlignCenter)

        message_label = QLabel(message)
        message_label.setObjectName("dialogMessage")
        message_label.setWordWrap(True)
        main_layout.addWidget(message_label)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        ok_button = QPushButton("OK")
        ok_button.setObjectName("okButton")
        ok_button.clicked.connect(self.accept)
        button_layout.addWidget(ok_button)

        button_layout.addStretch()
        main_layout.addLayout(button_layout)

        self.resize(420, 180)


class OnNotificationClick(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)

    def windowCreate(self, title, message):
        def open_dialog():
            dialog = NotificationClickDialog(title, message)
            dialog.exec()
        return open_dialog


class SecureDnsMonitor(QObject):

    def __init__(self, triggerDnsCheck, doh_url):
        super().__init__()

        self.NotificationManager = NotificationManager()
        self.doh_url = doh_url
        self.triggerDnsCheck = triggerDnsCheck

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_dns)
        self.onNotificationClicked = OnNotificationClick()

        self.timer.start(10000)

        self.last_state = None
    
    def __del__(self):
        print("Monitor destroyed")

    def check_dns(self):
        if not self.triggerDnsCheck:
            return

        try:
            r = requests.get(
                self.doh_url,
                params={"name":"example.com","type":"A"},
                headers={"accept":"application/dns-json"},
                timeout=2
            )
            healthy = r.ok

        except Exception as e:
            print("DNS exception:", e)
            healthy = False
        if healthy != self.last_state:
            self.last_state = healthy
            if healthy:
                if self.NotificationManager is not None:
                    self.NotificationManager.showNotification(
                        title="DNS Alert",
                        message="Encrypted DNS connection (DoH) enabled."
                    )
                    

            else:
                if self.NotificationManager is not None:
                    notif = self.NotificationManager.showNotification(
                        title="DNS Alert",
                        message="Encrypted DNS connection (DoH) disabled automatically. Click for more details."
                    )
                    notif.clicked.connect(self.onNotificationClicked.windowCreate("DNS Encryption Fail", "Midnight Watch has detected that the current connection is not allowing a secure DNS connection.\n\nThe browser has dropped to a standard unencrypted connection to maintain activity.\n\nYou can change this behaviour in settings."))



class GPULogMonitor(QObject):

    emergency_fired = Signal(str)

    def __init__(self, time_window=5.0, severity_threshold=10, error_regex=None, fatalPatterns=None):
        super().__init__()
        self.time_window = time_window  # Seconds to remember errors
        self.severity_threshold = severity_threshold  # Max allowed severity score
        self.history = deque()  # Stores tuples of (timestamp, severity)
        self.GPUErrorRegex = error_regex
        self.FatalGPUPatterns = fatalPatterns


    def process_line(self, line):
        match = self.GPUErrorRegex.search(line)
        if not match:
            return

        matched_phrase = match.group(0)
        severity = self.FatalGPUPatterns[matched_phrase]
        current_time = time.time()

        #Log the new incident
        self.history.append((current_time, severity))

        #Prune incidents older than the time window
        oldest_allowed = current_time - self.time_window
        while self.history and self.history[0][0] < oldest_allowed:
            self.history.popleft()

        #Calculate total severity score in the current window
        total_severity = sum(event[1] for event in self.history)
        print(f"Detected: {matched_phrase} (+{severity}). Current window score: {total_severity}")

        #Trigger response if threshold is breached
        if total_severity >= self.severity_threshold:
            self.trigger_emergency_recovery(total_severity)

    def trigger_emergency_recovery(self, score):
        print(
            f"EMERGENCY RECOVERY: Severity score hit {score} in under {self.time_window}s!"
        )
        # Clear history to avoid double-triggering during recovery actions
        self.history.clear()

        #management logic here
        self.emergency_fired.emit("accelVidDecodeErr")

