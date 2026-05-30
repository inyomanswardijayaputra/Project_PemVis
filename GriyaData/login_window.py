import sys
import requests
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

class LoginWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GriyaData - Login System")
        self.setFixedSize(400, 500)
        self.API_URL = "https://griyadataapi-zv35m9ms.b4a.run/api/login"
        self.initUI()
        
    def initUI(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(40, 40, 40, 40)
        main_layout.setSpacing(15)
        
        title_label = QLabel("🎌  GriyaData", self)
        title_label.setFont(QFont("Arial", 24, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("color: #2C3E50;")
        
        subtitle_label = QLabel("Aplikasi Manajemen Toko Miniatur", self)
        subtitle_label.setFont(QFont("Arial", 10))
        subtitle_label.setAlignment(Qt.AlignCenter)
        subtitle_label.setStyleSheet("color: #7F8C8D;")
        
        main_layout.addWidget(title_label)
        main_layout.addWidget(subtitle_label)
        main_layout.addSpacing(20)
        
        username_label = QLabel("Username", self)
        username_label.setFont(QFont("Arial", 10, QFont.Bold))
        self.username_input = QLineEdit(self)
        self.username_input.setPlaceholderText("Masukkan username Anda")
        self.username_input.setStyleSheet(self.input_style())
        
        main_layout.addWidget(username_label)
        main_layout.addWidget(self.username_input)
        
        password_label = QLabel("Password", self)
        password_label.setFont(QFont("Arial", 10, QFont.Bold))
        self.password_input = QLineEdit(self)
        self.password_input.setPlaceholderText("Masukkan password Anda")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setStyleSheet(self.input_style())
        self.password_input.returnPressed.connect(self.handle_login)
        
        main_layout.addWidget(password_label)
        main_layout.addWidget(self.password_input)
        main_layout.addSpacing(10)
        
        self.login_button = QPushButton("Masuk Ke Sistem", self)
        self.login_button.setFont(QFont("Arial", 11, QFont.Bold))
        self.login_button.setCursor(Qt.PointingHandCursor)
        self.login_button.setStyleSheet("""
            QPushButton {
                background-color: #2980B9;
                color: white;
                border-radius: 6px;
                padding: 12px;
            }
            QPushButton:hover { background-color: #3498DB; }
            QPushButton:pressed { background-color: #1F618D; }
        """)
        self.login_button.clicked.connect(self.handle_login)
        main_layout.addWidget(self.login_button)
        main_layout.addStretch()
        
    def input_style(self):
        return """
            QLineEdit {
                border: 2px solid #BDC3C7;
                border-radius: 6px;
                padding: 10px;
                font-size: 11px;
                background-color: #FAFAFA;
            }
            QLineEdit:focus {
                border: 2px solid #2980B9;
                background-color: white;
            }
        """
        
    def handle_login(self):
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        
        if not username or not password:
            QMessageBox.warning(self, "Peringatan", "Username dan Password wajib diisi!")
            return
            
        payload = {"username": username, "password": password}
        self.login_button.setText("Memverifikasi...")
        self.login_button.setEnabled(False)
        
        try:
            response = requests.post(self.API_URL, json=payload, timeout=10)
            
            if response.status_code == 200:
                self._open_dashboard(username)
            else:
                # Parsing JSON dengan aman
                try:
                    error_detail = response.json().get("detail", "Login gagal.")
                except Exception:
                    error_detail = (
                        f"Server mengembalikan respons tidak valid "
                        f"(HTTP {response.status_code}).\n"
                        f"Kemungkinan API sedang down atau URL tidak ditemukan.\n\n"
                        f"URL: {self.API_URL}"
                    )
                QMessageBox.critical(self, "Login Gagal", error_detail)

        except requests.exceptions.ConnectionError:
            QMessageBox.critical(
                self, "Tidak Bisa Terhubung",
                "Gagal terhubung ke server API.\n\n"
                "Kemungkinan penyebab:\n"
                "• Tidak ada koneksi internet\n"
                "• Server API sedang offline\n\n"
                f"URL: {self.API_URL}"
            )
        except requests.exceptions.Timeout:
            QMessageBox.critical(
                self, "Timeout",
                "Server tidak merespons dalam 10 detik.\n"
                "Coba lagi beberapa saat."
            )
        except Exception as e:
            QMessageBox.critical(self, "Error Tidak Terduga", str(e))
        finally:
            self.login_button.setText("Masuk Ke Sistem")
            self.login_button.setEnabled(True)

    def _open_dashboard(self, username: str):
        from ui.main_window import MainWindow
        import os
        self._dashboard = MainWindow(username=username)
        qss_path = os.path.join(os.path.dirname(__file__), "styles", "app.qss")
        if os.path.exists(qss_path):
            with open(qss_path, "r", encoding="utf-8") as f:
                self._dashboard.setStyleSheet(f.read())
        self._dashboard.show()
        self.close()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LoginWindow()
    window.show()
    sys.exit(app.exec())
