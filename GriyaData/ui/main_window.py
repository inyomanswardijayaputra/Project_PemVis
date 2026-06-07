from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QLabel, QFrame, QComboBox, QDialog,
    QMessageBox, QSizePolicy, QLineEdit, QFormLayout,
    QDialogButtonBox,
)
from PySide6.QtCore import Qt, Slot, QThread, Signal
from PySide6.QtGui import QAction, QColor

from core.api_handler import APIHandler, OrderRecord, ProductRecord
from utils import Formatter
from ui.chart_widget import ChartWidget
from ui.dialog_order import DialogOrder
from ui.dialog_import import DialogImport
from ui.tab_prediksi import TabPrediksi

APP_TITLE = "GriyaData — Manajemen Penjualan"

STATUS_LIST  = ["All","Pending","Diproses","Dikirim","Selesai","Dibatalkan"]
CHANNEL_LIST = ["All","Shopee","Tokopedia","Lazada","TikTok Shop","Website","Offline"]


# Background loader
class DataLoader(QThread):
    finished = Signal(list)
    error    = Signal(str)
    def __init__(self, api, status, channel):
        super().__init__()
        self.api = api; self.status = status; self.channel = channel
    def run(self):
        try:
            self.finished.emit(self.api.get_all_orders(self.status, self.channel))
        except Exception as e:
            self.error.emit(str(e))


# Dialog Tambah/Edit Produk
class DialogProduk(QDialog):
    def __init__(self, parent=None, product: ProductRecord = None):
        super().__init__(parent)
        self.setWindowTitle("Tambah Produk" if product is None else "Edit Produk")
        self.setMinimumWidth(360)
        self.setObjectName("dialogSales")
        self._build(product)

    def _build(self, p):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 16); lay.setSpacing(14)

        title = QLabel("Tambah Produk Baru" if p is None else f"Edit Produk ID {p.id}")
        title.setObjectName("dialogTitle")
        lay.addWidget(title)

        form = QFormLayout(); form.setSpacing(10)
        self.inp_name = QLineEdit(p.product_name if p else "")
        self.inp_name.setObjectName("inputField")
        self.inp_name.setPlaceholderText("e.g. Meja Belajar")
        self.inp_cat  = QLineEdit(p.category if p else "")
        self.inp_cat.setObjectName("inputField")
        self.inp_cat.setPlaceholderText("e.g. Meja")
        self.inp_price = QLineEdit(str(p.price) if p else "")
        self.inp_price.setObjectName("inputField")
        self.inp_price.setPlaceholderText("e.g. 150000")

        form.addRow("Nama Produk *", self.inp_name)
        form.addRow("Category *",    self.inp_cat)
        form.addRow("Price *",       self.inp_price)
        lay.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setText("Simpan")
        btns.button(QDialogButtonBox.Ok).setObjectName("btnPrimary")
        btns.button(QDialogButtonBox.Cancel).setObjectName("btnSecondary")
        btns.accepted.connect(self._validate)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def _validate(self):
        if not self.inp_name.text().strip():
            QMessageBox.warning(self, "Input Kurang", "Nama produk tidak boleh kosong."); return
        if not self.inp_cat.text().strip():
            QMessageBox.warning(self, "Input Kurang", "Category tidak boleh kosong."); return
        try:
            float(self.inp_price.text().replace(",",""))
        except ValueError:
            QMessageBox.warning(self, "Input Salah", "Price harus berupa angka."); return
        self.accept()

    def get_data(self) -> dict:
        return {
            "product_name": self.inp_name.text().strip(),
            "category":     self.inp_cat.text().strip(),
            "price":        float(self.inp_price.text().replace(",","").strip()),
        }


# Main Window
class MainWindow(QMainWindow):
    def __init__(self, username="Admin"):
        super().__init__()
        self.username = username
        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(1280, 760)
        
        self.showMaximized()

        self.api = APIHandler()
        self._orders: list[OrderRecord] = []
        self._loader = None

        self._build_menu()
        self._build_ui()
        self._build_statusbar()
        self.refresh_all()

    # Menu
    def _build_menu(self):
        mb = self.menuBar(); mb.setObjectName("menuBar")
        mf = mb.addMenu("&File")
        for label, shortcut, slot in [
            ("Refresh Data",         "F5",    self.refresh_all),
            ("Logout",                    "Ctrl+L", self._logout),
            ("Keluar",                    "Ctrl+Q", self.close),
        ]:
            a = QAction(label, self); a.setShortcut(shortcut)
            a.triggered.connect(slot); mf.addAction(a)
        md = mb.addMenu("&Pesanan")
        for label, shortcut, slot in [
            ("Tambah Pesanan",            "Ctrl+N", self._tambah_order),
            ("Edit Pesanan",              "Ctrl+E", self._edit_order),
            ("Hapus Pesanan",             "Delete", self._hapus_order),
            ("Import CSV/Excel",      "Ctrl+I", self._import_file),
        ]:
            a = QAction(label, self); a.setShortcut(shortcut)
            a.triggered.connect(slot); md.addAction(a)

    # Layout
    def _build_ui(self):
        central = QWidget(); central.setObjectName("mainContainer")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0,0,0,0); root.setSpacing(0)
        root.addWidget(self._make_banner())
        self.tabs = QTabWidget(); self.tabs.setObjectName("mainTabs")
        root.addWidget(self.tabs, 1)
        self._build_tab_dashboard()
        self._build_tab_orders()
        self._build_tab_products()
        self._build_tab_prediksi()

    def _make_banner(self):
        b = QFrame(); b.setObjectName("banner")
        lay = QHBoxLayout(b); lay.setContentsMargins(20,12,20,12)
        
        lbl = QLabel("GriyaData — Dashboard Manajemen Furniture")
        lbl.setObjectName("bannerApp")
        lbl.setStyleSheet("font-size:19px;font-weight:700;color:#1a1a1a;")
        lay.addWidget(lbl); lay.addStretch()
        fr = QFrame(); fr.setObjectName("frameIdentitas")
        
        fr.setMinimumWidth(280)
        il = QHBoxLayout(fr); il.setContentsMargins(14,6,14,6); il.setSpacing(16)
        
        il.addWidget(QLabel(f"User: {self.username}"))
        il.addWidget(QLabel("API: griyadataapi"))
        lay.addWidget(fr)
        return b

    # Tab Dashboard
    def _build_tab_dashboard(self):
        tab = QWidget(); tab.setObjectName("tabDashboard")
        root = QVBoxLayout(tab); root.setContentsMargins(20,16,20,16); root.setSpacing(16)
        cl = QHBoxLayout(); cl.setSpacing(12)
        self._card_tx    = self._stat_card("Total Pesanan",      "—", "#3b82f6")
        self._card_rev   = self._stat_card("Total Sales",        "—", "#10b981")
        self._card_avg   = self._stat_card("Rata-rata / Order",  "—", "#f59e0b")
        self._card_units = self._stat_card("Total Unit Terjual", "—", "#8b5cf6")
        for c in (self._card_tx, self._card_rev, self._card_avg, self._card_units):
            cl.addWidget(c)
        root.addLayout(cl)
        self._dash_chart = ChartWidget()
        self._dash_chart.combo_chart.setCurrentIndex(2)
        root.addWidget(self._dash_chart, 1)
        self.tabs.addTab(tab, "Dashboard")

    def _stat_card(self, title, value, color):
        card = QFrame(); card.setObjectName("statCard")
        card.setStyleSheet("""
            #statCard{background:#ffffff;border:1.5px solid #e5e7eb;border-radius:10px;}
            #statCard:hover{border-color:#bfdbfe;}""")
        lay = QVBoxLayout(card); lay.setContentsMargins(18,14,18,14); lay.setSpacing(4)
        lv = QLabel(value); lv.setStyleSheet(f"font-size:24px;font-weight:700;color:{color};")
        lv.setObjectName("cardVal")
        lt = QLabel(title); lt.setStyleSheet("font-size:11px;color:#6b7280;font-weight:600;")
        lay.addWidget(lv); lay.addWidget(lt)
        return card

    def _set_card(self, card, val):
        lbl = card.findChild(QLabel, "cardVal")
        if lbl: lbl.setText(val)

    # Tab Data Pesanan 
    def _build_tab_orders(self):
        tab = QWidget(); tab.setObjectName("tabTable")
        root = QVBoxLayout(tab); root.setContentsMargins(16,14,16,14); root.setSpacing(8)

        fb = QHBoxLayout(); fb.setSpacing(8)
        
        for label, attr, items in [
            ("Status:",  "f_status",  STATUS_LIST),
            ("Channel:", "f_channel", CHANNEL_LIST),
        ]:
            lbl = QLabel(label); lbl.setObjectName("panelSubinfo")
            lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
            cb = QComboBox(); cb.setObjectName("inputField")
            cb.setMinimumWidth(120); cb.setMaximumWidth(160)
            cb.addItems(items)
            cb.currentTextChanged.connect(self._on_filter_changed)
            setattr(self, attr, cb)
            fb.addWidget(lbl); fb.addWidget(cb); fb.addSpacing(12)

        btn_ref = QPushButton("Refresh"); btn_ref.setObjectName("btnRefresh")
        btn_ref.clicked.connect(self.refresh_all)
        fb.addWidget(btn_ref); fb.addStretch()

        btn_add = QPushButton("Tambah"); btn_add.setObjectName("btnPrimary")
        btn_add.clicked.connect(self._tambah_order); fb.addWidget(btn_add)
        self.btn_edit = QPushButton("Edit Pesanan"); self.btn_edit.setObjectName("btnSecondary")
        self.btn_edit.setEnabled(False); self.btn_edit.clicked.connect(self._edit_order)
        fb.addWidget(self.btn_edit)
        self.btn_del = QPushButton("Hapus"); self.btn_del.setObjectName("btnDanger")
        self.btn_del.setEnabled(False); self.btn_del.clicked.connect(self._hapus_order)
        fb.addWidget(self.btn_del)
        btn_imp = QPushButton("Import File"); btn_imp.setObjectName("btnSecondary")
        btn_imp.clicked.connect(self._import_file); fb.addWidget(btn_imp)
        root.addLayout(fb)

        self.table = QTableWidget(); self.table.setObjectName("dataTable")
        self._ORDER_COLS = [
            "ID DB", "Order ID", "Pelanggan", "Produk", "Category", "Price",
            "Qty", "Discount", "Total", "Shipping Fee", "Total Sales",
            "Status", "Alamat", "Gender", "Kota", "Payment",
            "Courier", "Est. Hari", "Channel", "Rating", "Sales Date",
        ]
        self.table.setColumnCount(len(self._ORDER_COLS))
        self.table.setHorizontalHeaderLabels(self._ORDER_COLS)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeToContents)
        hdr.setMinimumSectionSize(60)
        self.table.setHorizontalScrollMode(QTableWidget.ScrollPerPixel)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        
        self.table.setStyleSheet("""
            QTableWidget::item:selected {
                background-color: #3b82f6; 
                color: white;
            }
        """)
        
        self.table.itemSelectionChanged.connect(self._on_sel_changed)
        self.table.doubleClicked.connect(self._edit_order)
        root.addWidget(self.table)
        self.tabs.addTab(tab, "Data Pesanan")

    # Tab Produk
    def _build_tab_products(self):
        tab = QWidget(); tab.setObjectName("tabProduk")
        root = QVBoxLayout(tab); root.setContentsMargins(16,14,16,14); root.setSpacing(8)

        fb = QHBoxLayout(); fb.setSpacing(8)
        fb.addStretch()
        
        btn_ref = QPushButton("Refresh"); btn_ref.setObjectName("btnRefresh")
        btn_ref.clicked.connect(self._load_products)
        fb.addWidget(btn_ref)
        
        btn_add = QPushButton("Tambah Produk"); btn_add.setObjectName("btnPrimary")
        btn_add.clicked.connect(self._tambah_produk); fb.addWidget(btn_add)
        self.btn_edit_prod = QPushButton("Edit"); self.btn_edit_prod.setObjectName("btnSecondary")
        self.btn_edit_prod.setEnabled(False); self.btn_edit_prod.clicked.connect(self._edit_produk)
        fb.addWidget(self.btn_edit_prod)
        self.btn_del_prod = QPushButton("Hapus"); self.btn_del_prod.setObjectName("btnDanger")
        self.btn_del_prod.setEnabled(False); self.btn_del_prod.clicked.connect(self._hapus_produk)
        fb.addWidget(self.btn_del_prod)
        root.addLayout(fb)

        self.tbl_prod = QTableWidget(); self.tbl_prod.setObjectName("dataTable")
        pcols = ["ID", "Product Name", "Category", "Price"]
        self.tbl_prod.setColumnCount(len(pcols))
        self.tbl_prod.setHorizontalHeaderLabels(pcols)
        self.tbl_prod.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_prod.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.tbl_prod.setColumnWidth(0, 50)
        self.tbl_prod.setSelectionBehavior(QTableWidget.SelectRows)
        self.tbl_prod.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl_prod.setAlternatingRowColors(True)
        self.tbl_prod.verticalHeader().setVisible(False)
        self.tbl_prod.setShowGrid(False)
        self.tbl_prod.setStyleSheet("QTableWidget::item:selected { background-color: #3b82f6; color: white; }")
        self.tbl_prod.itemSelectionChanged.connect(self._on_prod_sel_changed)
        root.addWidget(self.tbl_prod)
        self.tabs.addTab(tab, "Produk")

    # Tab Prediksi ML
    def _build_tab_prediksi(self):
        self._tab_prediksi = TabPrediksi()
        self.tabs.addTab(self._tab_prediksi, "Prediksi ML")

    def _build_statusbar(self):
        sb = self.statusBar(); sb.setObjectName("statusBar")
        sb.setSizeGripEnabled(False)
        sb.setStyleSheet("QStatusBar::item { border: none; }")
        self.lbl_status = QLabel("  Memuat data...")
        sb.addWidget(self.lbl_status)

    # Data Loading
    def refresh_all(self):
        self.lbl_status.setText("Mengambil data dari API...")
        status  = self.f_status.currentText()  if hasattr(self, "f_status")  else "All"
        channel = self.f_channel.currentText() if hasattr(self, "f_channel") else "All"
        self._loader = DataLoader(self.api, status, channel)
        self._loader.finished.connect(self._on_data_loaded)
        self._loader.error.connect(self._on_data_error)
        self._loader.start()
        self._load_products()

    @Slot(list)
    def _on_data_loaded(self, orders):
        self._orders = orders
        self._fill_order_table(orders)
        stats = self.api.summary_stats(orders)
        self._set_card(self._card_tx,    Formatter.number(stats["total_tx"]))
        self._set_card(self._card_rev,   Formatter.short_currency(stats["total_rev"]))
        self._set_card(self._card_avg,   Formatter.short_currency(stats["avg_rev"]))
        self._set_card(self._card_units, Formatter.number(stats["total_units"]))
        self._dash_chart.set_data({
            "revenue_by_kategori": self.api.revenue_by_kategori(orders),
            "revenue_by_status":   self.api.revenue_by_status(orders),
            "revenue_by_month":    self.api.revenue_by_month(orders),
            "units_by_payment":    self.api.units_by_payment(orders),
            "top_products":        self.api.top_products(orders),
        })
        self._tab_prediksi.load_orders(orders)
        self.lbl_status.setText(
            f"{len(orders)} pesanan  |  diperbarui dari API")

    @Slot(str)
    def _on_data_error(self, msg):
        self.lbl_status.setText(f"Gagal memuat: {msg}")
        QMessageBox.warning(self, "Koneksi API Gagal", f"Detail: {msg}")

    def _fill_order_table(self, orders):
        STATUS_BG = {
            "Selesai":"#dcfce7","Diproses":"#dbeafe",
            "Dikirim":"#e0e7ff","Pending":"#fef9c3","Dibatalkan":"#fee2e2",
        }
        self.table.setRowCount(0)
        for o in orders:
            r = self.table.rowCount(); self.table.insertRow(r)
            vals = [
                str(o.id),
                o.order_id,
                o.customer_name,
                o.product_name,
                o.category,
                Formatter.currency(o.price),
                str(o.quantity),
                Formatter.currency(o.discount),
                Formatter.currency(o.total),
                Formatter.currency(o.shipping_fee),
                Formatter.currency(o.total_sales),
                o.status,
                o.shipping_address,
                o.customer_gender,
                o.customer_city,
                o.payment_method,
                o.courier,
                str(o.estimated_delivery_days),
                o.sales_channel,
                str(o.customer_rating),
                o.sales_date,
            ]
            bg = STATUS_BG.get(o.status)
            for c, v in enumerate(vals):
                item = QTableWidgetItem(v)
                item.setTextAlignment(Qt.AlignCenter)
                if bg: item.setBackground(QColor(bg))
                self.table.setItem(r, c, item)

    # Produk tab
    def _load_products(self):
        prods = self.api.get_products()
        self.tbl_prod.setRowCount(0)
        for p in prods:
            r = self.tbl_prod.rowCount(); self.tbl_prod.insertRow(r)
            for c, v in enumerate([str(p.id), p.product_name, p.category,
                                    Formatter.currency(p.price)]):
                item = QTableWidgetItem(v)
                item.setTextAlignment(Qt.AlignCenter)
                self.tbl_prod.setItem(r, c, item)

    def _on_prod_sel_changed(self):
        has = bool(self.tbl_prod.selectedItems())
        self.btn_edit_prod.setEnabled(has)
        self.btn_del_prod.setEnabled(has)

    def _selected_product(self) -> ProductRecord | None:
        row = self.tbl_prod.currentRow()
        if row < 0: return None
        pid = int(self.tbl_prod.item(row, 0).text())
        for p in self.api._products_cache:
            if p.id == pid: return p
        return None

    def _tambah_produk(self):
        dlg = DialogProduk(self)
        if dlg.exec() != QDialog.Accepted: return
        try:
            self.api.create_product(dlg.get_data())
            self._load_products()
            self.lbl_status.setText("Produk baru berhasil ditambahkan.")
        except Exception as e:
            QMessageBox.critical(self, "Gagal Tambah Produk", str(e))

    def _edit_produk(self):
        p = self._selected_product()
        if not p: return
        dlg = DialogProduk(self, product=p)
        if dlg.exec() != QDialog.Accepted: return
        try:
            self.api.update_product(p.id, dlg.get_data())
            self._load_products()
            self.lbl_status.setText(f"Produk ID {p.id} berhasil diperbarui.")
        except Exception as e:
            QMessageBox.critical(self, "Gagal Edit Produk", str(e))

    def _hapus_produk(self):
        p = self._selected_product()
        if not p: return
        if QMessageBox.question(
            self, "Hapus Produk",
            f"Hapus produk '{p.product_name}'?\nPesanan yang menggunakan produk ini mungkin terpengaruh.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        ) != QMessageBox.Yes: return
        try:
            self.api.delete_product(p.id)
            self._load_products()
            self.lbl_status.setText(f"Produk '{p.product_name}' dihapus.")
        except Exception as e:
            QMessageBox.critical(self, "Gagal Hapus Produk", str(e))

    # Filter & Selection
    @Slot()
    def _on_filter_changed(self): self.refresh_all()

    @Slot()
    def _on_sel_changed(self):
        has = bool(self.table.selectedItems())
        self.btn_edit.setEnabled(has); self.btn_del.setEnabled(has)

    def _selected_order(self):
        row = self.table.currentRow()
        if row < 0: return None
        oid = int(self.table.item(row, 0).text())
        for o in self._orders:
            if o.id == oid: return o
        return None

    # CRUD Pesanan
    def _tambah_order(self):
        prods = self.api.get_products()
        if not prods:
            QMessageBox.warning(self, "Produk Kosong",
                                "Tambahkan produk dulu di tab Produk."); return
        dlg = DialogOrder(self, products=prods)
        if dlg.exec() != QDialog.Accepted: return
        try:
            self.api.create_order(dlg.get_raw_data())
            self.refresh_all()
            self.lbl_status.setText("Pesanan baru berhasil dicatat.")
        except Exception as e:
            QMessageBox.critical(self, "Gagal Tambah", str(e))

    def _edit_order(self):
        o = self._selected_order()
        if not o:
            QMessageBox.information(self, "Info", "Pilih baris yang ingin diedit."); return
        prods = self.api.get_products()
        dlg = DialogOrder(self, record=o, products=prods)
        if dlg.exec() != QDialog.Accepted: return
        try:
            self.api.update_order(o.id, dlg.get_raw_data())
            self.refresh_all()
            self.lbl_status.setText(f"Pesanan ID {o.id} berhasil diperbarui.")
        except Exception as e:
            QMessageBox.critical(self, "Gagal Update", str(e))

    def _hapus_order(self):
        o = self._selected_order()
        if not o:
            QMessageBox.information(self, "Info", "Pilih baris yang ingin dihapus."); return
        if QMessageBox.question(
            self, "Konfirmasi Hapus",
            f"Hapus pesanan ID {o.id} — {o.customer_name} ({o.product_name})?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        ) != QMessageBox.Yes: return
        try:
            self.api.delete_order(o.id)
            self.refresh_all()
            self.lbl_status.setText(f"Pesanan ID {o.id} dihapus.")
        except Exception as e:
            QMessageBox.critical(self, "Gagal Hapus", str(e))

    def _import_file(self):
        dlg = DialogImport(self, api=self.api)
        if dlg.exec() == QDialog.Accepted:
            self.refresh_all()
            self.lbl_status.setText("Import selesai.")

    def _logout(self):
        if QMessageBox.question(
            self, "Logout", "Yakin ingin keluar?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        ) == QMessageBox.Yes:
            self.close()
            from ui.login_window import LoginWindow
            self._lw = LoginWindow(); self._lw.show()