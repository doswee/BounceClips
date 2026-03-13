import os
import sys
import traceback
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QFrame, QComboBox, QMessageBox, 
    QLineEdit, QFileDialog, QCheckBox, QRadioButton, QButtonGroup,
    QListView, QApplication
)
from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtGui import QColor, QPalette

# --- BRANDING COLORS ---
COLOR_BG = "#1E1E1E"          
COLOR_CARD = "#252525"        
COLOR_ACCENT = "#58A39C"      
COLOR_ACCENT_HOVER = "#68B3AC" 
COLOR_TEXT = "#E0E0E0"        
COLOR_TEXT_DIM = "#888888"    

# =========================================================
# 1. THE MODERN DROPDOWN CLASS
# =========================================================
class ModernDropdown(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.view_widget = QListView()
        self.view_widget.setFrameShape(QListView.NoFrame)
        self.view_widget.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view_widget.setSpacing(2) 
        self.setView(self.view_widget)

    def showPopup(self):
        # Math from dropdownref_final.py
        self.setMaxVisibleItems(self.count() if self.count() > 0 else 1)
        container = self.view().parentWidget()
        if container:
            container.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
            container.setAttribute(Qt.WA_TranslucentBackground)
            container.setStyleSheet("background: transparent; border: none;")

        count = self.count()
        row_height = 48 
        total_h = (count * row_height) + 16 if count > 0 else 50
        
        self.view().setFixedHeight(total_h)
        if container:
            container.setFixedHeight(total_h)
            container.setFixedWidth(self.width())
            global_pos = self.mapToGlobal(QPoint(0, 0))
            container.move(global_pos.x(), global_pos.y())
        
        super().showPopup()

# =========================================================
# 2. MAIN GUI
# =========================================================
class RogueWavesGUI(QMainWindow):
    def __init__(self, ptsl_client):
        super().__init__()
        self.ptsl = ptsl_client
        self.custom_folder_path = ""
        self.session_bounced_folder = ""
        self.last_session_name = None
        self.first_run = True # Force initial population
        
        self.setWindowTitle("ROGUE WAVES CLIP BOUNCE")
        self.setMinimumSize(520, 920) 
        
        self.set_dark_palette()
        self.init_ui()
        self.apply_styles()
        
        # Start monitoring immediately
        print("--- APP STARTED ---")
        self.start_session_monitor()

    def set_dark_palette(self):
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(COLOR_BG))
        palette.setColor(QPalette.Base, QColor(COLOR_CARD))
        palette.setColor(QPalette.Text, QColor(COLOR_TEXT))
        QApplication.setPalette(palette)

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(10)

        # LOGO
        self.lbl_logo = QLabel('<p align="center"><span style="font-size:38px; font-weight:600; font-style:italic; color:#58A39C;">ROGUE WAVES</span></p>')
        layout.addWidget(self.lbl_logo)

        # SECTION: CLIPS
        layout.addWidget(self.header_lbl("CLIPS"))
        clips_card = QFrame(); clips_card.setObjectName("Card")
        cv = QVBoxLayout(clips_card)
        self.combo_naming_mode = ModernDropdown()
        self.combo_naming_mode.addItems(["Use Original Clip Names", "Custom Name + Numbering"])
        self.combo_naming_mode.currentIndexChanged.connect(self.on_naming_mode_changed)
        
        self.custom_name_widget = QWidget()
        cl = QHBoxLayout(self.custom_name_widget); cl.setContentsMargins(0,0,0,0)
        self.edit_base_name = QLineEdit(); self.edit_base_name.setPlaceholderText("Base Name...")
        self.combo_digits = ModernDropdown(); self.combo_digits.addItems(["1", "01", "001", "0001"])
        cl.addWidget(self.edit_base_name, 3); cl.addWidget(self.combo_digits, 1)
        self.custom_name_widget.setVisible(False)

        pre_suf = QHBoxLayout()
        self.edit_prefix = QLineEdit(); self.edit_prefix.setPlaceholderText("Prefix...")
        self.edit_suffix = QLineEdit(); self.edit_suffix.setPlaceholderText("Suffix...")
        pre_suf.addWidget(self.edit_prefix); pre_suf.addWidget(self.edit_suffix)
        
        self.chk_merge = QCheckBox("Merge contiguous clips"); self.chk_merge.setObjectName("Toggle"); self.chk_merge.setChecked(True)

        cv.addWidget(self.combo_naming_mode); cv.addWidget(self.custom_name_widget); cv.addLayout(pre_suf); cv.addWidget(self.chk_merge)
        layout.addWidget(clips_card)

        # SECTION: OUTPUT
        layout.addWidget(self.header_lbl("OUTPUT LOCATION"))
        loc_card = QFrame(); loc_card.setObjectName("Card")
        lv = QVBoxLayout(loc_card)
        self.rad_session = QRadioButton("Session 'Bounced Files'"); self.rad_session.setChecked(True); self.rad_session.setObjectName("Toggle")
        self.rad_custom = QRadioButton("Choose custom folder..."); self.rad_custom.setObjectName("Toggle")
        self.path_display = QLineEdit("Waiting for Pro Tools..."); self.path_display.setReadOnly(True); self.path_display.setObjectName("PathDisplay")
        lv.addWidget(self.rad_session); lv.addWidget(self.rad_custom); lv.addWidget(self.path_display)
        layout.addWidget(loc_card)

        # SECTION: MIX SOURCE
        layout.addWidget(self.header_lbl("MIX SOURCE"))
        source_card = QFrame(); source_card.setObjectName("Card")
        sv = QVBoxLayout(source_card)
        self.combo_source = ModernDropdown()
        self.combo_source.addItem("Searching...")
        sv.addWidget(self.combo_source)
        layout.addWidget(source_card)

        # SECTION: FORMAT
        layout.addWidget(self.header_lbl("AUDIO FORMAT"))
        format_card = QFrame(); format_card.setObjectName("Card")
        grid = QGridLayout(format_card)
        self.combo_type = ModernDropdown(); self.combo_type.addItems(["WAV", "AIFF", "MP3"])
        self.combo_sr = ModernDropdown(); self.combo_sr.addItems(["44100", "48000", "96000"]); self.combo_sr.setCurrentText("48000")
        self.combo_bit = ModernDropdown(); self.combo_bit.addItems(["16", "24", "32"]); self.combo_bit.setCurrentText("24")
        grid.addWidget(QLabel("File type:"), 0, 0); grid.addWidget(self.combo_type, 0, 1)
        grid.addWidget(QLabel("Sample rate:"), 1, 0); grid.addWidget(self.combo_sr, 1, 1)
        grid.addWidget(QLabel("Bit depth:"), 2, 0); grid.addWidget(self.combo_bit, 2, 1)
        layout.addWidget(format_card)

        layout.addStretch()
        self.btn_bounce = QPushButton("BOUNCE SELECTION")
        self.btn_bounce.setObjectName("MainBtn"); self.btn_bounce.setFixedHeight(80) 
        layout.addWidget(self.btn_bounce)

    def header_lbl(self, txt):
        l = QLabel(txt); l.setObjectName("SectionHeader"); return l

    def start_session_monitor(self):
        self.session_timer = QTimer(self)
        self.session_timer.timeout.connect(self.check_session_change)
        self.session_timer.start(2000)

    def check_session_change(self):
        try:
            # 1. Attempt to get session name
            name = self.ptsl.get_session_name()
            
            # 2. Check if we need to refresh (Session change OR first successful name grab)
            if name != self.last_session_name or (self.first_run and name):
                print(f"Update Detected. Session: {name}")
                self.last_session_name = name
                self.first_run = False
                
                if name:
                    self.session_bounced_folder = self.ptsl.get_bounced_files_path()
                    self.path_display.setText(self.session_bounced_folder)
                    self.refresh_sources()
                else:
                    self.path_display.setText("No Session Open")
                    self.combo_source.clear()
                    self.combo_source.addItem("No Session Found")
                    
        except Exception as e:
            print(f"Monitor Loop Error: {e}")

    def refresh_sources(self):
        print("Refreshing Mix Sources...")
        try:
            sources = self.ptsl.get_available_sources()
            print(f"PTSL returned: {sources}")
            
            self.combo_source.clear()
            if not sources:
                self.combo_source.addItem("No sources found")
                return

            for s in sources:
                label = f"[{s['type'].split('_')[-1]}] {s['name']}"
                self.combo_source.addItem(label, s)
            
            print(f"Successfully added {self.combo_source.count()} items to dropdown.")
        except Exception as e:
            print(f"Failed to populate sources: {e}")
            traceback.print_exc()

    def on_naming_mode_changed(self, index): self.custom_name_widget.setVisible(index == 1)
    def on_session_rad_clicked(self): self.path_display.setText(self.session_bounced_folder)
    def on_custom_rad_clicked(self):
        p = QFileDialog.getExistingDirectory(self, "Select Folder")
        if p: self.path_display.setText(p)

    def apply_styles(self):
        self.setStyleSheet(f"""
            QWidget {{ color: {COLOR_TEXT}; font-size: 13px; font-family: "Segoe UI", Arial; }}
            QMainWindow {{ background-color: {COLOR_BG}; }}
            QFrame#Card {{ background-color: {COLOR_CARD}; border-radius: 12px; padding: 12px; }}
            QLabel#SectionHeader {{ color: #CCC; font-weight: 600; font-size: 14px; margin-top: 5px; }}
            QLineEdit {{ background-color: #333; border: 1px solid #444; border-radius: 4px; padding: 6px; color: #ddd; }}
            QLineEdit#PathDisplay {{ color: {COLOR_ACCENT}; font-size: 11px; border: none; background: transparent; }}
            QPushButton#MainBtn {{ background-color: {COLOR_ACCENT}; color: white; border-radius: 12px; font-weight: 600; font-size: 32px; }}
            QComboBox {{
                background-color: #1e1e1e; border: 2px solid #333; border-radius: 10px; padding-left: 10px; min-height: 42px;
            }}
            QComboBox QListView {{
                background-color: #1e1e1e; border: 2px solid {COLOR_ACCENT}; border-radius: 10px; outline: none;
            }}
            QComboBox QListView::item {{ min-height: 40px; padding-left: 10px; color: #bbb; }}
            QComboBox QListView::item:selected {{ background-color: {COLOR_ACCENT}; color: white; }}
        """)