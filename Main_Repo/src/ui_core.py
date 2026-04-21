import json
from pathlib import Path
from PySide6.QtGui import QIcon, QTransform
from PySide6.QtWidgets import *
from PySide6.QtCore import QRect, QSize, QTimer, QUrl, Qt
from PySide6.QtWidgets import QTabWidget
from PySide6.QtWidgets import QTabBar, QStylePainter, QStyleOptionTab, QStyle
from PySide6.QtCore import QSize
from functools import partial
from cookieManager import CookieManager




icon_cache_dir = Path(__file__).parent / "ui/icon_cache"
icon_cache_dir.mkdir(exist_ok=True)
def get_normIcon(name):
    icon_path = icon_cache_dir / f"{name}"

    return QIcon(str(icon_path))

class BarManager:

    def __init__(self, parent, eColsStyle, eColsButton, srcSourceDir):
        self.parent = parent
        self.eColsStyle = eColsStyle
        self.eColsButton = eColsButton
        self.srcSourceDir = srcSourceDir

        with open (self.srcSourceDir / "data/actionToggles.json", "r") as f:
            self.actionToggles = json.load(f)
        

    def setup_url_bar(self):
        self.url_bar = QLineEdit()
        self.url_bar.returnPressed.connect(self.parent.load_url)
        self.parent.nav_bar.addWidget(self.url_bar)
        self.eColsStyle.append("url_bar")
        return self.url_bar


    def setup_tabs(self):
        if self.actionToggles["tab_position"] in ["North", "South"]:
            self.tabs = QTabWidget()
            self.tabs.tabBar().setElideMode(Qt.TextElideMode.ElideRight)

        elif self.actionToggles["tab_position"] in ["East", "West"]:
            self.tabs = QTabWidget()
            self.tabs.setTabBar(VerticalTabBar())
        else:
            print("tab position loading error, defaulting to north")
            self.tabs = QTabWidget()
            self.tabs.tabBar().setElideMode(Qt.TextElideMode.ElideRight)

        self.eColsStyle.append("tabs")
        self.eColsStyle.append("tab_backer")
        self.tabs.setTabsClosable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.tabBar().setStyleSheet("QTabBar::tab { height: 30px; width: 200px; padding-left: 5px; padding-right: 5px; }")
        self.tabs.tabBar().setExpanding(True)
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

        #reload animation components
        self.rotation_angle = 0
        self.parent.rotation_timer = QTimer()
        self.parent.rotation_timer.timeout.connect(self.rotate_reload_icon)
        self.parent.current_browser.loadStarted.connect(self.start_reload_animation)
        self.parent.current_browser.loadFinished.connect(self.stop_reload_animation)


        return self.nav_bar
    
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
        self.colourPalette_btn = QToolButton(self.parent)
        self.colourPalette_btn.setToolTip("Colour Palettes")
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

        #add more themes button append
        Awidget = QWidget()
        Alayout = QHBoxLayout(Awidget)
        Alayout.setContentsMargins(5, 2, 5, 2)
        Alayout.setSpacing(5)

        Atext_label = QLabel("Add New Themes")
        Alayout.addWidget(Atext_label)

        Awidget_action = QWidgetAction(self.parent)
        Awidget_action.setDefaultWidget(Awidget)
        Awidget_action.setData("Add New Themes")
        Awidget_action.triggered.connect(self.parent.ColourThemeEditor)
        self.ColourMenu.addAction(Awidget_action)

        
        self.colourPalette_btn.setMenu(self.ColourMenu)
        self.colourPalette_btn.setIcon(get_normIcon("colourPalette"))

        # When the main button is clicked, read the current selectedprofile at click time
        self.colourPalette_btn.clicked.connect(lambda checked=False, d=Colourdata: self.parent.ToggleColourTheme(self.parent.selectedprofile, d))

        self.colourPalette_btn.setPopupMode(QToolButton.MenuButtonPopup)
        self.parent.nav_bar.addWidget(self.colourPalette_btn)
        self.eColsButton.append("colourPalette_btn")

        return self.colourPalette_btn, self.ColourMenu

    def setup_engine_button(self, engines):
        self.engine_btn = QToolButton(self.parent)
        self.engine_btn.setText("Search With...")
        self.browserMenu = QMenu(self.parent)

        for key, search_url in engines.items():
            # Create widget for menu item
            widget = QWidget()
            layout = QHBoxLayout(widget)
            layout.setContentsMargins(5, 2, 5, 2)
            layout.setSpacing(5)
            
            # Add icon
            icon_label = QLabel()
            icon = QIcon(str(icon_cache_dir / f"{key}"))
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
            widget_action.setData((key, search_url))
            widget_action.triggered.connect(lambda checked, k=key: self.parent.set_engine(k))
            self.browserMenu.addAction(widget_action)
            
        self.engine_btn.setMenu(self.browserMenu)
        self.engine_btn.setIcon(QIcon(str(icon_cache_dir / f"{self.parent.engine}")))

        self.engine_btn.clicked.connect(lambda: self.parent.current_browser.setUrl(QUrl(engines[self.parent.engine].split('/search?q=')[0])))

        self.engine_btn.setPopupMode(QToolButton.MenuButtonPopup)
        self.parent.nav_bar.addWidget(self.engine_btn)


        self.parent.set_engine(self.parent.engine)

        return self.engine_btn, self.browserMenu


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
            btn_accept.clicked.connect(lambda _, id=cookieID: self.parent.handle_cookie_action(id, "accept"))
            btn_deny.clicked.connect(lambda _, id=cookieID: self.parent.handle_cookie_action(id, "deny"))

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
    


class VerticalTabBar(QTabBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.hovered_index = -1
        self.update_close_buttons()

    def tabSizeHint(self, index):
        return QSize(200, 35) 
    
    def mouseMoveEvent(self, event):
        # Find which tab the mouse is currently over
        new_hover = self.tabAt(event.position().toPoint())
        if new_hover != self.hovered_index:
            self.hovered_index = new_hover
            self.update_close_buttons()
            self.update() # Trigger a repaint
        super().mouseMoveEvent(event)
    
    def leaveEvent(self, event):
        self.update_close_buttons()
        self.update()
        super().leaveEvent(event)

    def update_close_buttons(self):
        for i in range(self.count()):
            # Grab the actual widget QTabBar uses for the close button
            btn = self.tabButton(i, QTabBar.ButtonPosition.RightSide)
            if btn:
                is_hovered = (i == self.hovered_index)
                is_active = (i == self.currentIndex())
                btn.setVisible(is_hovered or is_active)

    def paintEvent(self, event):
        painter = QStylePainter(self)
        option = QStyleOptionTab()

        for i in range(self.count()):
            self.initStyleOption(option, i)
            option.shape = QTabBar.Shape.RoundedNorth
            painter.drawControl(QStyle.ControlElement.CE_TabBarTab, option)