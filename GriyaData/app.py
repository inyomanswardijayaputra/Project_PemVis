"""
app.py — Entry point GriyaData
Jalankan: python app.py
"""
import sys
import os
from PySide6.QtWidgets import QApplication
from ui.login_window import LoginWindow

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("GriyaData")
    
    # Load stylesheet global
    qss_path = os.path.join(os.path.dirname(__file__), "styles", "app.qss")
    if os.path.exists(qss_path):
        with open(qss_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
    
    window = LoginWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
    