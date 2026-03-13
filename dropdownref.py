import sys
from PyQt5.QtWidgets import QApplication, QComboBox, QWidget, QVBoxLayout, QLabel, QStyleFactory, QListView
from PyQt5.QtCore import Qt

STYLE = """
/* The Main Window */
ModernApp {
    background-color: #121212;
}

QWidget {
    color: #FFFFFF;
    font-family: "SF Pro Display", "Helvetica Neue", Arial;
}

QLabel {
    color: #008080;
    font-size: 11px;
    font-weight: bold;
    margin-bottom: 5px;
    letter-spacing: 1px;
}

/* THE BUTTON */
QComboBox {
    background-color: #1e1e1e;
    border: 2px solid #333333;
    border-radius: 12px;
    padding-left: 15px;
    min-height: 36px;
}

QComboBox:hover {
    border: 2px solid #008080;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 30px;
    border-left: none;
    background: transparent;
}

QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 5px solid #008080;
    width: 0;
    height: 0;
}

/* THE POPUP LIST (The visible rounded part) */
QComboBox QListView {
    background-color: #1e1e1e; /* Our nice dark background */
    border: 2px solid #333333;
    border-radius: 12px;
    outline: none; /* Removes the dotted focus border */
}

/* Prevents the internal Qt canvas from drawing a solid square over our rounded corners */
QComboBox QListView::viewport {
    background-color: transparent;
}

/* THE ITEMS */
QComboBox QListView::item {
    min-height: 38px;
    padding-left: 10px;
    margin: 3px;         
    border-radius: 8px;  
    color: #bbbbbb;
}

QComboBox QListView::item:selected {
    background-color: #008080;
    color: #ffffff;
}
"""

class ModernApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BounceClips Clean UI")
        self.setFixedSize(400, 300)
        
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)

        label = QLabel("OUTPUT QUALITY")
        
        self.combo = QComboBox()
        
        view = QListView()
        view.setFrameShape(QListView.NoFrame)
        self.combo.setView(view)
        
        # ---------------------------------------------------------
        # THE ULTIMATE FIX
        # ---------------------------------------------------------
        container = self.combo.view().parentWidget()
        if container:
            # 1. Force the OS to drop the window frame and allow alpha transparency
            container.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
            container.setAttribute(Qt.WA_TranslucentBackground)
            
            # 2. Give the container an ID, and apply an inline stylesheet ONLY to that ID.
            # This makes the square box invisible without destroying the list's CSS!
            container.setObjectName("TransparentDropContainer")
            container.setStyleSheet("#TransparentDropContainer { background: transparent; border: none; }")
        
        self.combo.addItems([
            "Low (Standard Def)", 
            "High (High Def)", 
            "Ultra (4K Resolution)", 
            "ProRes (Lossless)"
        ])
        
        layout.addWidget(label)
        layout.addWidget(self.combo)
        self.setLayout(layout)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    app.setStyle(QStyleFactory.create("Fusion"))
    app.setStyleSheet(STYLE)
    
    window = ModernApp()
    window.show()
    sys.exit(app.exec_())