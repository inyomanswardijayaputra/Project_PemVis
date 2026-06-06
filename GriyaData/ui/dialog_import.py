"""
ui/dialog_import.py — Import CSV/Excel ke GriyaData (schema baru)
Logic:
  1. Baca file
  2. Auto-detect mapping 20 kolom → field DB
  3. Tiap baris: cek produk di products, kalau baru → POST /api/products
  4. Bulk insert ke /api/orders/bulk dengan semua kolom lengkap
"""

import os
import requests
import pandas as pd
from datetime import datetime

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QFrame, QMessageBox,
    QFileDialog, QTableWidget, QTableWidgetItem,
    QHeaderView, QComboBox, QProgressBar, QSizePolicy,
    QScrollArea, QWidget, QCheckBox,
)
from PySide6.QtCore import Qt, QThread, Signal

from core.api_handler import APIHandler, ProductRecord


# ─── Auto-detect mapping ──────────────────────────────────────────────────────
# "nama_kolom_di_file_lowercase" → "field_internal"
AUTO_MAP = {
    "sales_date": "sales_date", "order_date": "sales_date",
    "tanggal": "sales_date", "date": "sales_date",
    "order_id": "order_id", "id_pesanan": "order_id",
    "customer_name": "customer_name", "nama_pelanggan": "customer_name",
    "nama_pembeli": "customer_name", "customer": "customer_name",
    "product_name": "product_name", "nama_barang": "product_name",
    "nama_produk": "product_name", "produk": "product_name", "item": "product_name",
    "category": "category", "kategori": "category",
    "price": "price", "harga": "price", "unit_price": "price",
    "quantity": "quantity", "jumlah": "quantity", "qty": "quantity",
    "discount": "discount", "diskon": "discount",
    "total": "total", "total_harga": "total", "subtotal": "total",
    "shipping_fee": "shipping_fee", "ongkir": "shipping_fee", "ongkos_kirim": "shipping_fee",
    "total_sales": "total_sales", "grand_total": "total_sales",
    "status": "status", "status_pesanan": "status", "order_status": "status",
    "shipping_address": "shipping_address", "alamat": "shipping_address",
    "customer_gender": "customer_gender", "gender": "customer_gender",
    "customer_city": "customer_city", "kota": "customer_city", "city": "customer_city",
    "payment_method": "payment_method", "metode_pembayaran": "payment_method",
    "courier": "courier", "kurir": "courier",
    "estimated_delivery_days": "estimated_delivery_days", "delivery_days": "estimated_delivery_days",
    "sales_channel": "sales_channel", "channel": "sales_channel", "platform": "sales_channel",
    "customer_rating": "customer_rating", "rating": "customer_rating",
}

# Wajib (4 kolom utama)
REQUIRED_FIELDS = [
    ("customer_name", "Nama Pelanggan *"),
    ("product_name",  "Nama Produk *"),
    ("quantity",      "Jumlah (qty) *"),
    ("total_sales",   "Total Sales *"),
]
# Opsional (sisanya)
OPTIONAL_FIELDS = [
    ("sales_date",             "Sales Date"),
    ("order_id",               "Order ID"),
    ("category",               "Category"),
    ("price",                  "Price"),
    ("discount",               "Discount"),
    ("total",                  "Total (sebelum ongkir)"),
    ("shipping_fee",           "Shipping Fee"),
    ("status",                 "Status"),
    ("shipping_address",       "Shipping Address"),
    ("customer_gender",        "Gender"),
    ("customer_city",          "Customer City"),
    ("payment_method",         "Payment Method"),
    ("courier",                "Courier"),
    ("estimated_delivery_days","Est. Delivery Days"),
    ("sales_channel",          "Sales Channel"),
    ("customer_rating",        "Customer Rating"),
]

STATUS_NORM = {
    "completed": "Selesai", "selesai": "Selesai",
    "processing": "Diproses", "diproses": "Diproses",
    "shipped": "Dikirim", "dikirim": "Dikirim",
    "pending": "Pending",
    "cancelled": "Dibatalkan", "canceled": "Dibatalkan", "dibatalkan": "Dibatalkan",
}


# ─── Background insert worker ─────────────────────────────────────────────────

class InsertWorker(QThread):
    progress = Signal(int)
    finished = Signal(dict)
    error    = Signal(str)

    def __init__(self, api_base, orders):
        super().__init__()
        self.api_base = api_base.rstrip("/")
        self.orders   = orders

    def run(self):
        try:
            BATCH = 500
            ins, skip, errs = 0, 0, []
            for i in range(0, len(self.orders), BATCH):
                batch = self.orders[i:i+BATCH]
                r = requests.post(f"{self.api_base}/api/orders/bulk",
                                  json={"orders": batch}, timeout=30)
                r.raise_for_status()
                res = r.json()
                ins  += res.get("inserted", 0)
                skip += res.get("skipped",  0)
                errs += res.get("errors",   [])
                self.progress.emit(int((i+len(batch))/len(self.orders)*100))
            self.finished.emit({"inserted": ins, "skipped": skip, "errors": errs})
        except Exception as e:
            self.error.emit(str(e))


# ─── Dialog ───────────────────────────────────────────────────────────────────

class DialogImport(QDialog):
    def __init__(self, parent=None, api: APIHandler = None):
        super().__init__(parent)
        self.api = api
        self._df  = None
        self._products: list[ProductRecord] = []
        self._col_combos: dict[str, QComboBox] = {}
        self._worker = None

        self.setWindowTitle("Import Data dari File CSV / Excel")
        self.setMinimumSize(1000, 680)
        self.resize(1060, 740)
        self.setObjectName("dialogSales")
        self._build_ui()
        if self.api:
            self._products = self.api.get_products()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(0); root.setContentsMargins(0, 0, 0, 0)

        hdr = QFrame(); hdr.setObjectName("dialogHeader")
        h = QVBoxLayout(hdr); h.setContentsMargins(24, 16, 24, 14); h.setSpacing(3)
        t = QLabel("Import Data CSV / Excel"); t.setObjectName("dialogTitle")
        h.addWidget(t)
        sub = QLabel("Pilih file → mapping kolom → produk dicek/dibuat otomatis → bulk insert ke database")
        sub.setObjectName("dialogSubtitle"); h.addWidget(sub)
        root.addWidget(hdr)

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        wrap = QWidget()
        body = QVBoxLayout(wrap); body.setContentsMargins(20,16,20,8); body.setSpacing(14)

        # Step 1
        s1 = QFrame()
        s1.setStyleSheet("QFrame{background:#f0f9ff;border:1.5px solid #bfdbfe;border-radius:8px;}")
        l1 = QHBoxLayout(s1); l1.setContentsMargins(16,12,16,12); l1.setSpacing(12)
        lbl_s = QLabel("📂  Pilih file CSV atau Excel (.xlsx / .xls)")
        lbl_s.setStyleSheet("font-weight:600;color:#1d4ed8;font-size:12px;")
        l1.addWidget(lbl_s, 1)
        self.lbl_file = QLabel("Belum ada file dipilih")
        self.lbl_file.setStyleSheet("color:#6b7280;font-size:11px;")
        self.lbl_file.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        l1.addWidget(self.lbl_file, 2)
        btn_br = QPushButton("Pilih File..."); btn_br.setObjectName("btnPrimary")
        btn_br.setFixedWidth(120); btn_br.clicked.connect(self._browse)
        l1.addWidget(btn_br)
        body.addWidget(s1)

        # Step 2: mapping
        self.frame_map = QFrame()
        self.frame_map.setStyleSheet(
            "QFrame{background:#fffbeb;border:1.5px solid #fde68a;border-radius:8px;}")
        self.frame_map.setVisible(False)
        mo = QVBoxLayout(self.frame_map); mo.setContentsMargins(16,12,16,14); mo.setSpacing(8)
        lbl_m = QLabel("🔗  Mapping Kolom  —  4 kolom WAJIB + 16 opsional (auto-detect)")
        lbl_m.setStyleSheet("font-weight:600;color:#92400e;font-size:12px;")
        mo.addWidget(lbl_m)
        hint = QLabel("ℹ️  Kolom opsional yang tidak dipakai → nilai default. "
                      "Kolom banyak? Scroll ke bawah untuk lihat semua.")
        hint.setStyleSheet("color:#78350f;font-size:10px;"); hint.setWordWrap(True)
        mo.addWidget(hint)
        # grid 2 pasang per baris
        self.grid_map = QGridLayout(); self.grid_map.setSpacing(6)
        self.grid_map.setColumnStretch(1, 1); self.grid_map.setColumnStretch(3, 1)
        mo.addLayout(self.grid_map)
        self.chk_auto = QCheckBox("Tambah produk baru otomatis ke tabel products jika belum ada")
        self.chk_auto.setChecked(True)
        self.chk_auto.setStyleSheet("color:#78350f;font-size:10px;font-weight:600;")
        mo.addWidget(self.chk_auto)
        body.addWidget(self.frame_map)

        # Step 3: preview
        lbl_pv = QLabel("Preview Data (20 baris pertama):")
        lbl_pv.setStyleSheet("font-weight:600;color:#374151;font-size:11px;")
        body.addWidget(lbl_pv)
        self.tbl_prev = QTableWidget()
        self.tbl_prev.setObjectName("dataTable")
        self.tbl_prev.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl_prev.setAlternatingRowColors(True)
        self.tbl_prev.verticalHeader().setVisible(False)
        self.tbl_prev.setShowGrid(False)
        self.tbl_prev.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.tbl_prev.setHorizontalScrollMode(QTableWidget.ScrollPerPixel)
        self.tbl_prev.setMinimumHeight(180)
        body.addWidget(self.tbl_prev, 1)
        self.lbl_info = QLabel("")
        self.lbl_info.setStyleSheet("color:#6b7280;font-size:10px;")
        body.addWidget(self.lbl_info)
        self.progress = QProgressBar(); self.progress.setRange(0,100)
        self.progress.setValue(0); self.progress.setVisible(False)
        body.addWidget(self.progress)

        scroll.setWidget(wrap); root.addWidget(scroll, 1)

        footer = QFrame(); footer.setObjectName("dialogFooter")
        f = QHBoxLayout(footer); f.setContentsMargins(24,12,24,12); f.addStretch()
        btn_batal = QPushButton("Batal"); btn_batal.setObjectName("btnSecondary")
        btn_batal.clicked.connect(self.reject); f.addWidget(btn_batal)
        self.btn_imp = QPushButton("⬆️  Import ke Database")
        self.btn_imp.setObjectName("btnPrimary"); self.btn_imp.setEnabled(False)
        self.btn_imp.clicked.connect(self._start_import); f.addWidget(self.btn_imp)
        root.addWidget(footer)

    # ── File ──────────────────────────────────────────────────────────────────
    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Pilih File", os.path.expanduser("~"),
            "Data Files (*.csv *.xlsx *.xls)")
        if path: self._load_file(path)

    def _load_file(self, path):
        try:
            ext = os.path.splitext(path)[1].lower()
            df = pd.read_csv(path) if ext == ".csv" else pd.read_excel(path)
        except Exception as e:
            QMessageBox.critical(self, "Gagal baca file", str(e)); return
        self._df = df
        self.lbl_file.setText(
            f"{os.path.basename(path)}  ({len(df):,} baris, {len(df.columns)} kolom)")
        self._build_mapping(df)
        self._refresh_preview()
        self.btn_imp.setEnabled(True)

    # ── Mapping ───────────────────────────────────────────────────────────────
    def _auto_detect(self, field, columns):
        for col in columns:
            if AUTO_MAP.get(col.lower().strip().replace(" ","_")) == field:
                return col
        return None

    def _build_mapping(self, df):
        while self.grid_map.count():
            w = self.grid_map.takeAt(0).widget()
            if w: w.deleteLater()
        self._col_combos.clear()

        none_opt = "-- Tidak Dipakai --"
        cols_in  = [none_opt] + list(df.columns)
        all_flds = REQUIRED_FIELDS + OPTIONAL_FIELDS

        for i, (field, label) in enumerate(all_flds):
            row_g = i // 2; col_off = (i % 2) * 2
            is_req = any(field == f for f,_ in REQUIRED_FIELDS)
            lbl = QLabel(label)
            lbl.setStyleSheet(
                f"font-size:10px;font-weight:{'700' if is_req else '500'};"
                f"color:{'#374151' if is_req else '#6b7280'};")
            lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            lbl.setMinimumWidth(145)

            combo = QComboBox(); combo.setObjectName("inputField")
            combo.addItems(cols_in)
            combo.setMinimumWidth(190)
            combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

            det = self._auto_detect(field, df.columns.tolist())
            if det:
                combo.setCurrentIndex(cols_in.index(det))
                combo.setStyleSheet(
                    "QComboBox{border:1.5px solid #10b981;border-radius:5px;}")
            else:
                combo.setStyleSheet(
                    "QComboBox{border:1px solid #d1d5db;border-radius:5px;}")

            self.grid_map.addWidget(lbl,   row_g, col_off,     Qt.AlignRight)
            self.grid_map.addWidget(combo, row_g, col_off + 1)
            self._col_combos[field] = combo

        self.frame_map.setVisible(True)

    # ── Preview ───────────────────────────────────────────────────────────────
    def _refresh_preview(self):
        if self._df is None: return
        df = self._df.head(20)
        self.tbl_prev.setRowCount(0)
        self.tbl_prev.setColumnCount(len(df.columns))
        self.tbl_prev.setHorizontalHeaderLabels(list(df.columns))
        for _, row in df.iterrows():
            r = self.tbl_prev.rowCount(); self.tbl_prev.insertRow(r)
            for ci, val in enumerate(row):
                item = QTableWidgetItem(str(val) if pd.notna(val) else "")
                item.setTextAlignment(Qt.AlignCenter)
                self.tbl_prev.setItem(r, ci, item)
        self.lbl_info.setText(
            f"  {len(self._df):,} baris  •  preview 20 baris  •  {len(self._df.columns)} kolom")

    # ── Import ────────────────────────────────────────────────────────────────
    def _start_import(self):
        if self._df is None: return
        mapping = {f: self._col_combos[f].currentText() for f in self._col_combos}

        # Cek field wajib
        missing = [lbl for f,lbl in REQUIRED_FIELDS
                   if mapping.get(f,"-- Tidak Dipakai --") == "-- Tidak Dipakai --"]
        if missing:
            QMessageBox.warning(self, "Field Wajib Belum Di-mapping",
                                "Mapping dulu field ini:\n• " + "\n• ".join(missing))
            return

        # Product map
        product_map = {p.product_name.lower().strip(): p.id for p in self._products}
        auto_create = self.chk_auto.isChecked()
        orders_ready, skipped, new_prod_count = [], [], 0

        def get_val(field, default=None):
            col = mapping.get(field, "-- Tidak Dipakai --")
            if col == "-- Tidak Dipakai --": return default
            v = row.get(col)
            return v if pd.notna(v) else default

        for idx, row in self._df.iterrows():
            rn = idx + 2
            try:
                cname   = str(get_val("customer_name") or "").strip()
                pname   = str(get_val("product_name")  or "").strip()
                qty_raw = get_val("quantity")
                ts_raw  = get_val("total_sales")

                if not cname or cname in ("nan","None",""):
                    skipped.append(f"Baris {rn}: customer_name kosong"); continue
                if not pname or pname in ("nan","None",""):
                    skipped.append(f"Baris {rn}: product_name kosong"); continue
                if qty_raw is None or ts_raw is None:
                    skipped.append(f"Baris {rn}: quantity/total_sales kosong"); continue

                qty   = int(float(qty_raw))
                tsale = float(str(ts_raw).replace(",","").replace(" ",""))

                # ── cek / buat produk ────────────────────────────────────────
                key = pname.lower()
                pid = product_map.get(key)
                if pid is None:
                    if not auto_create or not self.api:
                        skipped.append(f"Baris {rn}: produk '{pname}' tidak ada"); continue
                    price_raw = get_val("price")
                    harga = float(str(price_raw).replace(",","")) if price_raw is not None \
                            else (tsale / qty if qty > 0 else tsale)
                    cat_raw = get_val("category") or "Lainnya"
                    cat = str(cat_raw).strip() or "Lainnya"
                    try:
                        res = self.api.create_product({
                            "product_name": pname,
                            "category":     cat,
                            "price":        round(harga, 0),
                        })
                        pid = res.get("data", {}).get("id")
                        if not pid:
                            skipped.append(f"Baris {rn}: gagal buat produk '{pname}'"); continue
                        product_map[key] = pid; new_prod_count += 1
                    except Exception as e:
                        skipped.append(f"Baris {rn}: error produk '{pname}': {e}"); continue

                # ── kolom opsional ───────────────────────────────────────────
                def safe_float(f, d=0.0):
                    v = get_val(f)
                    try: return float(str(v).replace(",","")) if v is not None else d
                    except: return d

                def safe_int(f, d=0):
                    v = get_val(f)
                    try: return int(float(v)) if v is not None else d
                    except: return d

                def safe_str(f, d=""):
                    v = get_val(f)
                    s = str(v).strip() if v is not None else ""
                    return s if s not in ("nan","None","") else d

                # tanggal
                sd_raw = get_val("sales_date")
                sales_date_str = None
                if sd_raw is not None:
                    try: sales_date_str = pd.to_datetime(str(sd_raw)).isoformat()
                    except: pass

                # status normalisasi
                status_raw = safe_str("status", "Pending").lower()
                status = STATUS_NORM.get(status_raw, "Pending")

                disc  = safe_float("discount", 0)
                total = safe_float("total", tsale - safe_float("shipping_fee", 0))
                sfee  = safe_float("shipping_fee", 0)

                orders_ready.append({
                    "order_id":               safe_str("order_id"),
                    "customer_name":          cname,
                    "product_id":             pid,
                    "quantity":               qty,
                    "discount":               disc,
                    "total":                  total,
                    "shipping_fee":           sfee,
                    "total_sales":            tsale,
                    "status":                 status,
                    "shipping_address":       safe_str("shipping_address"),
                    "customer_gender":        safe_str("customer_gender"),
                    "customer_city":          safe_str("customer_city"),
                    "payment_method":         safe_str("payment_method", "Offline/COD"),
                    "courier":                safe_str("courier"),
                    "estimated_delivery_days":safe_int("estimated_delivery_days", 0),
                    "sales_channel":          safe_str("sales_channel"),
                    "customer_rating":        safe_float("customer_rating", 0),
                    "sales_date":             sales_date_str,
                })
            except Exception as e:
                skipped.append(f"Baris {rn}: {e}")

        if not orders_ready:
            msg = "Tidak ada data valid untuk diimport."
            if skipped: msg += "\n\nContoh masalah:\n" + "\n".join(skipped[:8])
            QMessageBox.warning(self, "Tidak Ada Data Valid", msg); return

        prod_info = f"\n✅ {new_prod_count} produk baru ditambahkan ke tabel products." \
                    if new_prod_count else ""
        konfirm = (f"Siap import {len(orders_ready):,} pesanan.\n"
                   f"{len(skipped):,} baris dilewati.{prod_info}\n\nLanjutkan?")
        if skipped[:3]:
            konfirm += "\n\nContoh dilewati:\n" + "\n".join(skipped[:3])

        if QMessageBox.question(self, "Konfirmasi Import", konfirm,
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return

        self.btn_imp.setEnabled(False)
        self.progress.setVisible(True); self.progress.setValue(0)
        self._worker = InsertWorker(self.api.base if self.api else "", orders_ready)
        self._worker.progress.connect(self.progress.setValue)
        self._worker.finished.connect(self._on_done)
        self._worker.error.connect(self._on_err)
        self._worker.start()

    def _on_done(self, res):
        self.progress.setValue(100); self.btn_imp.setEnabled(True)
        msg = (f"✅  Import selesai!\n\n"
               f"  Berhasil : {res['inserted']:,} pesanan\n"
               f"  Dilewati : {res['skipped']:,} baris\n")
        if res.get("errors"):
            msg += "\nContoh error:\n" + "\n".join(res["errors"][:5])
        QMessageBox.information(self, "Import Berhasil", msg); self.accept()

    def _on_err(self, msg):
        self.progress.setVisible(False); self.btn_imp.setEnabled(True)
        QMessageBox.critical(self, "Import Gagal", f"Error API:\n\n{msg}")
