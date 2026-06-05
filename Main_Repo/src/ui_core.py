import json
from pathlib import Path
import requests
from PySide6.QtGui import *
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from functools import partial
from cookieManager import CookieManager
import urllib




icon_cache_dir = Path(__file__).parent / "ui/icon_cache"
icon_cache_dir.mkdir(exist_ok=True)

srcSourceDir =  Path(__file__).parent

def loadActionToggles():
    with open (srcSourceDir / "data/actionToggles.json", "r") as f:
                actionToggles = json.load(f)
    return actionToggles

def get_normIcon(name):
    icon_path = icon_cache_dir / f"{name}"

    return QIcon(str(icon_path))

def get_cached_favicon(key, url_string, cache_dir: Path):
    #Set up directories
    cache_dir.mkdir(parents=True, exist_ok=True)
    icon_path = cache_dir / f"{key}.png"

    #Check for existing icon
    if icon_path.exists():
        return QIcon(str(icon_path))
    
    try:
        url = QUrl(url_string)
        domain = url.host()
        favicon_url = f"https://www.google.com/s2/favicons?domain={domain}&sz=64"

        response = requests.get(favicon_url)
        response.raise_for_status()

        with open(icon_path, 'wb') as f:
            f.write(response.content)
        print(f"Favicon saved")
        return QIcon(str(icon_path))
        
    except Exception as e:
        print(f"Could not fetch icon for {key}: {e}")
        # Return a fallback default icon if network/API fails
        return QIcon(str(cache_dir / "default_icon.png"))



class additionalUIElements:
    def __init__(self, parent):
        self.parent = parent
        

    def WindowConfirmation(self, title, message, num=2):
        parent=None
        if isinstance(self.parent,QWidget):
            parent=self.parent
        elif hasattr(self.parent,"view"):
            parent=self.parent.view()

        msg_box=QMessageBox(parent)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(QMessageBox.Icon.Question)

        if num==1:
            msg_box.setStandardButtons(QMessageBox.StandardButton.Yes)
            yes_button=msg_box.button(QMessageBox.StandardButton.Yes)
            yes_button.setText("Okay")
            msg_box.exec()
            return (msg_box.clickedButton() == yes_button)

        elif num==2:
            msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            msg_box.exec()
            return (msg_box.clickedButton() == msg_box.button(QMessageBox.StandardButton.Yes))
        

    def WindowInput(self, title, message, default_text=""):
        text, ok = QInputDialog.getText(
            self.parent,
            title,
            message,
            QLineEdit.EchoMode.Normal,
            default_text
        )
        if ok and text.strip():
            return text.strip()
        return None

    def WindowDoubleInput(self, title, message1, default_text1, message2, default_text2):
        dialog = QDialog(self.parent)
        dialog.setWindowTitle(title.capitalize())
        
        layout = QVBoxLayout(dialog)
        formLayout = QFormLayout()

        input1 = QLineEdit()
        message_1 = QLabel(message1)
        formLayout.addRow(message_1)
        formLayout.addRow(default_text1, input1)
        input2 = QLineEdit()
        message_2 = QLabel(message2)
        formLayout.addRow(message_2)
        formLayout.addRow(default_text2, input2)

        layout.addLayout(formLayout)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Yes | QDialogButtonBox.StandardButton.No)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.Accepted:
            return input1.text(), input2.text()
        return None, None

    

class NewProfileDialog(QDialog):
    def __init__(self, parent=None, title="Create New Profile", placeholder="Enter profile name...", image=None, image_text="Profile Image:"):
        super().__init__(parent)

        self.setWindowTitle(title)
        self.resize(400, 220)

        self.image_path = ""

        layout = QVBoxLayout(self)

        # ----- Name -----
        layout.addWidget(QLabel("Profile Name:"))

        self.nameInput = QLineEdit()
        self.nameInput.setPlaceholderText(placeholder)
        layout.addWidget(self.nameInput)

        # ----- Image Selection -----
        layout.addWidget(QLabel(image_text))

        imgLayout = QHBoxLayout()

        self.imagePreview = QLabel()
        self.imagePreview.setFixedSize(64,64)
        self.imagePreview.setStyleSheet("""
            border: 1px solid gray;
            background: transparent;
        """)
        self.imagePreview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if image:
            self.image_path = image

            pixmap = QPixmap(image)
            pixmap = pixmap.scaled(
                64,64,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )

            self.imagePreview.setPixmap(pixmap)

        self.browseButton = QPushButton("Browse...")
        self.browseButton.clicked.connect(self.selectImage)

        imgLayout.addWidget(self.imagePreview)
        imgLayout.addWidget(self.browseButton)

        layout.addLayout(imgLayout)

        # ----- OK / Cancel -----
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )

        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addWidget(buttons)

    def selectImage(self):

        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Select Profile Image",
            f"{srcSourceDir}/ui/images",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
        )

        if filepath:
            self.image_path = filepath

            pixmap = QPixmap(filepath)
            pixmap = pixmap.scaled(64,64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

            self.imagePreview.setPixmap(pixmap)

    def getData(self):
        return {
            "name": self.nameInput.text().strip(),
            "photoURL": self.image_path
        }
    

class EmergencyOverlay(QWidget):
    # Signal emitted when the action button is clicked
    reboot_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setStyleSheet("""
            QWidget {
                background-color: #0d0d0d;
                color: #f0f0f0;
            }
            QLabel#OverlayTitle {
                font-size: 24px;
                font-weight: bold;
                color: #ff4d4d;
                margin-bottom: 10px;
                background: transparent;
            }
            QLabel#OverlayText {
                font-size: 14px;
                color: #cccccc;
                background: transparent;
            }
            QPushButton#RebootButton {
                background-color: #ff4d4d;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton#RebootButton:hover {
                background-color: #e63939;
            }
            QPushButton#RebootButton:pressed {
                background-color: #cc2929;
            }
        """)

        # Set up the layout
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)

        # Create UI elements with specific object names for the CSS
        self.title_label = QLabel()
        self.title_label.setObjectName("OverlayTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        #self.title_label.setWordWrap(True)

        self.text_label = QLabel()
        self.text_label.setObjectName("OverlayText")
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        #self.text_label.setWordWrap(True)

        self.reboot_btn = QPushButton("Reboot Browser")
        self.reboot_btn.setObjectName("RebootButton")
        self.reboot_btn.setFixedSize(220, 45)
        self.reboot_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        

        # Connect the button click to out-of-file backend emitters
        self.reboot_btn.clicked.connect(self.reboot_requested.emit)

        self.title_label.setAlignment(Qt.AlignHCenter)
        self.text_label.setAlignment(Qt.AlignHCenter)
        self.text_label.adjustSize()


        # Assemble UI tree
        layout.addWidget(self.title_label)
        layout.addWidget(self.text_label)
        layout.addWidget(self.reboot_btn, alignment=Qt.AlignmentFlag.AlignCenter)

    def set_content(self, title, text):
        """Updates the labels dynamically when an error matches."""
        self.title_label.setText(title)
        self.text_label.setText(text)

class BarManager:

    def __init__(self, parent, eColsStyle, eColsButton):
        self.parent = parent
        self.eColsStyle = eColsStyle
        self.eColsButton = eColsButton

        
        

    def setup_url_bar(self):
        self.url_bar = QLineEdit()
        self.url_bar.returnPressed.connect(self.parent.load_url)
        self.url_bar.focusInEvent = self.parent._url_bar_focus_in
        self.parent.nav_bar.addWidget(self.url_bar)
        self.eColsStyle.append("url_bar")

        self.url_bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.url_bar.customContextMenuRequested.connect(self.parent.displayUrlBarContextMenu)
        return self.url_bar


    def setup_tabs(self):
        actionToggles = self.parent.settingsData
        if actionToggles["Tab-Position"] in ["North", "South"]:
            self.tabs = QTabWidget()
            self.tabs.tabBar().setElideMode(Qt.TextElideMode.ElideRight)
            self.tabs.tabBar().setExpanding(True)

        elif actionToggles["Tab-Position"] in ["East", "West"]:
            self.tabs = QTabWidget()
            self.tabs.setTabBar(VerticalTabBar())
            self.tabs.tabBar().setExpanding(False)
            self.tabs.tabBar().setElideMode(Qt.ElideNone)
            self.eColsButton.append("pintabs_btn")


        else:
            print("tab position loading error, defaulting to north")
            self.tabs = QTabWidget()
            self.tabs.tabBar().setElideMode(Qt.TextElideMode.ElideRight)
            self.tabs.tabBar().setExpanding(True)

        self.eColsStyle.append("tabs")
        self.eColsStyle.append("tab_backer")
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.tabBar().setStyleSheet("""QTabBar::tab {
                                                height: 35px;
                                                width: 200px;
                                            }
                                            """)
                                         
        self.tabs.tabBar().setUsesScrollButtons(True)
        return self.tabs
    

    def setup_navbar(self):
        self.nav_bar = QToolBar("Navigation")
        self.nav_bar.setMovable(False)
        self.nav_bar.setStyleSheet("background:rgb(1, 1, 100)")
        self.eColsStyle.append("nav_bar")


        #main button constructors
        self.ButtonConstructor("back_btn", "Back", "back", "go_back")
        self.ButtonConstructor("reload_btn", "Reload", "reload", "reload_tab")
        self.ButtonConstructor("forward_btn", "Forward", "forward", "go_forward")
        self.ButtonConstructor("home_btn", "Home", "home", "go_home")
        self.ButtonConstructor("newtab_btn", "New Tab", "newtab", "new_tab")
        self.ButtonConstructor("settings_btn", "Settings", "settings", "open_settings_menu")

        #reload animation components
        self.rotation_angle = 0
        self.parent.rotation_timer = QTimer()
        self.parent.rotation_timer.timeout.connect(self.rotate_reload_icon)
        self.parent.current_browser.loadStarted.connect(self.start_reload_animation)
        self.parent.current_browser.loadFinished.connect(self.stop_reload_animation)


        return self.nav_bar

    def setup_statusbar(self, profile_icon=None, name=None):
        self.status_bar = QToolBar("Status")
        self.status_bar.setMovable(False)

        self.status_bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.status_bar.customContextMenuRequested.connect(lambda pos: self.parent.displayStatusBarContextMenu(pos, self.status_bar, "Status Bar"))

        self.eColsStyle.append("status_bar")

        #spacer widget
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        #controls the date display
        self.dateBox = QLineEdit()
        self.dateBox.setReadOnly(True)
        self.dateBox.setPlaceholderText("...")
        self.dateBox.setMaximumWidth(300)
        
        #controls the time display
        self.timeBox = QLineEdit()
        self.timeBox.setReadOnly(True)
        self.timeBox.setPlaceholderText("...")
        self.timeBox.setMaximumWidth(150)

        #controls the zoom display and slider
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setMinimum(0)
        self.zoom_slider.setMaximum(300)
        self.zoom_slider.setValue(100)
        self.zoom_slider.setFixedWidth(self.status_bar.width() // 3)
        self.zoom_slider.sliderMoved.connect(self.on_zoom_slider_moved)

        #dispay based on current zoom value, press to return to 100% exactly
        self.zoomDisplay = QPushButton("100%")
        self.zoomDisplay.clicked.connect(lambda: self.zoom_slider.setValue(100))
        self.zoom_slider.valueChanged.connect(lambda value: (self.zoomDisplay.setText(f"{value}%"), self.on_zoom_slider_moved(value)))

        self.zoomDisplay.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.zoomDisplay.customContextMenuRequested.connect(lambda pos: self.parent.displayStatusBarContextMenu(pos, self.zoomDisplay, "zoomDisplay"))

        self.helpButton = QPushButton()
        helpIcon = QImage()
        try:
            if helpIcon.load(str(f"{srcSourceDir}/ui/icon_cache/help.png")):
                pixmapIcon = QPixmap.fromImage(helpIcon)
                self.helpButton.setIcon(QIcon(pixmapIcon))
                self.helpButton.setIconSize(QSize(16, 16))
            else:
                print("Failed to load help button icon")
        except Exception as e:
            print(f"Error loading help icon: {e}")
        self.helpButton.clicked.connect(lambda: self.parent.UIHelper("General"))


        self.profileDisplay = QPushButton(name if name else "Unnamed")
        if profile_icon:
            try:
                print(f"Loading profile icon from: {profile_icon}")
                image = QImage()
                if image.load(str(profile_icon)):
                    pixmap = QPixmap.fromImage(image)
                    self.profileDisplay.setIcon(QIcon(pixmap))
                    self.profileDisplay.setIconSize(QSize(16, 16))
                else:
                    print(f"Failed to load image from: {profile_icon}")
            except Exception as e:
                print(f"Error loading profile icon: {e}")
        #is there a way to make this reopen the profile selection menu?
        self.profileDisplay.clicked.connect(self.parent.open_profile_menu)

        self.profileDisplay.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.profileDisplay.customContextMenuRequested.connect(lambda pos: self.parent.displayStatusBarContextMenu(pos, self.profileDisplay, "profileDisplay"))



        #sets the displays to the bar
        self.status_bar.addWidget(self.profileDisplay)
        self.status_bar.addWidget(self.zoom_slider)
        self.status_bar.addWidget(self.zoomDisplay)
        self.status_bar.addWidget(spacer)
        self.status_bar.addWidget(self.timeBox)
        self.status_bar.addWidget(self.dateBox)
        self.status_bar.addWidget(self.helpButton)


        #runs the update timer
        self.barUpdateTimer = QTimer(self.parent)
        self.barUpdateTimer.timeout.connect(self.updateStatusBar)
        self.barUpdateTimer.start(1000)

        return self.status_bar
    
    def on_zoom_slider_moved(self, value):
        self.parent.tab_zoom_values[self.parent.current_browser] = value
        self.parent.zoomValue = value
        self.parent.current_browser.setZoomFactor(value / 100)
        self.zoomDisplay.setText(f"{value}%")

    def updateStatusBar(self):
        settingsDataPull = self.parent.settingsData
        
        #time return - pulls from same system as new tab window display
        timeFormat = (settingsDataPull["Time-Display"])
        timeCall = QDateTime.currentDateTime()
        time_text = timeCall.toString(f"{timeFormat}")
        self.timeBox.setText(time_text)
        time_metrics = QFontMetrics(self.timeBox.font())
        time_width = time_metrics.horizontalAdvance(time_text) + 16
        self.timeBox.setFixedWidth(time_width)



        #date return - pulls from same system as new tab window display
        date_format, provide_year = settingsDataPull["Date-Display"][0], settingsDataPull["Date-Display"][1]
        dateCall = QDateTime.currentDateTime()

        # Define base formats without year info
        format_map = {
                "dd/MM": "Global",
                "M/d": "US",
                "MM-dd": "ISO",  
                "dddd, d MMMM": "Long-Form",
                "dd MMM": "Minimalist"
            }
        
        if date_format in format_map.keys():
            base = format_map[date_format]

            # Specific year-attachment logic per format
            if provide_year:
                if base == "ISO":
                    date_format = f"yyyy-{date_format}"
                elif base in ["Global", "US"]:
                    date_format += "/yyyy"
                else: # Long-Form and Minimalist
                    date_format += " yyyy"

        else:
            if provide_year:  
                date_format += " yyyy"
            else:
                pass
        date_text = dateCall.toString(date_format)
        self.dateBox.setText(date_text)
        date_metrics = QFontMetrics(self.dateBox.font())
        date_width = date_metrics.horizontalAdvance(date_text) + 16
        self.dateBox.setFixedWidth(date_width)
    
    def setup_bookmarksbar(self, bookmarksData):
        self.bookmarks_bar = QToolBar("Bookmarks")
        self.bookmarks_bar.setMovable(False)
        self.bookmarks_bar.setStyleSheet("background:rgb(1, 1, 100)")
        self.eColsStyle.append("bookmarks_bar")
        self.eColsButton.append("bookmarks_btn")

        try:
            bookmarkData = bookmarksData
            
            for bid, data in bookmarkData.items():
                name = data["name"]
                url = data["url"]
                Bbutton = QPushButton(name.capitalize())

                FAVurl = f"https://www.google.com/s2/favicons?domain={QUrl(url).host()}&sz=32"
                response = requests.get(FAVurl)
                if response.status_code == 200: 
                    image = QImage()
                    image.loadFromData(response.content)
                    pixmap = QPixmap.fromImage(image)
                else:
                    #use image for tabIcon.png
                    pixmap = QPixmap(str(icon_cache_dir / "tabIcon.png"))

                Bbutton.setIcon(QIcon(pixmap))
                Bbutton.setIconSize(QSize(16, 16))
                Bbutton.clicked.connect(partial(self.parent.load_url, qurl=QUrl(url), label=name))
                Bbutton_action = QWidgetAction(self.parent)
                Bbutton_action.setDefaultWidget(Bbutton)

                #Right click context menu 
                Bbutton.setContextMenuPolicy(Qt.CustomContextMenu)
                Bbutton.customContextMenuRequested.connect(partial(self.parent.displayBookmarksContextMenu, Bbutton, bid, bookmarkData))

                self.bookmarks_bar.addAction(Bbutton_action)

        except json.decoder.JSONDecodeError:
            print("No bookmarks saved, skipping.")

        return self.bookmarks_bar
    

    def refresh_bookmarksbar(self, bookmarksData):
        self.bookmarks_bar.clear()
        try:
            bookmarkData = bookmarksData
            for bid, data in bookmarkData.items():
                name = data["name"]
                url = data["url"]
                btn = QPushButton(name.capitalize())

                try:
                    domain = QUrl(url).host()
                    icon_url = f"https://www.google.com/s2/favicons?domain={domain}&sz=32"
                    response = requests.get(icon_url, timeout=5)

                    if response.status_code == 200:
                        image = QImage()
                        image.loadFromData(response.content)
                        pixmap = QPixmap.fromImage(image)
                    else:
                        pixmap = QPixmap(str(icon_cache_dir / "tabIcon.png"))

                except:
                    pixmap = QPixmap(str(icon_cache_dir / "tabIcon.png"))

                btn.setIcon(QIcon(pixmap))
                btn.setIconSize(QSize(16, 16))

                btn.clicked.connect(
                    lambda checked, t=url, l=name: self.parent.add_new_tab(qurl=t, label=l)
                )

                action = QWidgetAction(self.parent)
                action.setDefaultWidget(btn)
                self.bookmarks_bar.addAction(action)

            #link to right click context menu after refreshing
            btn.setContextMenuPolicy(Qt.CustomContextMenu)
            btn.customContextMenuRequested.connect(partial(self.show_bookmark_menu, btn, bid, bookmarkData))
        except (json.decoder.JSONDecodeError, UnboundLocalError):
            print("Can't refresh bookmarks as none exist in the json file!")
            pass
    
    
    def setupContextMenu(self):
        # Parent it to the main window/browser class
        RContextMenu = QMenu(self.parent)

        # Default button actions
        backClick = QAction("Go Back", self.parent)
        backClick.triggered.connect(self.parent.go_back)
        RContextMenu.addAction(backClick)

        forwardClick = QAction("Go Forward", self.parent)
        forwardClick.triggered.connect(self.parent.go_forward)
        RContextMenu.addAction(forwardClick)

        reloadClick = QAction("Reload Page", self.parent)
        reloadClick.triggered.connect(self.parent.reload_tab)
        RContextMenu.addAction(reloadClick)

        return RContextMenu


    def ButtonConstructor(self, name, tooltip, icon, handler_name):
        """Creates all buttons for navbar"""
        btn = QToolButton(self.parent)
        btn.setToolTip(tooltip)
        btn.setText(name)
        btn.setIcon(get_normIcon(icon))
        self.nav_bar.addWidget(btn)

        #Dynamically attach button to object data
        setattr(self.parent, name, btn)

        #Connect to class method
        if hasattr(self.parent, handler_name):
            btn.clicked.connect(getattr(self.parent, handler_name))
        else:
            print(f"WARNING! Handler name {handler_name} not found")
        
        self.eColsButton.append(name)

        btn.setContextMenuPolicy(Qt.CustomContextMenu)
        btn.customContextMenuRequested.connect(lambda pos, b=btn: self.parent.displayContextMenu(pos, b))

        
        return btn
    
    #reload icon animations
    def rotate_reload_icon(self):
        """Rotate the reload icon continuously"""
        self.rotation_angle = (self.rotation_angle + 10) % 720
        base_icon = get_normIcon("reload")
        pixmap = base_icon.pixmap(24, 24)
        
        transform = QTransform().rotate(self.rotation_angle)
        rotated_pixmap = pixmap.transformed(transform, Qt.SmoothTransformation)
        self.parent.reload_btn.setIcon(QIcon(rotated_pixmap))
    
    def start_reload_animation(self):
        if not self.parent.rotation_timer.isActive():
            self.parent.rotation_timer.start(0.01)  # adjust speed here (ms per frame)
    
    def stop_reload_animation(self):
        if self.parent.rotation_timer.isActive():
            self.parent.rotation_timer.stop()
        # reset icon to upright
        self.rotation_angle = 0
        self.parent.reload_btn.setIcon(get_normIcon("reload"))

    def setup_colourPalette_button(self, Colourdata):
        self.colourpalette_btn = QToolButton(self.parent)
        self.colourpalette_btn.setToolTip("Colour Palettes")
        self.ColourMenu = QMenu(self.parent)
        
        self.update_colourPalette_menu(Colourdata)

        self.colourpalette_btn.setPopupMode(QToolButton.MenuButtonPopup)
        self.parent.nav_bar.addWidget(self.colourpalette_btn)
        self.eColsButton.append("colourpalette_btn")

        self.colourpalette_btn.setContextMenuPolicy(Qt.CustomContextMenu)
        self.colourpalette_btn.customContextMenuRequested.connect(lambda pos, b=self.colourpalette_btn: self.parent.displayContextMenu(pos, b))

        return self.colourpalette_btn, self.ColourMenu
    
    def update_colourPalette_menu(self, Colourdata):
        self.Colourdata = Colourdata

        self.ColourMenu = QMenu(self.parent)
        
        for key in Colourdata.keys():
            # Widgets for Menu Items
            Cwidget = QWidget()
            Clayout = QHBoxLayout(Cwidget)
            Clayout.setContentsMargins(5, 2, 5, 2)
            Clayout.setSpacing(5)

            #Add text
            Ctext_label = QLabel(key.capitalize())
            Ctext_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            Clayout.addWidget(Ctext_label)

            #Create Widget Action
            Cwidget_action = QWidgetAction(self.parent)
            Cwidget_action.setDefaultWidget(Cwidget)
            Cwidget_action.setData(key)
            Cwidget_action.triggered.connect(lambda checked, p=key, d=Colourdata: self.parent.SelectColourTheme(p, d))
            self.ColourMenu.addAction(Cwidget_action)

        
        self.colourpalette_btn.setMenu(self.ColourMenu)
        self.colourpalette_btn.setIcon(get_normIcon("colourpalette"))

        # When the main button is clicked, read the current selectedprofile at click time
        self.colourpalette_btn.clicked.connect(lambda checked=False, d=Colourdata: self.parent.ToggleColourTheme(self.parent.selectedprofile, d))

        self.ColourMenu.setWindowFlags(self.ColourMenu.windowFlags() | Qt.WindowType.FramelessWindowHint)
        self.ColourMenu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.parent.style().unpolish(self.ColourMenu)
        self.parent.style().polish(self.ColourMenu)
        self.ColourMenu.update()


    def setup_engine_button(self, engines):
        self.engine_btn = QToolButton(self.parent)
        self.engine_btn.setText("Search With...")
        self.browserMenu = QMenu(self.parent)
        self.engine_btn.setToolTip("Select/Switch Search Engines")


            
        self.engine_btn.setMenu(self.browserMenu)
        self.engine_btn.setIcon(QIcon(str(icon_cache_dir / f"{self.parent.engine}")))

        self.engine_btn.clicked.connect(lambda: self.parent.current_browser.setUrl(QUrl(engines[self.parent.engine]["URL"].split('/search?q=')[0])))

        self.engine_btn.setPopupMode(QToolButton.MenuButtonPopup)
        self.parent.nav_bar.addWidget(self.engine_btn)

        self.engine_btn.setContextMenuPolicy(Qt.CustomContextMenu)
        self.engine_btn.customContextMenuRequested.connect(lambda pos, b=self.engine_btn: self.parent.displayContextMenu(pos, b))

        self.update_engine_menu(engines)

        self.parent.set_engine(self.parent.engine)

        return self.engine_btn, self.browserMenu
    
    def update_engine_menu(self, engines):
        self.engines = engines

        if hasattr(self, 'browserMenu') and self.browserMenu:
            if hasattr(self.parent, 'RContextMenu') and self.parent.RContextMenu:
                # Reset parent back to the main window frame
                self.parent.RContextMenu.setParent(self.parent, self.parent.RContextMenu.windowFlags())
            
            self.engine_btn.setMenu(None)  
            self.browserMenu.deleteLater() 

        self.browserMenu = QMenu(self.parent)

        for key, value in engines.items():
            # Create widget for menu item
            widget = QWidget()
            layout = QHBoxLayout(widget)
            layout.setContentsMargins(5, 2, 5, 2)
            layout.setSpacing(5)
            widget.setContextMenuPolicy(Qt.CustomContextMenu)
            widget.customContextMenuRequested.connect(lambda pos, w=widget, k=key: self.parent.displayEngineContextMenu(pos, w, k))
            
            # Add icon
            icon_label = QLabel()
            icon = get_cached_favicon(key, value["URL"], icon_cache_dir)
            icon_label.setPixmap(icon.pixmap(16, 16))
            layout.addWidget(icon_label)
            icon_label.setFixedWidth(30) 
            
            # Add text
            text_label = QLabel(key.capitalize())   
            text_label.setObjectName(f"browser_menu_text_label_{key}")
            text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(text_label)

            # Create QWidgetAction and set the custom widget
            widget_action = QWidgetAction(self.parent)
            widget_action.setDefaultWidget(widget)
            widget_action.setData((key, value["URL"]))
            widget_action.triggered.connect(lambda checked, k=key: self.parent.set_engine(k))

            self.browserMenu.addAction(widget_action)

        #create 'add new engine' button
        ANwidget = QWidget()
        ANlayout = QHBoxLayout(ANwidget)
        ANlayout.setContentsMargins(5, 2, 5, 2)
        ANlayout.setSpacing(5)

        ANicon_label = QLabel()
        ANicon = QIcon(str(icon_cache_dir / "new_engine.png"))
        ANicon_label.setPixmap(ANicon.pixmap(16, 16))
        ANlayout.addWidget(ANicon_label)
        ANicon_label.setFixedWidth(30)

        ANtext_label = QLabel("Add New Engine")
        ANtext_label.setObjectName("browser_menu_text_label_new_engine")
        ANtext_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ANlayout.addWidget(ANtext_label)

        ANwidget_action = QWidgetAction(self.parent)
        ANwidget_action.setDefaultWidget(ANwidget)
        ANwidget_action.setData(("new_engine", None))
        ANwidget_action.triggered.connect(lambda: self.parent.add_new_engine())
        self.browserMenu.addAction(ANwidget_action)

        self.engine_btn.setMenu(self.browserMenu)
        self.engine_btn.setIcon(QIcon(str(icon_cache_dir/f"{self.parent.engine}")))

        self.browserMenu.setWindowFlags(self.browserMenu.windowFlags() | Qt.WindowType.FramelessWindowHint)
        self.browserMenu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.parent.style().unpolish(self.browserMenu)
        self.parent.style().polish(self.browserMenu)
        self.browserMenu.update()



    def setup_cookie_button(self):
        self.eColsButton.append("cookie_btn")
        self.cookie_btn = QToolButton(self.parent)
        self.cookie_btn.setText("cookie_btn")
        self.cookie_btn.setToolTip("Accept/Deny Cookies")
        self.cookieMenu = QMenu(self.parent)
        setattr(self, "cookie_btn", self.cookie_btn)

        self.cookie_btn.setMenu(self.cookieMenu)
        self.cookie_btn.setIcon(get_normIcon("cookie"))
        self.cookie_btn.setPopupMode(QToolButton.InstantPopup)
        self.nav_bar.addWidget(self.cookie_btn)

        self.cookie_btn.setContextMenuPolicy(Qt.CustomContextMenu)
        self.cookie_btn.customContextMenuRequested.connect(lambda pos, b=self.cookie_btn: self.parent.displayContextMenu(pos, b))

        return self.cookie_btn, self.cookieMenu
    
    def update_cookie_menu(self, row_colour):
        #Scroll bar system
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setStyleSheet(f"""
            QScrollArea {{
                background-color: {self.parent.hexval};
                border: none;
            }}
            /* Target the internal container specifically */
            QScrollArea > QWidget > QWidget {{ 
                background-color: {self.parent.hexval};
            }}
            /* Custom Scrollbar styling to make it look modern */
            QScrollBar:vertical {{
                border: none;
                background: {self.parent.hexval};
                width: 8px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(255, 255, 255, 0.3); /* Semi-transparent white */
                min-height: 20px;
                border-radius: 4px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)
        
        # Set max height to prevent the menu from growing off-screen
        scroll_area.setMaximumHeight(400)
        scroll_area.setFixedWidth(500)

        #Row Containers
        container_widget = QWidget()
        container_layout = QVBoxLayout(container_widget)
        container_layout.setContentsMargins(5, 5, 5, 5)
        container_layout.setSpacing(8)

        #Add rows to scroll bar
        for cookieID, value in self.parent.cookiedict.items():
            cookie_row = QWidget()
            cookie_row.setObjectName("CookieRow")
            row_layout = QHBoxLayout(cookie_row)
            
            name = (value["name"][:15] + "..") if len(value["name"]) > 15 else value["name"]
            name_label = QLabel(name)
            predict_label = QLabel(f"({value['prediction']})")
            predict_label.setStyleSheet(f"color: {self.parent.hexval}; font-size: 10px;")
            
            btn_accept = QPushButton("✓")
            btn_deny = QPushButton("✕")

            btn_accept.setStyleSheet(f"background-color: {self.parent.hexval}; color: {row_colour};")
            btn_deny.setStyleSheet(f"background-color: {self.parent.hexval}; color: {row_colour};")
            
            # Connect buttons (using the handle_cookie_action from previous step)
            btn_accept.clicked.connect(lambda _, Cid=cookieID: self.parent.handle_cookie_action(Cid, "accept"))
            btn_deny.clicked.connect(lambda _, Cid=cookieID: self.parent.handle_cookie_action(Cid, "deny"))

            row_layout.addWidget(name_label)
            row_layout.addWidget(predict_label)
            row_layout.addStretch()
            row_layout.addWidget(btn_accept)
            row_layout.addWidget(btn_deny)

            # Styling
            cookie_row.setStyleSheet(f"#CookieRow {{ background-color: {row_colour}; border-radius: 6px; }}")
            
            container_layout.addWidget(cookie_row)

        # Add a stretch at the end to keep rows at the top if there are few
        container_layout.addStretch()
        
        #Apply widget to scroll area
        scroll_area.setWidget(container_widget)
        
        # Host the entire ScrollArea inside one QWidgetAction
        menu_scroll_action = QWidgetAction(self.cookieMenu)
        menu_scroll_action.setDefaultWidget(scroll_area)
        self.cookieMenu.addAction(menu_scroll_action)

        return self.cookieMenu
    

    def get_muted_icon(self, original_icon):
        # Convert your existing icon into a pixel map (standard 16x16 size for tabs)
        pixmap = original_icon.pixmap(16, 16)
        
        # Initialize a painter to draw directly onto the image
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Define a thick, clean red line for the slash
        pen = QPen(QColor("red"), 2) 
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        
        # Draw a diagonal line from top-right to bottom-left
        painter.drawLine(14, 2, 2, 14)
        painter.end()
        
        # Return it as a brand new QIcon
        return QIcon(pixmap)
    


class VerticalTabBar(QTabBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.hovered_index = -1
        self.update_close_buttons()
        self.update_hover_from_cursor()
        self.currentChanged.connect(lambda _: self.update_hover_from_cursor())
        self.tabMoved.connect(lambda *_: self.update_hover_from_cursor())
        QTimer.singleShot(0, self.hideStarterTabClose)
        self.hover_timer = QTimer(self)
        self.hover_timer.timeout.connect(self.update_hover_from_cursor)
        self.hover_timer.start(16)

        #Compact mode systems
        self.autoCompact = True
        self.compact_mode = True
        self.expanded_width = 200
        self.collapsed_width = 48

        self.width_anim = QPropertyAnimation(self, b"minimumWidth")
        self.width_anim.setDuration(300)
        self.width_anim.setEasingCurve(QEasingCurve.OutQuint)
        self.setMinimumWidth(self.collapsed_width)
        self.setMaximumWidth(self.expanded_width)

        self.compact_timer = QTimer(self)
        self.compact_timer.setSingleShot(True)
        self.compact_timer.timeout.connect(lambda: (self.set_compact_mode(True), self.update_close_buttons()))

        self.width_anim.valueChanged.connect(lambda v: self.setMaximumWidth(v) if self.compact_mode else None)

        #Toggle Mode Pin Button
        self.pin_btn = QPushButton(self)
        self.pin_btn.setCheckable(True)
        self.pin_btn.setToolTip("Pin Tab Bar")
        self.pin_btn.clicked.connect(self.toggle_pin)
        self.pin_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                outline: none;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
                border-radius: 5px; 
            }
        """)

        self.default_pin_path = f"{srcSourceDir}/ui/icon_cache/pintabs.png"
        self.pin_btn.setIconSize(QSize(24, 24))

    def toggle_pin(self, checked):
        self.autoCompact = not checked
        if checked:
            self.compact_timer.stop()
            self.set_compact_mode(False)
        else:
            if not self.rect().contains(self.mapFromGlobal(QCursor.pos())):
                self.compact_timer.start(500)
                
        self.update_pin_icon() # This handles the rotation logic

    def update_pin_icon(self):
        size = self.pin_btn.iconSize()
        if size.width() <= 0: size = QSize(24, 24)
        pixmap = QPixmap(self.default_pin_path).scaled(size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        
        
        if pixmap.isNull():
            print(f"Error: Could not load icon at {self.default_pin_path}")
            return
        
        if not self.autoCompact:
            rotated = QPixmap(pixmap.size())
            rotated.fill(Qt.GlobalColor.transparent)
            painter = QPainter(rotated)
            if painter.isActive() or painter.begin(rotated):
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                painter.translate(rotated.width() / 2, rotated.height() / 2)
                painter.rotate(-45)
                painter.drawPixmap(-pixmap.width() / 2, -pixmap.height() / 2, pixmap)
                painter.end()
                pixmap = rotated

        self.pin_btn.setIcon(QIcon(pixmap))
        self.pin_btn.setIconSize(QSize(20, 20)) # Slightly smaller than the 30px button

    def update_pin_button_pos(self):
        btn_size = 30
        x = (self.width() - btn_size) // 2
        y = self.height() - btn_size - 5  # 5px padding from bottom
        self.pin_btn.setGeometry(x, y, btn_size, btn_size)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_pin_button_pos()

    def enterEvent(self, event):
        if self.autoCompact:
            self.compact_timer.stop()
            self.set_compact_mode(False)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self.autoCompact:
            self.compact_timer.start(500)
        super().leaveEvent(event)



    def tabSizeHint(self, index):
        # This makes the tabs follow the animation frame-by-frame
        return QSize(self.width(), 35) 

    def set_compact_mode(self, enabled: bool):
        if self.compact_mode == enabled:
            return
        self.compact_mode = enabled
        
        target = self.collapsed_width if enabled else self.expanded_width
        
        self.width_anim.stop()
        self.width_anim.setStartValue(self.width())
        self.width_anim.setEndValue(target)
        
        # Force the maximum width to expand so the minimum animation isn't blocked
        if not enabled: 
            self.setMaximumWidth(self.expanded_width)
        
        self.width_anim.start()

    def update_hover_from_cursor(self):
        pos = self.mapFromGlobal(QCursor.pos())

        if not self.rect().contains(pos):
            new_hover = -1
        else:
            new_hover = self.tabAt(pos)

        if new_hover != self.hovered_index:
            self.hovered_index = new_hover
            self.update_close_buttons()
            self.update()

    def update_close_buttons(self):
        for i in range(self.count()):
            btn = self.tabButton(i, QTabBar.RightSide)

            if btn:
                btn.move(
                    self.tabRect(i).right() - btn.width() - 5,
                    self.tabRect(i).center().y() - btn.height() // 2
                )

                is_hovered = (i == self.hovered_index)
                btn.setVisible(is_hovered)

    def hideStarterTabClose(self):
        for i in range(self.count()):
            btn = self.tabButton(i, QTabBar.RightSide)
            if btn:
                btn.hide()

    def paintEvent(self, event):
        painter = QStylePainter(self)

        for i in range(self.count()):
            option = QStyleOptionTab()
            self.initStyleOption(option, i)

            text = option.text
            icon = self.tabIcon(i)

            # Remove both so Qt doesn't draw them
            option.text = ""
            option.icon = QIcon()

            # Draw tab background + state
            painter.drawControl(QStyle.CE_TabBarTab, option)

            rect = self.tabRect(i)

            # --- ICON ---
            icon_size = QSize(16, 16)
            if self.compact_mode:
                icon_x = rect.center().x() - icon_size.width() // 2
            else:
                icon_x = rect.left() + 8
            icon_y = rect.center().y() - icon_size.height() // 2

            if not icon.isNull():
                painter.drawPixmap(
                    icon_x,
                    icon_y,
                    icon.pixmap(icon_size)
                )

            # --- TEXT ---
            if self.width() > self.collapsed_width + 20:

                text_color = self.tabTextColor(i)

                painter.setPen(text_color)

                text_rect = QRect(
                    icon_x + icon_size.width() + 6,
                    rect.top(),
                    rect.width() - (icon_size.width() + 10),
                    rect.height()
                )

                painter.drawText(
                    text_rect,
                    Qt.AlignVCenter | Qt.AlignLeft,
                    text
                )


class DynamicRatioButton(QPushButton):
    def __init__(self, name, ratio, parent=None):
        super().__init__(name, parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.ratio = ratio


    def resizeEvent(self, event):
        super().resizeEvent(event)
        new_height = int(self.width() / self.ratio)
        self.setFixedHeight(new_height)

class ClickableImage(QFrame):

    def __init__(self, pixmap, parent=None):
        super().__init__(parent)

        self.fullPixmap = pixmap
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("ClickableImageFrame")
        self.setStyleSheet("""
            QFrame#ClickableImageFrame{
                border:4px solid #3f81ff;
                border-radius:15px;
                background:transparent;
            }

            QLabel{
                border:none;
                background:transparent;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5,5,5,5)

        self.imageLabel = QLabel()
        self.imageLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.imageLabel.setStyleSheet("""border:none; background:transparent;""")

        scaled = pixmap.scaled(500, 300, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.imageLabel.setPixmap(scaled)

        layout.addWidget(self.imageLabel)

        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFixedSize(self.sizeHint())

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.showLargePreview()

    def showLargePreview(self):

        popup = QDialog(self)
        popup.setWindowTitle("Image Preview")
        popup.resize(1200,800)

        layout = QVBoxLayout(popup)
        label = QLabel()
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scaled = self.fullPixmap.scaled(1100, 700, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        label.setPixmap(scaled)
        layout.addWidget(label)


        closeBtn = QPushButton("✕", popup)
        closeBtn.setFixedSize(36,36)
        closeBtn.setStyleSheet("""
            QPushButton{
                background:rgba(20,20,25,200);
                color:white;
                border:2px solid #3f81ff;
                border-radius:5px;
                font-size:16px;
                font-weight:bold;
            }

            QPushButton:hover{
                background:rgba(50,50,70,220);
            }
        """)
        closeBtn.clicked.connect(popup.accept)
        closeBtn.raise_()
        closeBtn.move(24, 24)

        popup.exec()



class SystemHelperUI(QDialog):
    def __init__(self, parent, displayData, buttonClicked, selectedFromSettings):
        super().__init__(parent)
        self.setWindowTitle("Midnight Watch Help")
        self.resize(950, 700)
        self.setWindowIcon(get_normIcon("tightlyCroppedIcon.png"))
        self.parent = parent
        self.displayData = displayData
        self.ratio_buttons = []
        self.buttonClicked = buttonClicked
        self.sidebar_buttons = {}
        self.selectedFromSettings = selectedFromSettings

        self.NormalStyle = """
            QPushButton {
                background-color: rgb(60,60,75);
                color:white;
                border:2px solid rgb(63,129,255);
                border-radius:10px;
                font-size:14px;
                font-weight:bold;
            }

            QPushButton:hover {
                background-color: rgb(70,70,85);
                border:2px solid rgb(96,151,253);
            }

            QPushButton QLabel {
                background: transparent;
                border: none;
                color: white;
            }
            """

        self.SelectedStyle = """
            QPushButton {
                background-color: rgb(85,105,160);
                color:white;
                border:4px solid #3f81ff;
                border-radius:10px;
                font-size:14px;
                font-weight:bold;
            }

            QPushButton:hover {
                background-color: rgb(100,120,180);
            }

            QPushButton QLabel {
                background: transparent;
                border: none;
                color: white;
            }
            """
        
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet("""
            QDialog {
                background-color: rgb(45, 45, 60);
            }
        """)

        # Main horizontal layout for the dialog window
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # LEFT SIDEBAR: Outer Scroll Area
        sidebarFrame = QWidget()
        sidebarFrame.setObjectName("sidebarFrame")
        sidebarFrame.setStyleSheet("""
            QWidget#sidebarFrame{
                background-color: rgb(45,45,60);
                border-radius:15px;
                border:5px solid #3f81ff;
            }
        """)
        sidebarLayout = QVBoxLayout(sidebarFrame)
        sidebarLayout.setContentsMargins(15,15,15,15)



        self.dataSelectArea = QScrollArea()
        self.dataSelectArea.setObjectName("dataSelectArea")
        self.dataSelectArea.setWidgetResizable(True)
        self.dataSelectArea.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.dataSelectArea.setStyleSheet("""
            QScrollArea#dataSelectArea{
                background-color: rgb(45, 45, 60);
                border: none;
                border-radius:15px;
            }
            QScrollBar:vertical {
                background: rgb(45, 45, 60);
                width: 12px;
                border-radius:15px;
            }
            QScrollBar::handle:vertical {
                background: rgb(85, 85, 105);
            }
            QScrollBar::handle:vertical:hover {
                background: rgb(110, 110, 135);
            }
        """)
        self.dataSelectArea.viewport().setStyleSheet("""
            background-color: rgb(45,45,60);
            border-radius:15px;
        """)

        # LEFT SIDEBAR: Inner Container Widget
        self.dataSelectContainer = QWidget()

        # Layout inside the left sidebar container
        self.buttonBox = QVBoxLayout(self.dataSelectContainer)
        self.buttonBox.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.buttonBox.setSpacing(15)
        self.buttonBox.setContentsMargins(15, 15, 15, 15)

        for key, value in self.displayData.items():
            self.buttonBox.addStretch()
            
            name = value[1]

            icon = QIcon()
            iconPixmap = (QPixmap(f"{srcSourceDir}/ui/icon_cache/{value[2]}"))
            icon.addPixmap(iconPixmap.scaled(50, 50, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))            


            btn = DynamicRatioButton(name=name, ratio=3)
            btn.setIcon(icon)
            btn.setStyleSheet(self.NormalStyle)
            self.ratio_buttons.append(btn)
            

            internal_id = value[1]
            self.sidebar_buttons[internal_id] = btn



            self.buttonBox.addWidget(btn)

            btn.clicked.connect(lambda checked=False, iid=internal_id: self.selectButton(iid))



        # Attach inner container to the left scroll area
        self.dataSelectArea.setWidget(self.dataSelectContainer)

        # RIGHT CONTENT: Main Area
        self.content_area = QScrollArea()
        self.content_area.setWidgetResizable(True)
        self.content_area.setStyleSheet("""
            QScrollArea {
                background-color: rgb(45, 45, 60); 
                border-radius: 15px; 
                border: 5px solid #3f81ff;
            }
            QScrollBar:vertical {
                background: rgb(45, 45, 60);
                width: 12px;
                border-radius:15px;
            }
            QScrollBar::handle:vertical {
                background: rgb(85, 85, 105);
            }
            QScrollBar::handle:vertical:hover {
                background: rgb(110, 110, 135);
            }
        """)

        sidebarLayout.addWidget(self.dataSelectArea)
        main_layout.addWidget(sidebarFrame, stretch=3)
        main_layout.addWidget(self.content_area, stretch=10)

        if not self.selectedFromSettings:
            QTimer.singleShot(0, lambda: self.selectButton(self.buttonClicked))
        else:
            self.renderMainUI("Starting")

    def selectButton(self, selected_id):
        self.buttonClicked = selected_id
        for internal_id, btn in self.sidebar_buttons.items():
            if internal_id == selected_id:
                btn.setStyleSheet(self.SelectedStyle)
                self.renderMainUI(self.buttonClicked)
            else:
                btn.setStyleSheet(self.NormalStyle)
    
    def renderMainUI(self, SelectedUI):        
        self.contentWidget = QWidget()
        self.contentWidget.setStyleSheet("background: transparent;")

        self.contentLayout = QVBoxLayout()
        self.contentLayout.setContentsMargins(20, 20, 20, 20)
        self.contentLayout.setSpacing(20)


        title = QLabel(SelectedUI + " Help")
        title.setStyleSheet("""
            color: #3f81ff;
            font-size: 30px;
            font-weight: 800;
        """)
        self.contentLayout.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)
        self.contentLayout.addSpacing(35)


        data = self.returnMainDisplay(SelectedUI)
        for key, value in data.items():
            if "text" in key:
                text = QLabel(value)
                text.setStyleSheet("""
                    color: white;
                    font-size: 15px;
                    margin-bottom: 5px;
                """)
                text.setWordWrap(True)
                text.adjustSize()
                self.contentLayout.addWidget(text)
            
            if "imagebox" in key:
                image = QPixmap(value)

                if not image.isNull():

                    label = ClickableImage(image)
                    label.setToolTip(f"Click to expand!")

                    self.contentLayout.addWidget(label, Qt.AlignmentFlag.AlignCenter)
            
            if "subtitle" in key:
                subtitle = QLabel(value)
                subtitle.setStyleSheet("""
                    color: #ffeb78;
                    font-size: 20px;
                    font-weight: 700;
                    margin-bottom: 5px;
                    text-decoration: underline;
                """)
                subtitle.setWordWrap(True)
                subtitle.adjustSize()
                self.contentLayout.addWidget(subtitle)

            if "subimage" in key:
                subtext = QLabel(value)
                subtext.setStyleSheet("""
                    color: grey;
                    font-size: 10px;
                    margin-bottom: 5px;
                """)
                subtext.setWordWrap(True)
                subtext.adjustSize()
                self.contentLayout.addWidget(subtext)


        self.contentLayout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.contentWidget.setLayout(self.contentLayout)
        self.content_area.setWidget(self.contentWidget)


    def returnMainDisplay(self, SelectedUI):
        DisplayUIText = {
            "General": {
                "subtitle1": "Welcome to the Midnight Watch Help Index",
                "text1": "This system is designed as a menu for you to look through each important component of the browser and see how it works on a deeper level.",
                "text2": "The left hand sidebar lets you scroll through all entries in the menu, and find out specific information on each one. You can also access help for a given button or object by right clicking on it and selecting it's help option.",
                "text3": "Not all entries in this menu are linked directly to buttons though, so we suggest taking a cursory look through the entries to find out more if you're curious!", #Add this if I decide to add extra sections with additional keybind components
                "imagebox1": f"{srcSourceDir}/ui/images/MainImageBackground.png",
                "subimage1": "^ Images and their related subtitles just like this one can be seen to give more context for what you're reading!",
                "text4": "These images can also be clicked on to open a viewing window if different parts are too difficult to see in their normal place! Press the X button or hit escape to close the viewing window when you're done!",
                "text5": "With that being said, enjoy the browser! If there are any other questions you may have, feel free to check some of the data entries on our website!"
            },
            "Back" : {
                "subtitle1": "The Back Button",
                "text1": "The back button allows you to undo your recent navigation actions and thus reload to previous pages of the active tab.",
                "subtitle2": "Location",
                "imagebox1": f"{srcSourceDir}/ui/help_image_cache/back_button_boxed.png",
                "subimage1": "^ Back button location on the toolbar",
                "subtitle3": "Important Info",
                "text3": "The back button stores a full history of the previous pages visited on the given tab, similar to the forward button.",
                "text4": "This is per-tab and is not stored after close or reboot.",
                "text5": "Note that you can also trigger this by pressing alt+left arrow"
            },
            "Forward": {
                "subtitle1": "The Forward Button",
                "text1": "The forward button allows you to undo your recent back-button presses and thus reload to previous pages of the active tab.",
                "subtitle2": "Location",
                "imagebox1": f"{srcSourceDir}/ui/help_image_cache/forward_button_boxed.png",
                "subimage1": "^ Forward button location on the toolbar",
                "subtitle3": "Important Info",
                "text3": "The forward button stores a full history of the previous pages visited on the given tab, similar to the back button.",
                "text4": "This is per-tab and is not stored after close or reboot.",
                "text5": "Note that you can also trigger this by pressing alt+right arrow"
            },
            "Home": {
                "subtitle1": "The Home Button",
                "text1": "The home button immediately sets the current active tab to the new tab page.",
                "subtitle2": "Location",
                "imagebox1": f"{srcSourceDir}/ui/help_image_cache/home_button_boxed.png",
                "subimage1": "^ Home button location on the toolbar",
                "subtitle3": "Important Info",
                "text2": "This does save to back/forward button history. You can use the arrow keys to restore previous pages navigated in case of an accidental click.",
            },
            "Reload": {
                "subtitle1": "The Reload Button",
                "text1": "The reload button forces the current active tab to reload its page.",
                "subtitle2": "Location",
                "imagebox1": f"{srcSourceDir}/ui/help_image_cache/reload_button_boxed.png",
                "subimage1": "^ Reload button location on the toolbar",
                "subtitle3": "Important Info",
                "text2": "The reload button is triggered by pressing the icon and can be seen to be processing while the icon is spinning.",
                "text3": "While reloading, any cookies linked to the tab that have been already saved will remain, however cookies in the selection list will be removed.",
                "text4": "Reloading also refreshes internal browser scripts, reloads the bookmark checks and lets internal content refresh if the site has been updated."
            },
            "Settings": {
                "subtitle1": "The Settings Button",
                "text1": "The settings button triggers the opening of a new tab that contains the settings menu, which allows users to customise internal settings.",
                "subtitle2": "Location",
                "imagebox1": f"{srcSourceDir}/ui/help_image_cache/settings_button_boxed.png",
                "subimage1": "^ Settings button location on the toolbar",
                "subtitle3": "Important Info",
                "text2": "The settings menu contains all important controls for the browser profile and how it should operate. The question mark boxes display the important information for each setting.",
                "text3": "Make sure to click apply for the settings to actually work. Certain settings also require a restart to ensure they apply properly, as they contain critical components that are only initialised at runtime.",
                "text4": "For example, the browser tab locations need a full refresh to change positions without breaking. The DNS controls hook into inbuilt HTTPS routing and therefore require reboots to refresh the internal cache.",
                "text5": f"Fun fact for developers, if you follow this filepath: \n\n[{srcSourceDir}/ui]\n\nYou can see all the internal settings buttons and even edit the html of the new page and settings page! Be careful though, the pages contain important hooks for saving and rendering data."
            },
            "New Tab": {
                "subtitle1": "The New Tab Button",
                "text1": "The new tab button creates a new tab and sets it to the new tab page.",
                "subtitle2": "Location",
                "imagebox1": f"{srcSourceDir}/ui/help_image_cache/newtab_button_boxed.png",
                "subimage1": "^ New tab button location on the toolbar",
                "subtitle3": "Important Info",
                "text2": "The new tab button always opens in a new tab and does not affect the current active tab. This is useful for quickly opening a fresh page to search or navigate to a new site while keeping your current page intact.",
                "text3": "Components of the new tab page, such as the background image, blur amount, displayed name, greeting, and time display can be changed from the settings menu.",
                "text4": f"As with the settings button, the new tab page can be customised by editing the html at \n\n[{srcSourceDir}/ui]\n\nJust be careful not to break the important hooks in the html that allow the page to function properly!"
            },
            "Colour Palettes": {
                "subtitle1": "The Colour Palettes Button",
                "text1": "The colour palette button allows you to select a colour palette for the browser, which changes the colours of various UI elements and the overall theme of the browser.",
                "subtitle2": "Location",
                "imagebox1": f"{srcSourceDir}/ui/help_image_cache/colourpalettes_button_boxed.png",
                "subimage1": "^ Colour palette button location on the toolbar",
                "subtitle3": "Important Info",
                "text2": "The colour palette system is accessible via the clickable button or the dropdown.",
                "text3": "The dropdown allows you to select from any of your saved colour palettes.",
                "imagebox2": f"{srcSourceDir}/ui/help_image_cache/colourpalettes_dropdown_boxed.png",
                "subimage2": "^ Dropdown location for the colourpalettes button",
                "text4": "Clicking on the toggle button will swap to the next profile in the list, descending down the options as provided in the dropdown.",
                "imagebox3": f"{srcSourceDir}/ui/help_image_cache/colourpalettes_toggle_boxed.png",
                "subimage3": "^ Toggle location for the colourpalettes button",
                "text5": "The colour palette system changes the colours of various UI elements, such as the toolbar, tab bar, scroll bars, buttons and backgrounds. It does not change the colours of web content, as that is determined by the websites themselves.",
                "text6": "Colour palettes are saved outside of the profile system and can be accessed from any profile.",
                "text7": "To make a colour theme of your own, visit the settings menu and click on the Themes page."
            },
            "Engines": {
                "subtitle1": "The Engine Button",
                "text1": "The engine button allows you to select a search engine for the url bar, which changes the search engine used when you type a query into the url bar and press enter without typing a full url.",
                "subtitle2": "Location",
                "imagebox1": f"{srcSourceDir}/ui/help_image_cache/engines_button_boxed.png",
                "subimage1": "^ Engine button location on the toolbar",
                "subtitle3": "Important Info",
                "text2": "The engine button automatically shows your current selected engine for a given search as it's icon. Clicking the icon opens the full webpage for searching with that engine if you'd rather use that than the normal url bars.",
                "imagebox2": f"{srcSourceDir}/ui/help_image_cache/engines_select_boxed.png",
                "subimage2": "^ Engine selection location on the toolbar",
                "text3": "The dropdown allows you to select from any of your saved search engines and apply it as the active one. The icon will be replaced to show that the change is saved.",
                "imagebox3": f"{srcSourceDir}/ui/help_image_cache/engines_dropdown_boxed.png",
                "subimage3": "^ Engine dropdown location on the toolbar",
                "text4": "Engines control how your browser operates to search queries that don't match specific site addresses (e.g. 'https://www.wikipedia.com' vs 'wikipedia'). Entering the former would redirect to the wikipedia site, where the latter is missing everything including the .com identifier, which means the browser defaults to using whichever engine you have selected.",
                "text5": "Four engines are currently available for search:\n - Google; the most common one\n - Brave; the common alternative\n - Duckduckgo; a surprisingly good contender for privacy\n - Ecosia; more privacy and lets you plant trees with searches!",
                "text6": "If you have an alternative to the main four, it can be added via the button at the bottom of the engine selection! Further, if you decide you don't want an engine in the system, just right click on the engine you don't want and click delete.",
                "text7": "Note that the search engine system applies to both the url bar and the new tab page search!"
            },
            "Cookies": {
                "subtitle1": "The Cookies Button",
                "text1": "The cookies button allows you to manage cookies on a per-site basis, leaving them in a pending state until you either accept or deny them. Additional cookie customisation like automatic acceptance or non-acceptance on closed tabs or enabling automatic passthrough can be found in settings.",
                "subtitle2": "Location",
                "imagebox1": f"{srcSourceDir}/ui/help_image_cache/cookies_button_boxed.png",
                "subimage1": "^ Cookies button location on the toolbar",
                "subtitle3": "Important Info",
                "text2": "Cookies are small packets of information that websites use to store data from their site onto your browser in order to preserve it for the next time you visit, or just to test different features.",
                "text3": "Cookies can be used for helpful website actions, such as keeping you logged in to specific sites, remembering your preferences for important data, or saving things like your shopping cart on an online store. However, they can also be used for malicious purposes, such as tracking your activity across the web, storing invasive data, or even being used as a vector for malware.",
                "text4": "With how invasive sites are becoming on forcing cookie acceptance for both good and bad terms, the cookie management system in the browser is designed to give you full control over which cookies you accept and which you deny, while also giving you the option to automatically accept or deny certain cookies based on rules you can set up in the settings menu.",
                "text5": "In addition, since the cookies are stored in a pending state until you accept or deny them, you can choose to leave cookies in the pending state if you want to browse without being spammed to turn off your cookie blockers, then deny them before leaving.",
                "imagebox2": f"{srcSourceDir}/ui/help_image_cache/cookies_dropdown_display.png",
                "subimage2": "^ Cookie management dropdown display when clicking the cookies button",
                "text6": "The cookie management dropdown shows you all the cookies that are currently pending for the active tabs' site, allowing you to accept or deny them with the click of a button. You can also see the predicted purpose of the cookie, which is determined by the internal cookie classification system. This can help you make informed decisions about which cookies to accept and which to deny.",
                "text7": "Note that if you ever want to remove all the cookies you have saved, a specialised button exists in settings to control it!",
                "text8": "Finally, if cookies ever get too annoying to constantly add and remove yourself, feel free to enable the automatic cookie accept system in settings. Recommended for use only with a filter strength of tier 2 or above."
            },
            "Tabs": {
                "subtitle1": "The Tabs Display",
                "text1": "The tabs display shows you all your open tabs and allows you to switch between them, close them, or open new ones. You can also see the title and icon of each tab, as well as right click to mute sounds from a tab.",
                "subtitle2": "Important Info",
                "text2": "The tabs display is a critical component of the browser, as it allows you to manage your open pages and navigate between them. You can also use keyboard shortcuts to switch between tabs, such as ctrl+left arrow to go to the next tab and ctrl+right arrow to go to the previous tab. Ctrl+W can be used to close the current active tab, and ctrl+T can be used to open a new tab. Ctrl+M will mute or unmute the current active tab, and you can also right click on a tab to access the mute option from the context menu.",
                "imagebox1": f"{srcSourceDir}/ui/help_image_cache/tabs_display_boxed.png",
                "subimage1": "^ The tabs display location on the toolbar",
                "subtitle3": "Additional Features",
                "text3": "Tabs can display vertically or horizontally based on your preference, which can be changed in the settings menu after a reboot. The vertical tab bar collapses when not hovered by the mouse, but can be pinned in place with the icon at the bottom of the tab section.",
                "imagebox2": f"{srcSourceDir}/ui/help_image_cache/vertical_tabs_boxed.png",
                "subimage2": "^ Vertical tabs display, showing the toggle button at the bottom of the sidebar.",
                "text4": "Tabs can also be rearranged to your preferences to allow organisation.",
                "text5": "Note that tabs are inextricably linked to the web content, which is why unfortunately it cannot be placed above the bookmarks or navigation bar similar to Google Chrome."
            },
            "Bookmarks": {
                "subtitle1": "The Bookmarks Display",
                "text1": "The bookmarks system allows you to save specific links and webpages in an easy-to-access format, displayable at either the top or bottom of your screen.",
                "subtitle2": "Important Info",
                "text2": "The bookmarks display stacks linearly across the screen to allow saving of any site you desire. You can choose to set a name for the bookmark or leave it blank. The image will update according to the page you select.",
                "imagebox1": f"{srcSourceDir}/ui/help_image_cache/bookmarks_display_boxed.png",
                "subimage1": "^ The bookmarks bar on the toolbar (can also be on the bottom depending on preference)",
                "text3": "Located on the url bar, you can save any page to a bookmark by pressing the empty star icon. If the star is full, it means you've already saved the tab to your bookmarks, and pressing the full star will allow you to instead remove the active bookmark.",
                "imagebox2": f"{srcSourceDir}/ui/help_image_cache/bookmarks_button_boxed.png",
                "subimage2": "^ The location of the bookmark icon. Note that it updates depending on the page!",
                "text4": "Bookmarks can be name-edited or deleted by right clicking over the specific button."
                #"text5": "Bookmarks that overflow the main bar will enter an overflow segment that can be scrolled between to see all available bookmarks." - add this when I fix that up!
            },
            "Url Bar": {
                "subtitle1": "The URL Bar",
                "text1": "The URL bar is the main way to access the web, by searching various terms using the engine system or otherwise entering specific URLs.",
                "imagebox1": f"{srcSourceDir}/ui/help_image_cache/urlbar_display_boxed.png",
                "subimage1": "^ The two available URL bars are that of the new tab page bar and the universal url bar.",
                "subtitle2": "Universal URL bar",
                "text2": "The universal URL bar is present in the navigation bar at all times. The universal bar has access to both the engine search (e.g. searching something on google) and specific link connections (e.g. directly entering youtube.com), letting you visit wherever you please.",
                "text3": "The universal URL bar also displays a sanitised version of the current active url to the site that you're on. See below for sanitised url definitions.",
                "subtitle3": "The New Tab Page URL Bar",
                "text4": "The new tab page URL bar is a smaller version of the url bar. It only supports conventional engine-based searches, but is present in every page and updates to your active selected engine. (see: engines button for more info)",
                "text5": "If your search query begins to overflow the search bar, you can simply scroll through to see what you've typed by using the arrow keys.",
                "subtitle4": "Sanitised URLs",
                "text6": "Midnight Watch utilises URL sanitisation to avoid providing websites extra tracking information. The url sanitiser is an inbuilt function for the url bar display, link interpreter, and even in the right click menu as 'copy cleaned url'.",
                "text7": "The URL sanitiser automatically strips out links like youtube's SI=<> which saves data like your browser type and what program you clicked the link from, and google's gclid which tracks specific browser information and system specifications.",
                "text8": "Note that the sanitiser can occasionally be a little aggressive and strip out things you want to keep in the url. If you notice this is a problem, feel free to submit a bug report" #maybe add an allow-list or some kind of identification system?
            },
            "Zooming": {
                "subtitle1": "Zooming",
                "text1": "The zoom controls allow for for consistent zooming in and out of the screen in order to improve site readability and navigability.",
                "imagebox1": f"{srcSourceDir}/ui/help_image_cache/zoom_display_boxed.png",
                "subimage1": "^ The two zoom control options available on the left of the status bar.",
                "text2": "The zoom controls are an element of the status bar. Move the status bar position and the zoom controls will move with it.",
                "subtitle2": "Zoom Display Bar",
                "text3": "The zoom display bar is one of the two zoom controls. It updates from a percentage of 50 to 500 and allows you to click and drag to any level of zoom between those values.",
                "text4": "The zoom display bar will update to whatever percentage was set by other methods too.",
                "subtitle3": "Zoom Percentage",
                "text5": "Similarly to the display bar, the zoom percentage updates it's text to show whatever percentage of zoom you are currently at. Pressing on the zoom percentage button will automatically set the zoom amount back to 100%",
                "subtitle4": "Miscellaneous",
                "text6": "Rather than content-zooming as most browsers do, remember that if you are on laptop, you can also two-finger spread zoom to specifically zoom into a given point rather than just zooming the whole page. This is independent from the main zoom controls, and cannot zoom out past 100%",
                "text7": "Zooming also has associated keybinds. Press ctrl+- to zoom out and ctrl+= to zoom in. The text and slider displays will update accordingly.",
                "text8": "Zooming works on a per-tab basis, so different tabs, even on the same site, can have different levels of zoom! Closing and reopening tab will reset it's zoom value to 100%."
            },
            "Profiles": {
                "subtitle1": "Profiles",
                "text1": "The profiles display is a system that allows you to swap between 'profiles' which locally store specific settings and (optional) data for your browsing experience.",
                "subtitle2": "Location",
                "text2": "The profile button showcases the current active profile in the status bar for user information. It can be clicked to open the profile selection UI.",
                "imagebox1": f"{srcSourceDir}/ui/help_image_cache/profile_button_boxed.png",
                "subimage1": "^ The location of the profile button. The icon is determined by the set profile's icon, the name by it's set name.",
                "text2": "During normal startup or otherwise by pressing the profiles button, you can access the profile selection menu. In this menu, you are able to add, edit the names and photos of, or delete any profiles in the list. The number of profiles is uncapped and any images and names are accessible through the file selection UI.",
                "imagebox2": f"{srcSourceDir}/ui/help_image_cache/profile_select_menu_display.png",
                "subimage2": "^ The general appearance of the profile selection menu",
                "text3": "Each profile within the browser contains it's own arrangement of settings, and can have a set colour theme per profile. Individual saved tabs and bookmarks are not transferred across profiles, so you can have a set of saved tabs and bookmarks per profile with no limitations.",
                "text4": "In specific circumstances such as settings-save reboots, the browser will preserve the profile state and bypass it's selection menu to ensure that everything saves properly. Besides that, every reboot or selection of the profiles button will allow you to quickly swap between your desired profiles.",
                "text5": "This data is all stored locally. No information about how you browse will ever leave your PC.",
                "subtitle3": "Preset profiles",
                "text6": "As you may or may not have noticed, three profiles currently exist in the menu, and you likely selected one to get here.",
                "imagebox3": f"{srcSourceDir}/ui/help_image_cache/profile_select_buttons_boxed.png",
                "subimage3": "^ The starting profiles upon browser loading.",
                "text7": "\n- The default profile is the assumed user experience, with enough privacy to get by comfortably and common options enabled. \n\n- The lax version prioritises the smoothest experience possible but at the cost of removing some security features. \n\n- Ephemeral mode has the maximum security policy set through settings, as well as an inbuilt storage deletion mechanism that ensures no data is kept after the browser is closed.\n\n- The add new profile button is not a profile and cannot be removed. You can click it to add a new profile with default settings, of which you can then change to your liking.\n",
                "text8": "Feel free to remove or customise these to you desire, their relevant settings can be found in the settings menu as expected.",
                "text9": "Note that if you accidentally press the profile switcher button, you can cancel the action by pressing escape or closing the popup window."
            },
            "Status Bar": {
                "subtitle1": "The Status Bar",
                "text1": "The status bar is the container for the allocated systems of profile handling, zoom controls, and external time and date display",
                "imagebox1": f"{srcSourceDir}/ui/help_image_cache/status_bar_display.png",
                "subimage1": "^ The full layout of the status bar as shown in the default browser profile",
                "text2": "The status bar, like all other bars, can have it's position customised. Location and hierarchical order can be changed in the settings, but by default it is at the bottom.",
                "subtitle2": "Overview of Components",
                "text3": "The zoom controls and profiles selector have their own entries in this help menu, but as a summary:",
                "text4": "The zoom controls adjust the content-zoom effect which determines the relative size scaling of all visible web-browsing elements. Zoom can be handled with ctrl+= and ctrl+- for zooming, or otherwise using the click and drag controls. Press the percentage button to reset to default 100% zoom \n",
                "text5": "The main profile display shows your current selected profile in both name and a small icon display. Click on it to open the profile selection UI to choose a different one, or otherwise cancel the action by pressing escape or closing the popup window. \n",
                "text6": "The date and time display are individual widgets that showcase the current time and date. Their display formatting draws from the specified time and date settings for the new tab menu, and can hence be customised in settings."
            },
            "Keybinds": {
                "subtitle1": "Overview",
                "text1": "Keybinds are keyboard shortcuts triggered by pressing an arrangement of keys at once, designed to conveniently perform actions for you. All browsers contain some types of keybinds, and we wanted to keep it consistent with Midnight Watch too.",
                "subtitle2": "Keybinds List",
                "text2": "Quit: Ctrl+Q",
                "text3": "Open Tab: Ctrl+T",
                "text4": "Close Tab: Ctrl+W",
                "text5": "Reload Tab: Ctrl+R",
                "text6": "Tab History Forward: Alt+Right Arrow",
                "text6": "Tab History Backward: Alt+Left Arrow",
                "text7": "Scroll Tab Index Forward: Ctrl+Right Arrow (or Scrollwheel Up over the tab bar)",
                "text7": "Scroll Tab Index Backward: Ctrl+Left Arrow (or Scrollwheel Down over the tab bar)",
                "text8": "Zoom In: Ctrl+=",
                "text9": "Zoom Out: Ctrl+-",
                "text10": "Mute/Unmute Tab: Ctrl+M"
            }
        }

        return DisplayUIText[SelectedUI]

        