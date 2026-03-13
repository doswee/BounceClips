import sys
from PyQt5.QtWidgets import QApplication, QComboBox, QWidget, QVBoxLayout, QLabel, QStyleFactory, QListView
from PyQt5.QtCore import Qt, QPoint

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
    margin-bottom: 8px;
    letter-spacing: 1px;
}

/* THE BUTTON */
QComboBox {
    background-color: #1e1e1e;
    border: 2px solid #333333;
    border-radius: 12px;
    padding-left: 15px;
    min-height: 45px;
    font-size: 14px;
}

QComboBox:hover {
    border: 2px solid #008080;
}

QComboBox::drop-down {
    border: none;
    width: 35px;
}

QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 5px solid #008080;
}

/* THE POPUP LIST */
QComboBox QListView {
    background-color: #1e1e1e;
    border: 2px solid #008080; 
    border-radius: 12px;
    outline: none;
    /* Split the difference: 2px top, 6px bottom */
    padding: 2px 0px 6px 0px; 
}

QComboBox QListView::viewport {
    background-color: transparent;
}

/* THE ITEMS */
QComboBox QListView::item {
    min-height: 40px; 
    border-radius: 8px;
    color: #bbbbbb;
    padding-left: 10px;
    margin: 2px 5px; 
}

QComboBox QListView::item:selected {
    background-color: #008080;
    color: #ffffff;
}
"""

class ModernComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.view_widget = QListView()
        self.view_widget.setFrameShape(QListView.NoFrame)
        
        # Disable scroll behavior
        self.view_widget.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view_widget.setAutoScroll(False)
        self.view_widget.setSpacing(5) 
        
        self.setView(self.view_widget)

    def showPopup(self):
        # Force all items to be rendered to avoid scrolling
        self.setMaxVisibleItems(self.count())
        
        container = self.view().parentWidget()
        if container:
            container.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
            container.setAttribute(Qt.WA_TranslucentBackground)
            container.setObjectName("TransparentDropContainer")
            container.setStyleSheet("#TransparentDropContainer { background: transparent; border: none; }")

        # MATH: SPLIT THE DIFFERENCE
        count = self.count()
        if count > 0:
            row_height = 52 
            # 16 is the "middle ground" buffer between the previous two versions
            total_h = (count * row_height) + 16
            
            self.view().setFixedHeight(total_h)
            self.view().viewport().setFixedHeight(total_h)
            container.setFixedHeight(total_h)
            container.setFixedWidth(self.width())
        
        super().showPopup()

        # SEAMLESS POSITIONING
        if container:
            # Align exactly with the top of the button
            global_pos = self.mapToGlobal(QPoint(0, 0))
            container.move(global_pos.x(), global_pos.y())
            self.view().scrollToTop()

class ModernApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BounceClips Clean UI")
        self.setFixedSize(400, 600)
        
        layout = QVBoxLayout()
        layout.setSpacing(30)
        layout.setAlignment(Qt.AlignCenter)

        layout.addWidget(QLabel("OUTPUT QUALITY"))
        self.combo1 = ModernComboBox()
        self.combo1.addItems(["Low (Standard Def)", "High (High Def)", "Ultra (4K Resolution)", "ProRes (Lossless)"])
        layout.addWidget(self.combo1)

        layout.addWidget(QLabel("FRAME RATE"))
        self.combo2 = ModernComboBox()
        self.combo2.addItems(["30 FPS", "60 FPS"])
        layout.addWidget(self.combo2)
        
        layout.addWidget(QLabel("ASPECT RATIO"))
        self.combo3 = ModernComboBox()
        self.combo3.addItems(["16:9 Wide", "4:3 Classic", "1:1 Square", "9:16 Vertical", "21:9 UltraWide"])
        layout.addWidget(self.combo3)

        self.setLayout(layout)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create("Fusion"))
    app.setStyleSheet(STYLE)
    
    window = ModernApp()
    window.show()
    sys.exit(app.exec_())