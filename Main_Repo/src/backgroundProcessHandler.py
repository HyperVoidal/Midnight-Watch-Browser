import PySide6
from PySide6.QtCore import *
import requests
from notifypy import Notify
from pathlib import Path
import re
import time
from collections import deque
import platform
import os


OPERATING_SYSTEM = platform.system()

#Create main src source depending on operating system
if OPERATING_SYSTEM == "Linux":
    #Main src source since bubblewrap can use default installation location
    srcSourceDir = Path(__file__).parent
elif OPERATING_SYSTEM == "Windows":
    #If using windows I need MSIX which only permits read/write into the appdata location.
    localAppData = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser('~'), 'AppData', 'Local')
    appDataPath = Path(localAppData) / "Midnight Watch"
    appDataPath.mkdir(parents=True, exist_ok=True)
    srcSourceDir = Path(appDataPath)

class SecureDnsMonitor(QObject):

    def __init__(self, triggerDnsCheck, doh_url):
        super().__init__()

        self.doh_url = doh_url
        self.triggerDnsCheck = triggerDnsCheck

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_dns)

        # every 10 seconds
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
                notification = Notify()
                notification.application_name = "Midnight Watch"
                notification.title = "DNS Alert"
                notification.message = "Encrypted DNS connection (DoH) enabled."
                notification.icon = f"{srcSourceDir}/ui/icon_cache/tightlyCroppedIcon.png"
                notification.send()
            else:
                notification = Notify()
                notification.application_name = "Midnight Watch"
                notification.title = "DNS Alert"
                notification.message = "Midnight Watch has detected that the current connection is not allowing a secure DNS connection. \n The browser has dropped to standard unencrypted connection to maintain activity. \n You can change this behaviour in settings."
                notification.icon = f"{srcSourceDir}/ui/icon_cache/tightlyCroppedIcon.png"
                notification.send()



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

