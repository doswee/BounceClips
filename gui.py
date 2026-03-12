import os
import sys
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QFrame, QComboBox, QMessageBox, 
    QLineEdit, QFileDialog, QCheckBox, QRadioButton, QButtonGroup,
    QAbstractItemView, QListView, QApplication, QStyledItemDelegate
)
from PySide6.QtCore import Qt, Signal, Slot, QObject, QRunnable, QThreadPool, QTimer
from PySide6.QtGui import QFontDatabase, QColor, QPalette, QFont

# --- BRANDING COLORS (FauxStereo Palette) ---
COLOR_BG = "#1E1E1E"          
COLOR_CARD = "#252525"        
COLOR_ACCENT = "#58A39C"      
COLOR_ACCENT_HOVER = "#68B3AC" 
COLOR_TEXT = "#E0E0E0"        
COLOR_TEXT_DIM = "#888888"    

class DropdownCombo(QComboBox):
    """Custom ComboBox that aligns its popup's top with the button's top."""
    def showPopup(self):
        super().showPopup()
        popup = self.view().window()
        if popup:
            # Shift the popup so its top edge matches the top edge of the button
            geo = popup.geometry()
            point = self.mapToGlobal(self.rect().topLeft())
            geo.moveTop(point.y())
            popup.setGeometry(geo)

class RogueWavesGUI(QMainWindow):
    def __init__(self, ptsl_client):
        super().__init__()
        self.ptsl = ptsl_client
        self.threadpool = QThreadPool()
        self.custom_folder_path = ""
        self.session_bounced_folder = ""
        self.last_session_name = None
        
        self.setWindowTitle("ROGUE WAVES CLIP BOUNCE")
        self.setMinimumSize(520, 920) 
        
        self.font_family = self.load_fonts()
        
        # --- TOTAL FIX: Force global dark palette to prevent white popup margins ---
        self.set_dark_palette()
        
        self.init_ui()
        self.apply_styles()
        
        self.check_session_change()
        self.start_session_monitor()

    def set_dark_palette(self):
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(COLOR_BG))
        palette.setColor(QPalette.WindowText, QColor(COLOR_TEXT))
        palette.setColor(QPalette.Base, QColor(COLOR_CARD))
        palette.setColor(QPalette.AlternateBase, QColor(COLOR_BG))
        palette.setColor(QPalette.ToolTipBase, QColor(COLOR_TEXT))
        palette.setColor(QPalette.ToolTipText, QColor(COLOR_TEXT))
        palette.setColor(QPalette.Text, QColor(COLOR_TEXT))
        palette.setColor(QPalette.Button, QColor(COLOR_CARD))
        palette.setColor(QPalette.ButtonText, QColor(COLOR_TEXT))
        palette.setColor(QPalette.BrightText, Qt.white)
        palette.setColor(QPalette.Highlight, QColor(COLOR_ACCENT))
        palette.setColor(QPalette.HighlightedText, Qt.black)
        QApplication.setPalette(palette)

    def load_fonts(self):
        font_dir = os.path.dirname(os.path.abspath(__file__))
        found_family = "Segoe UI"
        if sys.platform == "darwin": found_family = "SF Pro Text"
        res = QFontDatabase.addApplicationFont(os.path.join(font_dir, "TitilliumWeb-Regular.ttf"))
        if res != -1:
            found_family = QFontDatabase.applicationFontFamilies(res)[0]
        QFontDatabase.addApplicationFont(os.path.join(font_dir, "TitilliumWeb-SemiBold.ttf"))
        return found_family

    def _setup_combo(self, combo):
        """Standardizes the dropdown look: naked, rounded, and matched to themes."""
        view = QListView()
        view.setFrameShape(QFrame.NoFrame)
        view.setItemDelegate(QStyledItemDelegate())
        view.setAttribute(Qt.WA_MacShowFocusRect, False)
        view.setSpacing(0)
        
        view.setFont(QFont(self.font_family, 13))
        combo.setView(view)
        
        if combo.view() and combo.view().parentWidget():
            container = combo.view().parentWidget()
            container.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
            container.setAttribute(Qt.WA_TranslucentBackground)
            
            if container.layout():
                container.layout().setContentsMargins(0, 0, 0, 0)
                container.layout().setSpacing(0)

        view.setStyleSheet(f"""
            QListView {{
                background-color: {COLOR_CARD};
                border: 1px solid {COLOR_ACCENT};
                border-radius: 6px;
                outline: 0px;
                padding: 0px;
                margin: 0px;
                color: {COLOR_TEXT};
            }}
            QListView QWidget {{
                background-color: {COLOR_CARD};
            }}
            QListView::item {{
                padding: 8px 12px;
                border: none;
                background-color: transparent;
            }}
            QListView::item:selected {{
                background-color: {COLOR_ACCENT};
                color: white;
            }}
        """)
        return combo

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(10)

        # LOGO
        self.lbl_logo = QLabel()
        self.lbl_logo.setAlignment(Qt.AlignCenter)
        self.lbl_logo.setText(f"""
            <p align="center" style="margin-bottom:0px; margin-top:0px; line-height:0.8;">
                <span style="font-family:'{self.font_family}'; font-size:38px; font-weight:600; font-style:italic; color:{COLOR_ACCENT};">ROGUE WAVES</span><br/>
                <span style="font-family:'{self.font_family}'; font-size:16px; font-weight:600; font-style:italic; color:{COLOR_TEXT_DIM};">CLIP BOUNCE</span>
            </p>
        """)
        layout.addWidget(self.lbl_logo)
        layout.addSpacing(15)

        # SECTION: CLIPS
        layout.addWidget(self.header_lbl("CLIPS"))
        clips_card = QFrame(); clips_card.setObjectName("Card")
        clips_v = QVBoxLayout(clips_card)
        clips_v.setSpacing(12)
        
        self.combo_naming_mode = self._setup_combo(DropdownCombo())
        self.combo_naming_mode.addItems(["Use Original Clip Names", "Use Custom Name + Numbering"])
        self.combo_naming_mode.currentIndexChanged.connect(self.on_naming_mode_changed)
        
        self.custom_name_widget = QWidget()
        custom_layout = QHBoxLayout(self.custom_name_widget); custom_layout.setContentsMargins(0,0,0,0)
        self.edit_base_name = QLineEdit(); self.edit_base_name.setPlaceholderText("Base Name...")
        self.combo_digits = self._setup_combo(DropdownCombo())
        self.combo_digits.addItems(["1", "01", "001", "0001"]); self.combo_digits.setCurrentIndex(1)
        custom_layout.addWidget(self.edit_base_name, 3); custom_layout.addWidget(self.combo_digits, 1)
        self.custom_name_widget.setVisible(False)

        pre_suf_layout = QHBoxLayout()
        self.edit_prefix = QLineEdit(); self.edit_prefix.setPlaceholderText("Prefix...")
        self.edit_suffix = QLineEdit(); self.edit_suffix.setPlaceholderText("Suffix...")
        pre_suf_layout.addWidget(self.edit_prefix); pre_suf_layout.addWidget(self.edit_suffix)
        
        self.chk_merge = QCheckBox("Merge contiguous clips")
        self.chk_merge.setObjectName("Toggle")
        self.chk_merge.setChecked(True)

        clips_v.addWidget(self.combo_naming_mode)
        clips_v.addWidget(self.custom_name_widget)
        clips_v.addLayout(pre_suf_layout)
        clips_v.addWidget(self.chk_merge)
        layout.addWidget(clips_card)

        # SECTION: OUTPUT LOCATION
        layout.addWidget(self.header_lbl("OUTPUT LOCATION"))
        loc_card = QFrame(); loc_card.setObjectName("Card")
        loc_v = QVBoxLayout(loc_card)
        
        self.rad_session = QRadioButton("Session 'Bounced Files' folder"); self.rad_session.setChecked(True)
        self.rad_session.setObjectName("Toggle")
        self.rad_custom = QRadioButton("Choose custom folder..."); self.rad_custom.setObjectName("Toggle")
        
        self.loc_group = QButtonGroup(self); self.loc_group.addButton(self.rad_session); self.loc_group.addButton(self.rad_custom)
        self.rad_custom.clicked.connect(self.on_custom_rad_clicked)
        self.rad_session.clicked.connect(self.on_session_rad_clicked)
        
        self.path_display = QLineEdit(); self.path_display.setReadOnly(True); self.path_display.setObjectName("PathDisplay")
        
        loc_v.addWidget(self.rad_session)
        loc_v.addWidget(self.rad_custom)
        loc_v.addWidget(self.path_display)
        layout.addWidget(loc_card)

        # SECTION: MIX SOURCE
        layout.addWidget(self.header_lbl("MIX SOURCE"))
        source_card = QFrame(); source_card.setObjectName("Card")
        source_v = QVBoxLayout(source_card)
        self.combo_source = self._setup_combo(DropdownCombo())
        source_v.addWidget(self.combo_source)
        layout.addWidget(source_card)

        # SECTION: AUDIO FORMAT
        layout.addWidget(self.header_lbl("AUDIO FORMAT"))
        format_card = QFrame(); format_card.setObjectName("Card")
        grid = QGridLayout(format_card)
        grid.setVerticalSpacing(10)
        
        self.combo_type = self._setup_combo(DropdownCombo()); self.combo_type.addItems(["WAV", "AIFF", "MP3"])
        self.combo_sr = self._setup_combo(DropdownCombo()); self.combo_sr.addItems(["44100", "48000", "88200", "96000"]); self.combo_sr.setCurrentText("48000")
        self.combo_bit = self._setup_combo(DropdownCombo()); self.combo_bit.addItems(["16", "24", "32"]); self.combo_bit.setCurrentText("24")
        
        grid.addWidget(QLabel("File type:"), 0, 0); grid.addWidget(self.combo_type, 0, 1)
        grid.addWidget(QLabel("Sample rate:"), 1, 0); grid.addWidget(self.combo_sr, 1, 1)
        grid.addWidget(QLabel("Bit depth:"), 2, 0); grid.addWidget(self.combo_bit, 2, 1)
        layout.addWidget(format_card)

        layout.addStretch()
        
        self.btn_bounce = QPushButton("BOUNCE SELECTION")
        self.btn_bounce.setObjectName("MainBtn")
        self.btn_bounce.setCursor(Qt.PointingHandCursor)
        self.btn_bounce.setFixedHeight(80) 
        self.btn_bounce.clicked.connect(self.on_click_bounce)
        layout.addWidget(self.btn_bounce)

    def header_lbl(self, txt):
        l = QLabel(txt)
        l.setObjectName("SectionHeader")
        l.setContentsMargins(0, 4, 0, 0)
        return l

    # Logic Methods
    def start_session_monitor(self):
        self.session_timer = QTimer(self); self.session_timer.timeout.connect(self.check_session_change); self.session_timer.start(3000)

    def check_session_change(self):
        try:
            current_session = self.ptsl.get_session_name()
            if current_session != self.last_session_name:
                self.last_session_name = current_session
                if current_session:
                    self.session_bounced_folder = self.ptsl.get_bounced_files_path()
                    if self.rad_session.isChecked(): self.update_path_display(self.session_bounced_folder)
                    self.refresh_sources()
                else:
                    self.session_bounced_folder = ""; self.path_display.setText("No session found"); self.combo_source.clear()
        except: pass

    def refresh_sources(self):
        self.combo_source.clear()
        sources = self.ptsl.get_available_sources()
        if not sources: return
        def add_section(title, items):
            if not items: return
            self.combo_source.addItem(f"--- {title} ---")
            idx = self.combo_source.count()-1
            self.combo_source.model().item(idx).setEnabled(False)
            self.combo_source.model().item(idx).setForeground(QColor(COLOR_ACCENT))
            for s in items: self.combo_source.addItem(f"   {s['name']}", s)
        add_section("OUTPUTS", [s for s in sources if "Output" in s['type']])
        add_section("BUSES", [s for s in sources if "Bus" in s['type']])

    def on_naming_mode_changed(self, index): self.custom_name_widget.setVisible(index == 1)
    def on_session_rad_clicked(self): self.update_path_display(self.session_bounced_folder)
    def on_custom_rad_clicked(self):
        path = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if path: self.custom_folder_path = path; self.update_path_display(path)
        else: self.rad_session.setChecked(True); self.on_session_rad_clicked()

    def update_path_display(self, path):
        self.path_display.setText(path); self.path_display.setToolTip(path)

    def on_click_bounce(self): pass

    def apply_styles(self):
        self.setStyleSheet(f"""
            QWidget {{ font-family: '{self.font_family}'; font-weight: 400; color: {COLOR_TEXT}; font-size: 13px; }}
            QMainWindow {{ background-color: {COLOR_BG}; }}
            
            QFrame#Card {{ background-color: {COLOR_CARD}; border-radius: 6px; border: none; padding: 12px; }}
            
            QLabel#SectionHeader {{ color: #CCC; font-weight: 600; font-style: italic; font-size: 18px; letter-spacing: 1px; }}

            QLineEdit {{ background-color: #333; border: 1px solid #444; border-radius: 4px; padding: 6px; color: #ddd; }}
            QLineEdit#PathDisplay {{ color: {COLOR_ACCENT}; font-size: 11px; border: none; background: transparent; font-style: italic; }}
            
            QPushButton {{ background-color: #333; border: 1px solid #444; border-radius: 4px; padding: 6px; color: #ddd; }}
            QPushButton:hover {{ background-color: #3E3E3E; border-color: #555; }}
            
            QPushButton#MainBtn {{ background-color: {COLOR_ACCENT}; color: white; border: none; font-weight: 600; font-style: italic; font-size: 32px; }}
            QPushButton#MainBtn:hover {{ background-color: {COLOR_ACCENT_HOVER}; }}

            QComboBox {{ background-color: #333; border: 1px solid #444; border-radius: 4px; padding: 6px 10px; color: #ddd; }}
            QComboBox::drop-down {{ width: 0px; border: 0px; }}
            
            /* Global popup styling */
            QComboBox QAbstractItemView {{
                background-color: {COLOR_CARD};
                border: 1px solid {COLOR_ACCENT};
                selection-background-color: {COLOR_ACCENT};
                outline: 0px;
            }}
            /* The viewport fix for macOS */
            QComboBox QAbstractItemView QWidget {{
                background-color: {COLOR_CARD};
            }}

            QCheckBox#Toggle, QRadioButton#Toggle {{ font-size: 13px; color: #ddd; spacing: 8px; font-weight: 500; }}
            QCheckBox#Toggle::indicator, QRadioButton#Toggle::indicator {{ 
                width: 18px; height: 18px; background: #333; border: 1px solid #555; border-radius: 4px; 
            }}
            QRadioButton#Toggle::indicator {{ border-radius: 10px; }} 
            QCheckBox#Toggle::indicator:checked, QRadioButton#Toggle::indicator:checked {{ 
                background: {COLOR_ACCENT}; border-color: {COLOR_ACCENT}; 
            }}
        """)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion") 
    class Mock:
        def get_session_name(self): return "Session"
        def get_bounced_files_path(self): return "/Path"
        def get_available_sources(self): return []
    window = RogueWavesGUI(Mock())
    window.show()
    sys.exit(app.exec())