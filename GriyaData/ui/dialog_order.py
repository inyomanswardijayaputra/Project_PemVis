from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox,
    QPushButton, QLabel, QFrame, QMessageBox,
    QScrollArea, QWidget, QDateEdit,
)
from PySide6.QtCore import Qt, QDate
from utils import Formatter
from core.api_handler import OrderRecord, ProductRecord

STATUS_LIST  = ["Pending", "Diproses", "Dikirim", "Selesai", "Dibatalkan"]
PAYMENT_LIST = ["Offline/COD", "Transfer Bank", "QRIS", "OVO", "GoPay", "ShopeePay"]
GENDER_LIST  = ["L", "P", "Lainnya"]
COURIER_LIST = ["JNE", "J&T", "SiCepat", "AnterAja", "Pos Indonesia", "Gosend", "Grab Express", "Lainnya"]
CHANNEL_LIST = ["Shopee", "Tokopedia", "Lazada", "TikTok Shop", "Website", "Offline", "Lainnya"]


class DialogOrder(QDialog):
    def __init__(self, parent=None, record: OrderRecord = None,
                 products: list[ProductRecord] = None):
        super().__init__(parent)
        self._record   = record
        self._products = products or []
        self._build_ui()
        if record:
            self._fill(record)
        self.inp_produk.currentIndexChanged.connect(self._auto_total)
        self.inp_qty.valueChanged.connect(self._auto_total)
        self.inp_discount.valueChanged.connect(self._auto_total)
        self.inp_shipping.valueChanged.connect(self._auto_total)
        self._auto_total()

    def _build_ui(self):
        mode = "Edit Pesanan" if self._record else "Tambah Pesanan Baru"
        self.setWindowTitle(mode)
        self.setMinimumWidth(520)
        self.setMinimumHeight(600)
        self.setObjectName("dialogSales")

        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # Header
        hdr = QFrame(); hdr.setObjectName("dialogHeader")
        h = QVBoxLayout(hdr); h.setContentsMargins(24, 16, 24, 14); h.setSpacing(3)
        t = QLabel(mode); t.setObjectName("dialogTitle")
        s = QLabel("Isi semua field — field bertanda * wajib diisi")
        s.setObjectName("dialogSubtitle")
        h.addWidget(t); h.addWidget(s)
        root.addWidget(hdr)

        # Scroll area
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        form = QFormLayout(body)
        form.setContentsMargins(24, 16, 24, 16)
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        def inp(placeholder=""):
            w = QLineEdit(); w.setObjectName("inputField")
            w.setPlaceholderText(placeholder)
            return w

        def cmb(items):
            w = QComboBox(); w.setObjectName("inputField")
            w.addItems(items); return w

        self._section(form, "── Identitas Pesanan ──")

        self.inp_order_id = inp("e.g. ORD00001  (kosongkan = auto)")
        form.addRow("Order ID", self.inp_order_id)

        self.inp_sales_date = QDateEdit()
        self.inp_sales_date.setObjectName("inputField")
        self.inp_sales_date.setCalendarPopup(True)
        self.inp_sales_date.setDate(QDate.currentDate())
        self.inp_sales_date.setDisplayFormat("yyyy-MM-dd")
        form.addRow("Sales Date *", self.inp_sales_date)

        self.inp_channel = cmb(CHANNEL_LIST)
        form.addRow("Sales Channel *", self.inp_channel)

        self._section(form, "── Data Pelanggan ──")

        self.inp_nama = inp("Nama pelanggan...")
        form.addRow("Customer Name *", self.inp_nama)

        self.inp_gender = cmb(GENDER_LIST)
        form.addRow("Gender *", self.inp_gender)

        self.inp_city = inp("e.g. Jakarta")
        form.addRow("Customer City *", self.inp_city)

        self.inp_address = inp("Alamat lengkap pengiriman...")
        form.addRow("Shipping Address", self.inp_address)

        self._section(form, "── Produk & Harga ──")

        self.inp_produk = QComboBox(); self.inp_produk.setObjectName("inputField")
        self.inp_produk.addItem("-- Pilih Produk --", 0)
        for p in self._products:
            self.inp_produk.addItem(
                f"{p.product_name} ({p.category}) — {Formatter.currency(p.price)}", p.id)
        form.addRow("Produk *", self.inp_produk)

        self.inp_qty = QSpinBox(); self.inp_qty.setObjectName("inputField")
        self.inp_qty.setButtonSymbols(QSpinBox.PlusMinus)
        self.inp_qty.setRange(1, 9999); self.inp_qty.setValue(1)
        form.addRow("Quantity *", self.inp_qty)

        self.inp_discount = QDoubleSpinBox(); self.inp_discount.setObjectName("inputField")
        self.inp_discount.setButtonSymbols(QDoubleSpinBox.PlusMinus) 
        self.inp_discount.setRange(0, 999_999_999); self.inp_discount.setDecimals(0)
        self.inp_discount.setPrefix("Rp "); self.inp_discount.setValue(0)
        form.addRow("Discount (Rp)", self.inp_discount)

        self.inp_shipping = QDoubleSpinBox(); self.inp_shipping.setObjectName("inputField")
        self.inp_shipping.setButtonSymbols(QDoubleSpinBox.PlusMinus) 
        self.inp_shipping.setRange(0, 999_999_999); self.inp_shipping.setDecimals(0)
        self.inp_shipping.setPrefix("Rp "); self.inp_shipping.setValue(0)
        form.addRow("Shipping Fee (Rp)", self.inp_shipping)

        # Total & Total Sales 
        self.inp_total = QDoubleSpinBox(); self.inp_total.setObjectName("inputField")
        self.inp_total.setButtonSymbols(QDoubleSpinBox.PlusMinus) 
        self.inp_total.setRange(0, 999_999_999); self.inp_total.setDecimals(0)
        self.inp_total.setPrefix("Rp "); self.inp_total.setReadOnly(True)
        self.inp_total.setToolTip("Auto: (Qty × Harga) − Discount")
        form.addRow("Total (auto)", self.inp_total)

        self.inp_total_sales = QDoubleSpinBox(); self.inp_total_sales.setObjectName("inputField")
        self.inp_total_sales.setButtonSymbols(QDoubleSpinBox.PlusMinus) 
        self.inp_total_sales.setRange(0, 999_999_999); self.inp_total_sales.setDecimals(0)
        self.inp_total_sales.setPrefix("Rp "); self.inp_total_sales.setReadOnly(True)
        self.inp_total_sales.setToolTip("Auto: Total + Shipping Fee")
        form.addRow("Total Sales (auto)", self.inp_total_sales)

        self._section(form, "── Pengiriman & Status ──")

        self.inp_courier = cmb(COURIER_LIST)
        form.addRow("Courier *", self.inp_courier)

        self.inp_est_days = QSpinBox(); self.inp_est_days.setObjectName("inputField")
        self.inp_est_days.setButtonSymbols(QSpinBox.PlusMinus) 
        self.inp_est_days.setRange(0, 30); self.inp_est_days.setValue(3)
        self.inp_est_days.setSuffix(" hari")
        form.addRow("Est. Delivery Days", self.inp_est_days)

        self.inp_status = cmb(STATUS_LIST)
        form.addRow("Status *", self.inp_status)

        self.inp_payment = cmb(PAYMENT_LIST)
        form.addRow("Payment Method *", self.inp_payment)

        self.inp_rating = QDoubleSpinBox(); self.inp_rating.setObjectName("inputField")
        self.inp_rating.setButtonSymbols(QDoubleSpinBox.PlusMinus) 
        self.inp_rating.setRange(0, 5); self.inp_rating.setDecimals(1)
        self.inp_rating.setSingleStep(0.1); self.inp_rating.setValue(0)
        self.inp_rating.setSuffix(" / 5")
        form.addRow("Customer Rating", self.inp_rating)

        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        # Footer
        footer = QFrame(); footer.setObjectName("dialogFooter")
        f = QHBoxLayout(footer); f.setContentsMargins(24, 12, 24, 12); f.addStretch()
        btn_batal = QPushButton("Batal"); btn_batal.setObjectName("btnSecondary")
        btn_batal.clicked.connect(self.reject)
        btn_ok = QPushButton("Simpan" if self._record else "Tambah")
        btn_ok.setObjectName("btnPrimary"); btn_ok.setDefault(True)
        btn_ok.clicked.connect(self._submit)
        f.addWidget(btn_batal); f.addWidget(btn_ok)
        root.addWidget(footer)

    def _section(self, form, title):
        lbl = QLabel(title)
        lbl.setStyleSheet("font-size:10px;font-weight:700;color:#6b7280;"
                          "padding-top:8px;")
        form.addRow("", lbl)

    def _auto_total(self):
        pid    = self.inp_produk.currentData()
        qty    = self.inp_qty.value()
        harga  = 0.0
        for p in self._products:
            if p.id == pid:
                harga = p.price; break
        subtotal   = qty * harga
        total      = max(0.0, subtotal - self.inp_discount.value())
        total_sales = total + self.inp_shipping.value()
        self.inp_total.setValue(total)
        self.inp_total_sales.setValue(total_sales)

    def _fill(self, r: OrderRecord):
        self.inp_order_id.setText(r.order_id or "")
        if r.sales_date:
            try:
                d = QDate.fromString(r.sales_date[:10], "yyyy-MM-dd")
                if d.isValid(): self.inp_sales_date.setDate(d)
            except: pass
        _set_combo(self.inp_channel,  r.sales_channel)
        self.inp_nama.setText(r.customer_name)
        _set_combo(self.inp_gender,   r.customer_gender)
        self.inp_city.setText(r.customer_city)
        self.inp_address.setText(r.shipping_address)
        for i in range(self.inp_produk.count()):
            if self.inp_produk.itemData(i) == r.product_id:
                self.inp_produk.setCurrentIndex(i); break
        self.inp_qty.setValue(r.quantity)
        self.inp_discount.setValue(r.discount)
        self.inp_shipping.setValue(r.shipping_fee)
        self.inp_total.setValue(r.total)
        self.inp_total_sales.setValue(r.total_sales)
        _set_combo(self.inp_courier, r.courier)
        self.inp_est_days.setValue(r.estimated_delivery_days)
        _set_combo(self.inp_status,  r.status)
        _set_combo(self.inp_payment, r.payment_method)
        self.inp_rating.setValue(r.customer_rating)

    def _submit(self):
        if not self.inp_nama.text().strip():
            QMessageBox.warning(self, "Validasi", "Customer Name wajib diisi."); return
        if not self.inp_produk.currentData():
            QMessageBox.warning(self, "Validasi", "Pilih produk terlebih dahulu."); return
        if self.inp_qty.value() <= 0:
            QMessageBox.warning(self, "Validasi", "Quantity harus lebih dari 0."); return
        self.accept()

    def get_raw_data(self) -> dict:
        return {
            "order_id":               self.inp_order_id.text().strip() or None,
            "sales_date":             self.inp_sales_date.date().toString("yyyy-MM-dd"),
            "sales_channel":          self.inp_channel.currentText(),
            "customer_name":          self.inp_nama.text().strip(),
            "customer_gender":        self.inp_gender.currentText(),
            "customer_city":          self.inp_city.text().strip(),
            "shipping_address":       self.inp_address.text().strip(),
            "product_id":             self.inp_produk.currentData() or 0,
            "quantity":               self.inp_qty.value(),
            "discount":               self.inp_discount.value(),
            "shipping_fee":           self.inp_shipping.value(),
            "total":                  self.inp_total.value(),
            "total_sales":            self.inp_total_sales.value(),
            "courier":                self.inp_courier.currentText(),
            "estimated_delivery_days":self.inp_est_days.value(),
            "status":                 self.inp_status.currentText(),
            "payment_method":         self.inp_payment.currentText(),
            "customer_rating":        self.inp_rating.value(),
        }


def _set_combo(combo: QComboBox, val: str):
    idx = combo.findText(str(val or ""))
    if idx >= 0: combo.setCurrentIndex(idx)