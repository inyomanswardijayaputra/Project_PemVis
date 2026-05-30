"""
ui/main_window.py
Dashboard utama GriyaData — Penjualan Produk Miniatur
Terinspirasi dari Week12 Online Sales Dashboard, diadaptasi untuk
berkomunikasi dengan REST API FastAPI (Supabase backend).
"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QLabel, QFrame, QComboBox, QDialog,
    QMessageBox, QSizePolicy, QStatusBar,
)
from PySide6.QtCore import Qt, Slot, QThread, Signal
from PySide6.QtGui import QAction, QColor

from api_handler import APIHandler, OrderRecord
from utils import Formatter, STATUS_PESANAN, METODE_PEMBAYARAN, STATUS_COLORS
from ui.chart_widget import ChartWidget
from ui.dialog_order import DialogOrder
from ui.dialog_import import DialogImport

NAMA        = "GriyaData"
APP_TITLE   = "GriyaData — Manajemen Penjualan Miniatur"


# ─── Background loader thread ─────────────────────────────────────────────────

class DataLoader(QThread):
    """Memuat data dari API di background agar UI tidak freeze."""
    finished = Signal(list)
    error    = Signal(str)

    def __init__(self, api: APIHandler, status: str, metode: str):
        super().__init__()
        self.api    = api
        self.status = status
        self.metode = metode

    def run(self):
        try:
            orders = self.api.get_all_orders(self.status, self.metode)
            self.finished.emit(orders)
        except Exception as e:
            self.error.emit(str(e))


# ─── Main Window ──────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self, username: str = "Admin"):
        super().__init__()
        self.username = username
        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(1200, 720)
        self.resize(1400, 820)

        self.api = APIHandler()
        self._orders: list[OrderRecord] = []
        self._loader: DataLoader | None = None

        self._build_menu()
        self._build_ui()
        self._build_statusbar()
        self.refresh_all()

    # ─── Menu ─────────────────────────────────────────────────────────────────

    def _build_menu(self):
        mb = self.menuBar()
        mb.setObjectName("menuBar")

        mf = mb.addMenu("&File")
        a_refresh = QAction("🔄  Refresh Data", self)
        a_refresh.setShortcut("F5")
        a_refresh.triggered.connect(self.refresh_all)
        mf.addAction(a_refresh)
        mf.addSeparator()
        a_logout = QAction("Logout", self)
        a_logout.setShortcut("Ctrl+L")
        a_logout.triggered.connect(self._logout)
        mf.addAction(a_logout)
        a_quit = QAction("Keluar", self)
        a_quit.setShortcut("Ctrl+Q")
        a_quit.triggered.connect(self.close)
        mf.addAction(a_quit)

        md = mb.addMenu("&Pesanan")
        a_add = QAction("Tambah Pesanan", self)
        a_add.setShortcut("Ctrl+N")
        a_add.triggered.connect(self._tambah)
        md.addAction(a_add)

        a_edit = QAction("Edit Status Pesanan", self)
        a_edit.setShortcut("Ctrl+E")
        a_edit.triggered.connect(self._edit)
        md.addAction(a_edit)

        a_del = QAction("Hapus Pesanan", self)
        a_del.setShortcut("Delete")
        a_del.triggered.connect(self._hapus)
        md.addAction(a_del)
        md.addSeparator()
        a_import = QAction("📥  Import dari CSV / Excel", self)
        a_import.setShortcut("Ctrl+I")
        a_import.triggered.connect(self._import_file)
        md.addAction(a_import)

    # ─── Layout ───────────────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        central.setObjectName("mainContainer")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._make_banner())

        self.tabs = QTabWidget()
        self.tabs.setObjectName("mainTabs")
        root.addWidget(self.tabs, 1)

        self._build_tab_dashboard()
        self._build_tab_table()

    def _make_banner(self) -> QFrame:
        banner = QFrame()
        banner.setObjectName("banner")
        lay = QHBoxLayout(banner)
        lay.setContentsMargins(20, 12, 20, 12)

        lbl_app = QLabel("🎌  GriyaData — Penjualan Miniatur")
        lbl_app.setObjectName("bannerApp")
        lbl_app.setStyleSheet("font-size:19px;font-weight:700;color:#1a1a1a;")
        lay.addWidget(lbl_app)
        lay.addStretch()

        frame_id = QFrame()
        frame_id.setObjectName("frameIdentitas")
        id_lay = QHBoxLayout(frame_id)
        id_lay.setContentsMargins(14, 6, 14, 6)
        id_lay.setSpacing(16)

        lbl_user = QLabel(f"👤  {self.username}")
        lbl_user.setObjectName("bannerIdentitas")
        lbl_api = QLabel("🔗 API: griyadataapi")
        lbl_api.setObjectName("bannerNIM")

        id_lay.addWidget(lbl_user)
        id_lay.addWidget(lbl_api)
        lay.addWidget(frame_id)
        return banner

    # ─── Tab Dashboard ────────────────────────────────────────────────────────

    def _build_tab_dashboard(self):
        tab = QWidget()
        tab.setObjectName("tabDashboard")
        root = QVBoxLayout(tab)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(16)

        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(12)

        self._card_tx    = self._make_stat_card("Total Pesanan",    "—", "#3b82f6")
        self._card_rev   = self._make_stat_card("Total Revenue",    "—", "#10b981")
        self._card_avg   = self._make_stat_card("Rata-rata / Order","—", "#f59e0b")
        self._card_units = self._make_stat_card("Total Unit Terjual","—", "#8b5cf6")

        for c in (self._card_tx, self._card_rev, self._card_avg, self._card_units):
            cards_layout.addWidget(c)

        root.addLayout(cards_layout)

        self._dash_chart = ChartWidget()
        self._dash_chart.combo_chart.setCurrentIndex(2)  # Trend per Bulan default
        root.addWidget(self._dash_chart, 1)

        self.tabs.addTab(tab, "📊  Dashboard")

    def _make_stat_card(self, title: str, value: str, color: str) -> QFrame:
        card = QFrame()
        card.setObjectName("statCard")
        card.setStyleSheet("""
            #statCard {
                background: #ffffff;
                border: 1.5px solid #e5e7eb;
                border-radius: 10px;
            }
            #statCard:hover { border-color: #bfdbfe; }
        """)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(4)

        lbl_val = QLabel(value)
        lbl_val.setStyleSheet(f"font-size:24px;font-weight:700;color:{color};")
        lbl_val.setObjectName("cardVal")

        lbl_tit = QLabel(title)
        lbl_tit.setStyleSheet("font-size:11px;color:#6b7280;font-weight:600;letter-spacing:0.3px;")

        lay.addWidget(lbl_val)
        lay.addWidget(lbl_tit)
        return card

    def _update_stat_card(self, card: QFrame, value: str):
        lbl = card.findChild(QLabel, "cardVal")
        if lbl:
            lbl.setText(value)

    # ─── Tab Tabel Pesanan ────────────────────────────────────────────────────

    def _build_tab_table(self):
        tab = QWidget()
        tab.setObjectName("tabTable")
        root = QVBoxLayout(tab)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(8)

        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(8)

        for label, attr, items in [
            ("Status:",  "f_status", ["All"] + STATUS_PESANAN),
            ("Metode:",  "f_metode", ["All"] + METODE_PEMBAYARAN),
        ]:
            lbl = QLabel(label)
            lbl.setObjectName("panelSubinfo")
            lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
            combo = QComboBox()
            combo.setObjectName("inputField")
            combo.setMinimumWidth(110)
            combo.setMaximumWidth(160)
            combo.addItems(items)
            combo.currentTextChanged.connect(self._on_filter_changed)
            setattr(self, attr, combo)
            filter_bar.addWidget(lbl)
            filter_bar.addWidget(combo)
            filter_bar.addSpacing(12)

        btn_refresh = QPushButton("🔄")
        btn_refresh.setObjectName("btnRefresh")
        btn_refresh.setFixedWidth(36)
        btn_refresh.clicked.connect(self.refresh_all)
        filter_bar.addWidget(btn_refresh)

        filter_bar.addStretch()

        btn_add = QPushButton("➕  Tambah")
        btn_add.setObjectName("btnPrimary")
        btn_add.clicked.connect(self._tambah)
        filter_bar.addWidget(btn_add)

        self.btn_edit = QPushButton("✏️  Edit Status")
        self.btn_edit.setObjectName("btnSecondary")
        self.btn_edit.setEnabled(False)
        self.btn_edit.clicked.connect(self._edit)
        filter_bar.addWidget(self.btn_edit)

        self.btn_del = QPushButton("🗑️  Hapus")
        self.btn_del.setObjectName("btnDanger")
        self.btn_del.setEnabled(False)
        self.btn_del.clicked.connect(self._hapus)
        filter_bar.addWidget(self.btn_del)

        btn_import = QPushButton("📥  Import File")
        btn_import.setObjectName("btnSecondary")
        btn_import.clicked.connect(self._import_file)
        btn_import.setToolTip("Import data pesanan dari file CSV atau Excel (Ctrl+I)")
        filter_bar.addWidget(btn_import)

        root.addLayout(filter_bar)

        self.table = QTableWidget()
        self.table.setObjectName("dataTable")
        cols = ["ID", "Pelanggan", "Produk", "Kategori",
                "Jumlah", "Total Harga", "Tgl Pesan", "Status", "Metode Bayar"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 44)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.doubleClicked.connect(self._edit)
        root.addWidget(self.table)

        self.tabs.addTab(tab, "📋  Data Pesanan")

    def _build_statusbar(self):
        sb = self.statusBar()
        sb.setObjectName("statusBar")
        sb.setSizeGripEnabled(False)
        sb.setStyleSheet("QStatusBar::item { border: none; }")
        self.lbl_status = QLabel("  Memuat data...")
        sb.addWidget(self.lbl_status)

    # ─── Data Loading ─────────────────────────────────────────────────────────

    def refresh_all(self):
        self.lbl_status.setText("  🔄  Mengambil data dari API...")
        status = self.f_status.currentText() if hasattr(self, "f_status") else "All"
        metode = self.f_metode.currentText() if hasattr(self, "f_metode") else "All"

        self._loader = DataLoader(self.api, status, metode)
        self._loader.finished.connect(self._on_data_loaded)
        self._loader.error.connect(self._on_data_error)
        self._loader.start()

    @Slot(list)
    def _on_data_loaded(self, orders: list[OrderRecord]):
        self._orders = orders
        self._load_table(orders)
        self._load_stats(orders)
        self._load_charts(orders)
        self.lbl_status.setText(f"  ✅  Total: {len(orders)} Pesanan  |  Terakhir diperbarui dari API")

    @Slot(str)
    def _on_data_error(self, msg: str):
        self.lbl_status.setText(f"  ❌  Gagal memuat data: {msg}")
        QMessageBox.warning(self, "Koneksi API Gagal",
                            f"Tidak dapat mengambil data dari server.\n\nDetail: {msg}")

    def _load_table(self, orders: list[OrderRecord]):
        self.table.setRowCount(0)
        STATUS_ROW_COLORS = {
            "Selesai":     "#dcfce7",
            "Diproses":    "#dbeafe",
            "Dikirim":     "#e0e7ff",
            "Pending":     "#fef9c3",
            "Dibatalkan":  "#fee2e2",
        }
        for o in orders:
            r = self.table.rowCount()
            self.table.insertRow(r)
            vals = [
                str(o.id),
                o.nama_pelanggan,
                o.nama_barang,
                o.kategori,
                str(o.jumlah),
                Formatter.currency(o.total_harga),
                o.tanggal_pesanan,
                o.status_pesanan,
                o.metode_pembayaran,
            ]
            row_bg = STATUS_ROW_COLORS.get(o.status_pesanan)
            for c, v in enumerate(vals):
                item = QTableWidgetItem(v)
                item.setTextAlignment(
                    Qt.AlignCenter if c in (0, 4, 5, 6) else Qt.AlignLeft | Qt.AlignVCenter
                )
                if row_bg:
                    item.setBackground(QColor(row_bg))
                self.table.setItem(r, c, item)

            # Warna badge kategori
            cat_color = STATUS_COLORS.get(o.kategori, "#6b7280")
            self.table.item(r, 3).setForeground(QColor(cat_color))

    def _load_stats(self, orders: list[OrderRecord]):
        stats = self.api.summary_stats(orders)
        self._update_stat_card(self._card_tx,    Formatter.number(stats["total_tx"]))
        self._update_stat_card(self._card_rev,   Formatter.short_currency(stats["total_rev"]))
        self._update_stat_card(self._card_avg,   Formatter.short_currency(stats["avg_rev"]))
        self._update_stat_card(self._card_units, Formatter.number(stats["total_units"]))

    def _load_charts(self, orders: list[OrderRecord]):
        agg = {
            "revenue_by_kategori": self.api.revenue_by_kategori(orders),
            "revenue_by_status":   self.api.revenue_by_status(orders),
            "revenue_by_month":    self.api.revenue_by_month(orders),
            "units_by_payment":    self.api.units_by_payment(orders),
            "top_products":        self.api.top_products(orders),
        }
        self._dash_chart.set_data(agg)

    # ─── Filter ───────────────────────────────────────────────────────────────

    @Slot()
    def _on_filter_changed(self):
        self.refresh_all()

    @Slot()
    def _on_selection_changed(self):
        has = bool(self.table.selectedItems())
        self.btn_edit.setEnabled(has)
        self.btn_del.setEnabled(has)

    def _selected_order_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return int(item.text()) if item else None

    def _selected_order(self) -> OrderRecord | None:
        oid = self._selected_order_id()
        if oid is None:
            return None
        for o in self._orders:
            if o.id == oid:
                return o
        return None

    # ─── CRUD ─────────────────────────────────────────────────────────────────

    def _tambah(self):
        products = self.api.get_products()
        if not products:
            QMessageBox.warning(self, "Produk Kosong",
                                "Tidak ada produk di database.\n"
                                "Pastikan API aktif dan tabel products sudah terisi.")
            return
        dlg = DialogOrder(self, products=products)
        if dlg.exec() != QDialog.Accepted:
            return
        data = dlg.get_raw_data()
        try:
            result = self.api.create_order({
                "nama_pelanggan": data["nama_pelanggan"],
                "product_id":     data["product_id"],
                "jumlah":         data["jumlah"],
                "total_harga":    data["total_harga"],
            })
            self.refresh_all()
            self.lbl_status.setText(f"  ✅  Pesanan baru berhasil dicatat.")
        except Exception as e:
            QMessageBox.critical(self, "Gagal Tambah", f"Error: {e}")

    def _edit(self):
        order = self._selected_order()
        if not order:
            QMessageBox.information(self, "Info", "Pilih baris yang ingin diedit.")
            return

        # Hanya update status_pesanan via API
        from PySide6.QtWidgets import QInputDialog
        status, ok = QInputDialog.getItem(
            self, "Update Status Pesanan",
            f"Pilih status baru untuk pesanan ID {order.id}\n"
            f"Pelanggan: {order.nama_pelanggan}",
            STATUS_PESANAN,
            STATUS_PESANAN.index(order.status_pesanan) if order.status_pesanan in STATUS_PESANAN else 0,
            False,
        )
        if not ok:
            return
        try:
            self.api.update_order_status(order.id, status)
            self.refresh_all()
            self.lbl_status.setText(f"  ✅  Status pesanan ID {order.id} diperbarui → {status}")
        except Exception as e:
            QMessageBox.critical(self, "Gagal Update", f"Error: {e}")

    def _hapus(self):
        order = self._selected_order()
        if not order:
            QMessageBox.information(self, "Info", "Pilih baris yang ingin dihapus.")
            return
        ret = QMessageBox.question(
            self, "Konfirmasi Hapus",
            f"Hapus pesanan berikut?\n\n"
            f"  ID       : {order.id}\n"
            f"  Pelanggan: {order.nama_pelanggan}\n"
            f"  Produk   : {order.nama_barang}\n"
            f"  Total    : {Formatter.currency(order.total_harga)}\n\n"
            f"Tindakan ini tidak bisa dibatalkan.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if ret != QMessageBox.Yes:
            return
        try:
            self.api.delete_order(order.id)
            self.refresh_all()
            self.lbl_status.setText(f"  🗑️  Pesanan ID {order.id} berhasil dihapus.")
        except Exception as e:
            QMessageBox.critical(self, "Gagal Hapus", f"Error: {e}")

    def _import_file(self):
        dlg = DialogImport(self, api=self.api)
        if dlg.exec() == QDialog.Accepted:
            self.refresh_all()
            self.lbl_status.setText("  ✅  Import selesai. Data berhasil dimuat ulang.")

    def _logout(self):
        ret = QMessageBox.question(self, "Logout",
                                   "Yakin ingin keluar dari sistem?",
                                   QMessageBox.Yes | QMessageBox.No,
                                   QMessageBox.No)
        if ret == QMessageBox.Yes:
            self.close()
            # Buka kembali login window
            from login_window import LoginWindow
            from PySide6.QtWidgets import QApplication
            import sys
            self._login_win = LoginWindow()
            self._login_win.show()
