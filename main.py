import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

# Import your custom modules
from ptsl_client import PTSLClient
from gui import RogueWavesGUI

def main():
    # 1. Enable High DPI scaling for sharp text and graphics
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    
    app = QApplication(sys.argv)
    app.setStyle("Fusion") # Use Fusion for a consistent dark look across OS
    
    # 2. Initialize the Pro Tools Client
    # Defaults to localhost:31416
    ptsl_client = PTSLClient()
    
    # 3. Initialize and show the GUI
    # We pass the client into the GUI so it can trigger commands
    window = RogueWavesGUI(ptsl_client)
    
    # Optional: Set window icon if you have one
    # window.setWindowIcon(QIcon("icon.ico"))
    
    window.show()
    
    # 4. Start the Application loop
    print("Rogue Waves Clip Bouncer is running...")
    sys.exit(app.exec())

if __name__ == "__main__":
    main()