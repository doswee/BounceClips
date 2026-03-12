import os
import sys
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QFrame, QComboBox, QMessageBox, 
    QLineEdit, QApplication, QFileDialog, QAbstractItemView,
    QCheckBox
)
from PySide6.QtCore import Qt, Signal, Slot, QObject, QRunnable, QThreadPool, QTimer
from PySide6.QtGui import QFont, QFontDatabase, QStandardItem, QColor

# --- BRANDING COLORS ---
COLOR_BG = "#0A0C0C"
COLOR_CARD = "#141818"
COLOR_ACCENT = "#58A39C" 
COLOR_TEXT = "#D0DCDC"
COLOR_TEXT_DIM = "#556666"
COLOR_DROPDOWN_BG = "#1A1F1F"

class WorkerSignals(QObject):
    finished = Signal(bool, str)

class BounceWorker(QRunnable):
    def __init__(self, ptsl, clips, settings):
        super().__init__()
        self.ptsl = ptsl
        self.clips = clips
        self.settings = settings
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            success = self.ptsl.perform_batch_bounce(self.clips, self.settings)
            self.signals.finished.emit(success, "" if success else "Bounce failed.")
        except Exception as e:
            self.signals.finished.emit(False, str(e))


class RogueWavesGUI(QMainWindow):
    def __init__(self, ptsl_client):
        super().__init__()
        self.ptsl = ptsl_client
        self.threadpool = QThreadPool()
        self.custom_folder_path = ""
        self.last_session_name = None
        
        self.setWindowTitle("ROGUE WAVES | CLIP BOUNCER")
        self.setMinimumSize(520, 850)
        
        self.load_fonts()
        self.init_ui()
        self.apply_styles()
        
        # Initial populate
        self.check_session_change()
        
        # Start background polling to detect session changes
        self.start_session_monitor()

    def load_fonts(self):
        font_dir = os.path.dirname(os.path.abspath(__file__))
        QFontDatabase.addApplicationFont(os.path.join(font_dir, "TitilliumWeb-Regular.ttf"))
        QFontDatabase.addApplicationFont(os.path.join(font_dir, "TitilliumWeb-SemiBold.ttf"))

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(35, 35, 35, 35)
        layout.setSpacing(15)

        # LOGO
        logo_container = QVBoxLayout()
        lbl_logo = QLabel("ROGUE WAVES")
        lbl_logo.setObjectName("Logo")
        lbl_logo.setAlignment(Qt.AlignCenter)
        lbl_sub = QLabel("PRECISION BATCH UTILITY")
        lbl_sub.setObjectName("SubLogo")
        lbl_sub.setAlignment(Qt.AlignCenter)
        logo_container.addWidget(lbl_logo); logo_container.addWidget(lbl_sub)
        layout.addLayout(logo_container)

        # NAMING CARD
        layout.addWidget(self.header_lbl("FILE NAMING"))
        naming_card = QFrame(); naming_card.setObjectName("Card")
        naming_grid = QGridLayout(naming_card)
        self.edit_prefix = QLineEdit(); self.edit_prefix.setPlaceholderText("Prefix...")
        self.edit_suffix = QLineEdit(); self.edit_suffix.setPlaceholderText("Suffix...")
        naming_grid.addWidget(QLabel("PREFIX:"), 0, 0); naming_grid.addWidget(self.edit_prefix, 0, 1)
        naming_grid.addWidget(QLabel("SUFFIX:"), 1, 0); naming_grid.addWidget(self.edit_suffix, 1, 1)
        layout.addWidget(naming_card)

        # LOCATION CARD
        layout.addWidget(self.header_lbl("OUTPUT LOCATION"))
        loc_card = QFrame(); loc_card.setObjectName("Card")
        loc_v = QVBoxLayout(loc_card)
        self.combo_loc = QComboBox()
        self.combo_loc.addItems(["Session 'Bounced Files' Folder", "Choose Custom Folder..."])
        self.combo_loc.currentIndexChanged.connect(self.on_location_changed)
        
        self.path_display = QLineEdit()
        self.path_display.setReadOnly(True)
        self.path_display.setPlaceholderText("Defaulting to Session Folder...")
        self.path_display.setObjectName("PathDisplay")
        
        self.btn_browse = QPushButton("BROWSE")
        self.btn_browse.setObjectName("MinorBtn")
        self.btn_browse.setVisible(False)
        self.btn_browse.clicked.connect(self.browse_folder)
        
        loc_v.addWidget(self.combo_loc)
        loc_v.addWidget(self.path_display)
        loc_v.addWidget(self.btn_browse)
        layout.addWidget(loc_card)

        # SOURCE CARD
        layout.addWidget(self.header_lbl("MIX SOURCE"))
        source_card = QFrame(); source_card.setObjectName("Card")
        source_v = QVBoxLayout(source_card)
        self.combo_source = QComboBox()
        self.combo_source.view().setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        source_v.addWidget(self.combo_source)
        layout.addWidget(source_card)

        # FORMAT CARD
        layout.addWidget(self.header_lbl("AUDIO FORMAT & OPTIONS"))
        format_card = QFrame(); format_card.setObjectName("Card")
        format_grid = QGridLayout(format_card)
        
        self.file_types = {"WAV": "EM_WAV", "AIFF": "EM_AIFF", "MP3": "EM_MP3"}
        self.combo_type = QComboBox()
        self.combo_type.addItems(list(self.file_types.keys()))
        
        self.combo_sr = QComboBox(); self.combo_sr.addItems(["44100", "48000", "88200", "96000"])
        self.combo_sr.setCurrentText("48000")
        
        self.combo_bit = QComboBox(); self.combo_bit.addItems(["16", "24", "32"])
        self.combo_bit.setCurrentText("24")

        self.chk_merge = QCheckBox("MERGE CONTIGUOUS CLIPS")

        format_grid.addWidget(QLabel("FILE TYPE:"), 0, 0); format_grid.addWidget(self.combo_type, 0, 1)
        format_grid.addWidget(QLabel("SAMPLE RATE:"), 1, 0); format_grid.addWidget(self.combo_sr, 1, 1)
        format_grid.addWidget(QLabel("BIT DEPTH:"), 2, 0); format_grid.addWidget(self.combo_bit, 2, 1)
        
        format_grid.addWidget(self.chk_merge, 3, 0, 1, 2)
        format_grid.setRowMinimumHeight(3, 35)

        layout.addWidget(format_card)

        layout.addStretch()
        self.btn_bounce = QPushButton("BOUNCE SELECTION")
        self.btn_bounce.setObjectName("MainBtn")
        self.btn_bounce.setFixedHeight(70)
        self.btn_bounce.clicked.connect(self.on_click_bounce)
        layout.addWidget(self.btn_bounce)

    def header_lbl(self, txt):
        l = QLabel(txt); l.setObjectName("Header"); return l

    def apply_styles(self):
        self.setStyleSheet(f"""
            QMainWindow {{ background-color: {COLOR_BG}; }}
            QWidget {{ font-family: 'Titillium Web'; color: {COLOR_TEXT}; }}
            
            #Logo {{ font-size: 38px; font-weight: 900; color: {COLOR_ACCENT}; letter-spacing: 1px; }}
            #SubLogo {{ font-size: 10px; color: {COLOR_TEXT_DIM}; letter-spacing: 5px; margin-top: -10px; font-weight: 600; }}
            #Header {{ font-size: 11px; font-weight: 800; color: {COLOR_ACCENT}; letter-spacing: 1.5px; margin-top: 5px; }}
            #Card {{ background-color: {COLOR_CARD}; border-radius: 4px; border: 1px solid #1A1F1F; padding: 12px; }}
            
            QLineEdit {{ background-color: #0A0D0D; border: 1px solid #2A2F2F; padding: 8px; border-radius: 3px; selection-background-color: {COLOR_ACCENT}; }}
            #PathDisplay {{ color: {COLOR_ACCENT}; font-size: 11px; font-style: italic; border: none; background: transparent; }}
            
            QComboBox {{ 
                background-color: #0A0D0D; border: 1px solid #2A2F2F; padding: 8px; border-radius: 3px; 
            }}
            QComboBox::drop-down {{ border: 0px; }}
            QComboBox::down-arrow {{ image: none; border-left: 5px solid transparent; border-right: 5px solid transparent; border-top: 5px solid {COLOR_ACCENT}; margin-right: 10px; }}
            
            /* DROPDOWN POPUP STYLE */
            QComboBox QAbstractItemView {{
                background-color: {COLOR_DROPDOWN_BG};
                border: 1px solid {COLOR_ACCENT};
                selection-background-color: {COLOR_ACCENT};
                selection-color: {COLOR_BG};
                outline: 0;
                padding: 5px;
            }}

            QCheckBox {{ font-size: 11px; font-weight: bold; color: {COLOR_TEXT}; spacing: 8px; }}
            QCheckBox::indicator {{ width: 14px; height: 14px; background-color: #0A0D0D; border: 1px solid #2A2F2F; border-radius: 3px; }}
            QCheckBox::indicator:checked {{ background-color: {COLOR_ACCENT}; border: 1px solid {COLOR_ACCENT}; }}

            QPushButton#MinorBtn {{ background-color: transparent; border: 1px solid {COLOR_ACCENT}; color: {COLOR_ACCENT}; font-size: 10px; font-weight: bold; padding: 6px; margin-top: 5px; }}
            QPushButton#MinorBtn:hover {{ background-color: #152524; }}
            
            QPushButton#MainBtn {{ background-color: {COLOR_ACCENT}; color: {COLOR_BG}; font-size: 20px; font-weight: 900; border-radius: 4px; }}
            QPushButton#MainBtn:hover {{ background-color: #6DBBB4; }}
            QPushButton#MainBtn:disabled {{ background-color: #1A1F1F; color: #444; }}
        """)

    def start_session_monitor(self):
        self.session_timer = QTimer(self)
        self.session_timer.timeout.connect(self.check_session_change)
        self.session_timer.start(3000) # Checks every 3 seconds

    def check_session_change(self):
        current_session = self.ptsl.get_session_name()
        if current_session != self.last_session_name:
            self.last_session_name = current_session
            if current_session:
                self.refresh_sources()
            else:
                self.combo_source.clear()
                self.combo_source.addItem("No active Pro Tools session...")

    def on_location_changed(self, index):
        is_custom = (index == 1)
        self.btn_browse.setVisible(is_custom)
        if not is_custom:
            self.path_display.setText("Defaulting to Session Folder...")
            self.custom_folder_path = ""
        else:
            self.path_display.setText(self.custom_folder_path if self.custom_folder_path else "No folder selected...")

    def browse_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if path:
            self.custom_folder_path = path
            self.path_display.setText(path)

    def refresh_sources(self):
        if not self.ptsl.session_id: self.ptsl.register("RogueWavesBouncer")
        self.combo_source.clear()
        sources = self.ptsl.get_available_sources()
        
        if not sources:
            self.combo_source.addItem("No sources available.")
            return

        # Categorize
        outputs =[s for s in sources if "Output" in s['type']]
        buses = [s for s in sources if "Bus" in s['type']]

        def add_section(title, items):
            if not items: return
            self.combo_source.addItem(f"--- {title} ---")
            idx = self.combo_source.count() - 1
            self.combo_source.model().item(idx).setEnabled(False)
            self.combo_source.model().item(idx).setForeground(QColor(COLOR_ACCENT))
            
            for s in items:
                self.combo_source.addItem(f"   {s['name']}", s)

        add_section("OUTPUTS", outputs)
        add_section("BUSES", buses)

    # No changes needed to the layout, just verify this logic in gui.py:
    def on_click_bounce(self):
        try:
            clips = self.ptsl.get_selected_clips_details()
            if not clips: 
                return QMessageBox.warning(self, "No Selection", "No clips found. Ensure clips and tracks are selected.")
                
            src = self.combo_source.currentData()
            if not src: 
                return QMessageBox.warning(self, "Mix Source", "Please select a valid Output or Bus.")

            # Validate settings
            settings = {
                "prefix": self.edit_prefix.text(),
                "suffix": self.edit_suffix.text(),
                "file_type": self.file_types[self.combo_type.currentText()],
                "sample_rate": self.combo_sr.currentText(),
                "bit_depth": self.combo_bit.currentText(),
                "source_name": src['name'],
                "source_type": src['type'],
                "custom_path": self.custom_folder_path
            }

            self.btn_bounce.setEnabled(False)
            self.btn_bounce.setText("BOUNCING...")
            
            worker = BounceWorker(self.ptsl, clips, settings)
            worker.signals.finished.connect(self.on_finished)
            self.threadpool.start(worker)
            
        except Exception as e:
            QMessageBox.critical(self, "Logic Error", f"App failed to start bounce: {e}")
            self.btn_bounce.setEnabled(True)

    def on_finished(self, success, err):
        self.btn_bounce.setEnabled(True)
        self.btn_bounce.setText("BOUNCE SELECTION")
        if success: QMessageBox.information(self, "Rogue Waves", "Batch Bounce Complete!")
        else: QMessageBox.critical(self, "Error", f"Failed: {err}")