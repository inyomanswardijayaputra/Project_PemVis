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
        self.API_URL = "https://griyadata-backend-production.up.railway.app/api/login"
        self.initUI()
        self.showMaximized()
        
    def initUI(self):
        outer_widget = QWidget(self)
        outer_widget.setStyleSheet("background-color: #E8EAED;")
        self.setCentralWidget(outer_widget)
        
        outer_layout = QVBoxLayout(outer_widget)
        outer_layout.setAlignment(Qt.AlignCenter)
        outer_layout.setContentsMargins(30, 30, 30, 30)
        
        card = QWidget()
        card.setStyleSheet("""
            QWidget#card {
                background-color: white;
                border-radius: 16px;
            }
        """)
        card.setObjectName("card")
        card.setFixedWidth(480)
        
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 40)
        card_layout.setSpacing(0)
        
        header = QLabel("GRIYADATA", card)
        header.setAlignment(Qt.AlignCenter)
        
        header.setFixedHeight(90) 
        
        header.setStyleSheet("""
            QLabel {
                font-family: 'Arial';
                font-size: 30px;         
                font-weight: bold;      
                background-color: #3AA0D5;
                color: white;
                border-top-left-radius: 16px;
                border-top-right-radius: 16px;
                letter-spacing: 3px;
            }
        """)
        card_layout.addWidget(header)
        
        subtitle_label = QLabel("Aplikasi Manajemen Toko Miniatur")
        subtitle_label.setAlignment(Qt.AlignCenter)
        subtitle_label.setStyleSheet("""
            QLabel {
                font-family: 'Arial';
                font-size: 20px;         
                font-weight: bold;       
                color: #1A1A1A;
                padding-top: 18px;
                padding-bottom: 6px;
                background-color: white;
            }
        """)
        card_layout.addWidget(subtitle_label)
        
        # Form area
        form_widget = QWidget()
        form_widget.setStyleSheet("background-color: white;")
        form_layout = QVBoxLayout(form_widget)
        form_layout.setContentsMargins(36, 20, 36, 0)
        form_layout.setSpacing(6)
        
        # Username
        username_label = QLabel("Username:")
        username_label.setFont(QFont("Arial", 11))
        username_label.setStyleSheet("color: #34495E; background: transparent;")
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Masukkan username Anda")
        self.username_input.setStyleSheet(self.input_style())
        self.username_input.setFixedHeight(48)
        
        form_layout.addWidget(username_label)
        form_layout.addWidget(self.username_input)
        form_layout.addSpacing(12)
        
        # Password
        password_label = QLabel("Password:")
        password_label.setFont(QFont("Arial", 11))
        password_label.setStyleSheet("color: #34495E; background: transparent;")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Masukkan password Anda")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setStyleSheet(self.input_style())
        self.password_input.setFixedHeight(48)
        self.password_input.returnPressed.connect(self.handle_login)
        
        form_layout.addWidget(password_label)
        form_layout.addWidget(self.password_input)
        form_layout.addSpacing(24)
        
        self.login_button = QPushButton("Masuk Ke Sistem")
        self.login_button.setFont(QFont("Arial", 12, QFont.Bold))
        self.login_button.setCursor(Qt.PointingHandCursor)
        self.login_button.setFixedHeight(50)
        self.login_button.setStyleSheet("""
            QPushButton {
                background-color: #3AA0D5;
                color: white;
                border-radius: 10px;
                font-size: 13px;
                letter-spacing: 1px;
            }
            QPushButton:hover { background-color: #2E86C1; }
            QPushButton:pressed { background-color: #1A5276; }
            QPushButton:disabled { background-color: #AED6F1; }
        """)
        self.login_button.clicked.connect(self.handle_login)
        form_layout.addWidget(self.login_button)
        
        card_layout.addWidget(form_widget)
        outer_layout.addWidget(card, alignment=Qt.AlignCenter)
        
    def input_style(self):
        return """
            QLineEdit {
                border: 1.5px solid #D5D8DC;
                border-radius: 8px;
                padding: 10px 14px;
                font-size: 12px;
                background-color: #FDFEFE;
                color: #2C3E50;
            }
            QLineEdit:focus {
                border: 2px solid #3AA0D5;
                background-color: white;
            }
            QLineEdit::placeholder {
                color: #AEB6BF;
            }
        """
        
    def handle_login(self):
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        
        if not username or not password:
            QMessageBox.warning(self, "Peringatan", "Username dan Password wajib diisi!")
            return
            
        payload = {
            "username": username, 
            "password": password,
            "role": "Admin"
        }
        
        self.login_button.setText("Memverifikasi...")
        self.login_button.setEnabled(False)
        
        try:
            response = requests.post(self.API_URL, json=payload, timeout=10)
            
            if response.status_code == 200:
                self._open_dashboard(username)
            else:
                try:
                    error_detail = response.json().get("detail", "Login gagal.")
                    
                    if isinstance(error_detail, list):
                        error_detail = str(error_detail[0].get("msg", "Data tidak lengkap/salah format."))
                    elif not isinstance(error_detail, str):
                        error_detail = str(error_detail)
                        
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
    sys.exit(app.exec())