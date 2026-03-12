import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QComboBox, QVBoxLayout, QWidget, QListView, QFrame
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtCore import Qt

class ObsidianUltimate(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Obsidian Dark - Total Fix")
        self.setMinimumSize(400, 300)
        
        # 1. THE ENGINE FIX: Force the global palette to be dark.
        # This prevents the OS from injecting white margins into popups.
        dark_palette = QPalette()
        dark_palette.setColor(QPalette.ColorRole.Window, QColor("#171717"))
        dark_palette.setColor(QPalette.ColorRole.Base, QColor("#171717"))
        dark_palette.setColor(QPalette.ColorRole.Button, QColor("#171717"))
        dark_palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
        dark_palette.setColor(QPalette.ColorRole.Highlight, QColor("#F59E0B"))
        dark_palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
        QApplication.setPalette(dark_palette)

        self.setStyleSheet("background-color: #121212;")

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # 2. Create the ComboBox
        self.combo = QComboBox()
        self.combo.addItems(["Primary Dashboard", "Security Settings", "Cloud Storage", "User Profile", "System Logout"])
        
        # 3. THE VIEW FIX: Manually create a ListView with NO frame
        view = QListView()
        view.setFrameShape(QFrame.Shape.NoFrame) # Kill the system border
        view.setSpacing(0)
        self.combo.setView(view)

        # 4. THE CSS FIX:
        self.combo.setStyleSheet("""
            /* MAIN BOX */
            QComboBox {
                background-color: #171717;
                border: 1px solid #404040;
                border-radius: 4px;
                padding: 10px 15px;
                color: #FFFFFF;
                font-size: 14px;
            }

            QComboBox:hover {
                border: 1px solid #F59E0B;
            }

            /* HIDE CHEVRON COMPLETELY */
            QComboBox::drop-down {
                width: 0px;
                border: 0px;
            }

            /* THE POPUP LIST */
            QAbstractItemView {
                background-color: #171717;
                border: 1px solid #404040; /* Single border around the whole popup */
                color: #FFFFFF;
                outline: none;
                padding: 0px;
                margin: 0px;
            }

            /* TARGET THE VIEWPORT (The actual scrolling area) */
            QAbstractItemView QWidget {
                background-color: #171717;
            }

            /* INDIVIDUAL ITEMS */
            QComboBox QAbstractItemView::item {
                min-height: 40px;
                padding-left: 15px;
                border: none;
                background-color: #171717;
            }

            QComboBox QAbstractItemView::item:selected {
                background-color: #F59E0B;
                color: black;
            }

            /* KILL THE SCROLLBAR TRACK WHITE SPACE */
            QScrollBar:vertical {
                width: 0px; /* Hiding scrollbar entirely for the cleanest look */
            }
        """)

        layout.addWidget(self.combo)
        layout.addStretch()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Fusion is essential for the palette to be respected
    app.setStyle("Fusion") 
    
    window = ObsidianUltimate()
    window.show()
    sys.exit(app.exec())