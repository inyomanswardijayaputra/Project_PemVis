"""
ui/dialog_import.py
Fitur Import Data dari file CSV atau Excel (.xlsx/.xls)

Logika:
1. User pilih file CSV/Excel
2. Python baca file pakai pandas
3. Mapping kolom file → kolom database (nama_pelanggan, product_id, jumlah, total_harga)
4. Preview data sebelum diinsert
5. Insert ke database via API /api/orders/bulk
"""

import os
import requests
import pandas as pd

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QPushButton, QLabel, QFrame, QMessageBox,
    QFileDialog, QTableWidget, QTableWidgetItem,
    QHeaderView, QComboBox, QProgressBar, QSizePolicy,
)
from PySide6.QtCore import Qt, QThread, Signal

from utils import Formatter
from api_handler import APIHandler, ProductRecord


# ─── Mapping kolom yang dikenali otomatis ─────────────────────────────────────
# Key = nama kolom di file user (lowercase, tanpa spasi)
# Value = field internal
AUTO_MAP = {
    # nama_pelanggan
    "customer_name":    "nama_pelanggan",
    "nama_pelanggan":   "nama_pelanggan",
    "nama_pembeli":     "nama_pelanggan",
    "pelanggan":        "nama_pelanggan",
    "customer":         "nama_pelanggan",
    # product_name (dipakai untuk lookup ke tabel produk)
    "product_name":     "product_name",
    "nama_barang":      "product_name",
    "produk":           "product_name",
    "nama_produk":      "product_name",
    # jumlah
    "quantity":         "jumlah",
    "jumlah":           "jumlah",
    "qty":              "jumlah",
    # total_harga
    "total":            "total_harga",
    "total_harga":      "total_harga",
    "total_sales":      "total_harga",
    "harga_total":      "total_harga",
    "subtotal":         "total_harga",
}

REQUIRED_FIELDS = ["nama_pelanggan", "product_name", "jumlah", "total_harga"]


# ─── Background insert thread ─────────────────────────────────────────────────

class InsertWorker(QThread):
    progress  = Signal(int)
    finished  = Signal(dict)
    error     = Signal(str)

    def __init__(self, api_base: str, orders: list[dict]):
        super().__init__()
        self.api_base = api_base.rstrip("/")
        self.orders   = orders

    def run(self):
        try:
            # Kirim dalam batch 500 biar tidak timeout
            BATCH = 500
            total_inserted = 0
            total_skipped  = 0
            all_errors     = []

            for i in range(0, len(self.orders), BATCH):
                batch = self.orders[i:i + BATCH]
                payload = {"orders": batch}
                r = requests.post(
                    f"{self.api_base}/api/orders/bulk",
                    json=payload,
                    timeout=30,
                )
                r.raise_for_status()
                result = r.json()
                total_inserted += result.get("inserted", 0)
                total_skipped  += result.get("skipped", 0)
                all_errors     += result.get("errors", [])

                pct = int((i + len(batch)) / len(self.orders) * 100)
                self.progress.emit(pct)

            self.finished.emit({
                "inserted": total_inserted,
                "skipped":  total_skipped,
                "errors":   all_errors,
            })
        except Exception as e:
            self.error.emit(str(e))


# ─── Dialog Utama ─────────────────────────────────────────────────────────────

class DialogImport(QDialog):
    def __init__(self, parent=None, api: APIHandler = None):
        super().__init__(parent)
        self.api = api
        self._df: pd.DataFrame | None = None
        self._products: list[ProductRecord] = []
        self._col_map: dict[str, str] = {}  # col_file → field_internal
        self._worker: InsertWorker | None = None

        self.setWindowTitle("Import Data dari File CSV / Excel")
        self.setMinimumSize(820, 600)
        self.setObjectName("dialogSales")
        self._build_ui()

        # Muat daftar produk di background
        if self.api:
            self._products = self.api.get_products()

    # ─── Build UI ─────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # Header
        hdr = QFrame()
        hdr.setObjectName("dialogHeader")
        h = QVBoxLayout(hdr)
        h.setContentsMargins(24, 16, 24, 14)
        h.setSpacing(3)
        QLabel("Import Data CSV / Excel", hdr).setObjectName("dialogTitle")
        h.addWidget(hdr.findChild(QLabel))
        sub = QLabel("Pilih file → periksa preview → klik Import untuk menyimpan ke database")
        sub.setObjectName("dialogSubtitle")
        h.addWidget(sub)
        root.addWidget(hdr)

        # Body
        body = QFrame()
        body.setObjectName("dialogBody")
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(20, 16, 20, 16)
        body_lay.setSpacing(14)

        # ── Step 1: Pilih File ──
        step1 = QFrame()
        step1.setObjectName("statCard")
        step1.setStyleSheet("#statCard{background:#f0f9ff;border:1.5px solid #bfdbfe;border-radius:8px;}")
        s1 = QHBoxLayout(step1)
        s1.setContentsMargins(16, 12, 16, 12)

        lbl_step = QLabel("📂  Pilih file CSV atau Excel (.xlsx / .xls)")
        lbl_step.setStyleSheet("font-weight:600;color:#1d4ed8;")
        s1.addWidget(lbl_step)
        s1.addStretch()

        self.lbl_file = QLabel("Belum ada file dipilih")
        self.lbl_file.setStyleSheet("color:#6b7280;font-size:11px;")
        s1.addWidget(self.lbl_file)

        btn_browse = QPushButton("Pilih File...")
        btn_browse.setObjectName("btnPrimary")
        btn_browse.setFixedWidth(110)
        btn_browse.clicked.connect(self._browse_file)
        s1.addWidget(btn_browse)
        body_lay.addWidget(step1)

        # ── Step 2: Mapping kolom (muncul setelah file dipilih) ──
        self.frame_map = QFrame()
        self.frame_map.setObjectName("statCard")
        self.frame_map.setStyleSheet("#statCard{background:#fffbeb;border:1.5px solid #fde68a;border-radius:8px;}")
        self.frame_map.setVisible(False)
        map_outer = QVBoxLayout(self.frame_map)
        map_outer.setContentsMargins(16, 12, 16, 12)
        map_outer.setSpacing(8)

        lbl_map = QLabel("🔗  Mapping Kolom  (cocokkan kolom file ke field database)")
        lbl_map.setStyleSheet("font-weight:600;color:#92400e;")
        map_outer.addWidget(lbl_map)

        self.form_map = QFormLayout()
        self.form_map.setSpacing(8)
        self.form_map.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        map_outer.addLayout(self.form_map)
        body_lay.addWidget(self.frame_map)

        # ── Step 3: Preview tabel ──
        lbl_preview = QLabel("Preview Data (maks. 20 baris pertama):")
        lbl_preview.setStyleSheet("font-weight:600;color:#374151;")
        body_lay.addWidget(lbl_preview)

        self.preview_table = QTableWidget()
        self.preview_table.setObjectName("dataTable")
        self.preview_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.preview_table.setAlternatingRowColors(True)
        self.preview_table.verticalHeader().setVisible(False)
        self.preview_table.setShowGrid(False)
        self.preview_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.preview_table.setMinimumHeight(200)
        body_lay.addWidget(self.preview_table)

        # Info jumlah baris
        self.lbl_info = QLabel("")
        self.lbl_info.setStyleSheet("color:#6b7280;font-size:11px;")
        body_lay.addWidget(self.lbl_info)

        # Progress bar (tersembunyi sampai insert)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setVisible(False)
        self.progress.setObjectName("inputField")
        body_lay.addWidget(self.progress)

        root.addWidget(body, 1)

        # Footer
        footer = QFrame()
        footer.setObjectName("dialogFooter")
        f = QHBoxLayout(footer)
        f.setContentsMargins(24, 12, 24, 12)
        f.addStretch()

        btn_batal = QPushButton("Batal")
        btn_batal.setObjectName("btnSecondary")
        btn_batal.clicked.connect(self.reject)
        f.addWidget(btn_batal)

        self.btn_import = QPushButton("⬆️  Import ke Database")
        self.btn_import.setObjectName("btnPrimary")
        self.btn_import.setEnabled(False)
        self.btn_import.clicked.connect(self._start_import)
        f.addWidget(self.btn_import)

        root.addWidget(footer)

    # ─── Step 1: Browse File ──────────────────────────────────────────────────

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Pilih File Data",
            os.path.expanduser("~"),
            "Data Files (*.csv *.xlsx *.xls);;CSV (*.csv);;Excel (*.xlsx *.xls)",
        )
        if not path:
            return
        self._load_file(path)

    def _load_file(self, path: str):
        try:
            ext = os.path.splitext(path)[1].lower()
            if ext == ".csv":
                df = pd.read_csv(path)
            elif ext in (".xlsx", ".xls"):
                df = pd.read_excel(path)
            else:
                QMessageBox.warning(self, "Format tidak didukung",
                                    "Hanya file .csv, .xlsx, dan .xls yang didukung.")
                return
        except Exception as e:
            QMessageBox.critical(self, "Gagal membaca file", str(e))
            return

        self._df = df
        self.lbl_file.setText(f"  {os.path.basename(path)}  ({len(df):,} baris, {len(df.columns)} kolom)")
        self._build_mapping(df)
        self._refresh_preview()
        self.btn_import.setEnabled(True)

    # ─── Step 2: Auto-mapping ─────────────────────────────────────────────────

    def _build_mapping(self, df: pd.DataFrame):
        # Hapus widget mapping lama
        while self.form_map.rowCount():
            self.form_map.removeRow(0)
        self._col_combos: dict[str, QComboBox] = {}

        cols_in_file = ["-- Tidak Dipakai --"] + list(df.columns)

        for field in REQUIRED_FIELDS:
            combo = QComboBox()
            combo.setObjectName("inputField")
            combo.addItems(cols_in_file)

            # Coba auto-detect kolom yang cocok
            for col in df.columns:
                normalized = col.lower().replace(" ", "_")
                if AUTO_MAP.get(normalized) == field:
                    idx = cols_in_file.index(col)
                    combo.setCurrentIndex(idx)
                    break

            label_map = {
                "nama_pelanggan": "Nama Pelanggan *",
                "product_name":   "Nama Produk *",
                "jumlah":         "Jumlah (qty) *",
                "total_harga":    "Total Harga *",
            }
            self.form_map.addRow(label_map[field], combo)
            self._col_combos[field] = combo

        self.frame_map.setVisible(True)

    # ─── Step 3: Preview ─────────────────────────────────────────────────────

    def _refresh_preview(self):
        if self._df is None:
            return
        df = self._df.head(20)
        self.preview_table.setRowCount(0)
        self.preview_table.setColumnCount(len(df.columns))
        self.preview_table.setHorizontalHeaderLabels(list(df.columns))

        for row_idx, row in df.iterrows():
            r = self.preview_table.rowCount()
            self.preview_table.insertRow(r)
            for c_idx, val in enumerate(row):
                item = QTableWidgetItem(str(val) if pd.notna(val) else "")
                item.setTextAlignment(Qt.AlignCenter)
                self.preview_table.setItem(r, c_idx, item)

        total = len(self._df)
        self.lbl_info.setText(
            f"  Total {total:,} baris akan diimport  •  Preview menampilkan 20 baris pertama"
        )

    # ─── Step 4: Import ───────────────────────────────────────────────────────

    def _start_import(self):
        if self._df is None:
            return

        # Ambil mapping dari combo
        mapping = {field: combo.currentText()
                   for field, combo in self._col_combos.items()}

        # Validasi semua field terpetakan
        not_mapped = [f for f, col in mapping.items() if col == "-- Tidak Dipakai --"]
        if not_mapped:
            QMessageBox.warning(
                self, "Mapping Belum Lengkap",
                "Field berikut belum dipetakan ke kolom:\n• " +
                "\n• ".join(not_mapped)
            )
            return

        # Buat product lookup: nama_barang (lowercase) → id
        product_map: dict[str, int] = {}
        if self._products:
            for p in self._products:
                product_map[p.nama_barang.lower().strip()] = p.id

        # Bangun list order
        orders  = []
        skipped = []
        df = self._df

        for idx, row in df.iterrows():
            try:
                nama_pelanggan = str(row[mapping["nama_pelanggan"]]).strip()
                product_name   = str(row[mapping["product_name"]]).strip()
                jumlah         = int(float(row[mapping["jumlah"]]))
                total_harga    = float(row[mapping["total_harga"]])

                if not nama_pelanggan or not product_name:
                    skipped.append(f"Baris {idx+2}: nama pelanggan/produk kosong")
                    continue

                # Lookup product_id
                pid = product_map.get(product_name.lower())
                if pid is None:
                    skipped.append(f"Baris {idx+2}: produk '{product_name}' tidak ditemukan")
                    continue

                orders.append({
                    "nama_pelanggan": nama_pelanggan,
                    "product_id":     pid,
                    "jumlah":         jumlah,
                    "total_harga":    total_harga,
                })
            except Exception as e:
                skipped.append(f"Baris {idx+2}: {str(e)}")

        if not orders:
            msg = "Tidak ada data yang valid untuk diimport."
            if skipped:
                msg += f"\n\nContoh masalah:\n" + "\n".join(skipped[:5])
            QMessageBox.warning(self, "Tidak Ada Data Valid", msg)
            return

        # Konfirmasi sebelum insert
        msg_konfirm = (
            f"Siap mengimport {len(orders):,} pesanan ke database.\n"
            f"{len(skipped):,} baris akan dilewati.\n\n"
            "Lanjutkan?"
        )
        if skipped:
            msg_konfirm += f"\n\nContoh baris yang dilewati:\n" + "\n".join(skipped[:3])
        ret = QMessageBox.question(self, "Konfirmasi Import",
                                   msg_konfirm,
                                   QMessageBox.Yes | QMessageBox.No)
        if ret != QMessageBox.Yes:
            return

        # Mulai insert di background thread
        self.btn_import.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setValue(0)

        api_base = self.api.base if self.api else "griyadataapi-4lkwxk47.b4a.run"
        self._worker = InsertWorker(api_base, orders)
        self._worker.progress.connect(self.progress.setValue)
        self._worker.finished.connect(self._on_insert_done)
        self._worker.error.connect(self._on_insert_error)
        self._worker.start()

    def _on_insert_done(self, result: dict):
        self.progress.setValue(100)
        self.btn_import.setEnabled(True)

        msg = (
            f"✅  Import selesai!\n\n"
            f"  Berhasil diinsert : {result['inserted']:,} pesanan\n"
            f"  Dilewati           : {result['skipped']:,} baris\n"
        )
        if result.get("errors"):
            msg += "\nContoh error:\n" + "\n".join(result["errors"][:5])

        QMessageBox.information(self, "Import Berhasil", msg)
        self.accept()

    def _on_insert_error(self, msg: str):
        self.progress.setVisible(False)
        self.btn_import.setEnabled(True)
        QMessageBox.critical(self, "Import Gagal",
                             f"Terjadi error saat menghubungi API:\n\n{msg}")
