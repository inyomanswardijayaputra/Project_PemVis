"""
ui/dialog_order.py
Dialog Tambah / Edit pesanan miniatur — memanggil API GriyaData
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox,
    QPushButton, QLabel, QFrame, QMessageBox,
)
from PySide6.QtCore import Qt

from utils import OrderValidator, Formatter, STATUS_PESANAN, METODE_PEMBAYARAN
from api_handler import OrderRecord, ProductRecord


class DialogOrder(QDialog):
    def __init__(self, parent=None, record: OrderRecord = None,
                 products: list[ProductRecord] = None):
        super().__init__(parent)
        self._record = record
        self._products = products or []
        self._build_ui()
        if record:
            self._fill(record)
        self.inp_jumlah.valueChanged.connect(self._auto_total)
        self._auto_total()

    def _build_ui(self):
        mode = "Edit Pesanan" if self._record else "Tambah Pesanan Baru"
        self.setWindowTitle(mode)
        self.setMinimumWidth(480)
        self.setObjectName("dialogSales")

        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # Header
        hdr = QFrame()
        hdr.setObjectName("dialogHeader")
        h = QVBoxLayout(hdr)
        h.setContentsMargins(24, 16, 24, 14)
        h.setSpacing(3)
        lbl_t = QLabel(mode)
        lbl_t.setObjectName("dialogTitle")
        lbl_s = QLabel("Isi semua field yang wajib (*) diisi")
        lbl_s.setObjectName("dialogSubtitle")
        h.addWidget(lbl_t)
        h.addWidget(lbl_s)
        root.addWidget(hdr)

        # Body form
        body = QFrame()
        body.setObjectName("dialogBody")
        form = QFormLayout(body)
        form.setContentsMargins(24, 18, 24, 18)
        form.setSpacing(11)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.inp_nama = QLineEdit()
        self.inp_nama.setPlaceholderText("Nama pelanggan...")
        self.inp_nama.setObjectName("inputField")
        form.addRow("Nama Pelanggan *", self.inp_nama)

        self.inp_produk = QComboBox()
        self.inp_produk.setObjectName("inputField")
        self.inp_produk.addItem("-- Pilih Produk --", 0)
        for p in self._products:
            self.inp_produk.addItem(f"{p.nama_barang} ({p.kategori}) — {Formatter.currency(p.harga)}", p.id)
        self.inp_produk.currentIndexChanged.connect(self._auto_total)
        form.addRow("Produk *", self.inp_produk)

        self.inp_jumlah = QSpinBox()
        self.inp_jumlah.setRange(1, 9999)
        self.inp_jumlah.setValue(1)
        self.inp_jumlah.setObjectName("inputField")
        form.addRow("Jumlah *", self.inp_jumlah)

        self.inp_total = QDoubleSpinBox()
        self.inp_total.setRange(0, 999_999_999)
        self.inp_total.setDecimals(0)
        self.inp_total.setPrefix("Rp ")
        self.inp_total.setReadOnly(True)
        self.inp_total.setObjectName("inputField")
        self.inp_total.setToolTip("Dihitung otomatis: Jumlah × Harga Satuan")
        form.addRow("Total Harga (auto)", self.inp_total)

        self.inp_status = QComboBox()
        self.inp_status.addItems(STATUS_PESANAN)
        self.inp_status.setObjectName("inputField")
        form.addRow("Status Pesanan *", self.inp_status)

        self.inp_metode = QComboBox()
        self.inp_metode.addItems(METODE_PEMBAYARAN)
        self.inp_metode.setObjectName("inputField")
        form.addRow("Metode Pembayaran *", self.inp_metode)

        root.addWidget(body)

        # Footer
        footer = QFrame()
        footer.setObjectName("dialogFooter")
        f = QHBoxLayout(footer)
        f.setContentsMargins(24, 12, 24, 12)
        f.addStretch()

        btn_batal = QPushButton("Batal")
        btn_batal.setObjectName("btnSecondary")
        btn_batal.clicked.connect(self.reject)

        label_ok = "Simpan" if self._record else "Tambah"
        btn_ok = QPushButton(label_ok)
        btn_ok.setObjectName("btnPrimary")
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self._submit)

        f.addWidget(btn_batal)
        f.addWidget(btn_ok)
        root.addWidget(footer)

    def _auto_total(self):
        pid = self.inp_produk.currentData()
        jumlah = self.inp_jumlah.value()
        harga = 0.0
        for p in self._products:
            if p.id == pid:
                harga = p.harga
                break
        self.inp_total.setValue(jumlah * harga)

    def _fill(self, r: OrderRecord):
        self.inp_nama.setText(r.nama_pelanggan)
        # Pilih produk
        for i in range(self.inp_produk.count()):
            if self.inp_produk.itemData(i) == r.product_id:
                self.inp_produk.setCurrentIndex(i)
                break
        self.inp_jumlah.setValue(r.jumlah)
        self.inp_total.setValue(r.total_harga)
        idx_s = self.inp_status.findText(r.status_pesanan)
        if idx_s >= 0:
            self.inp_status.setCurrentIndex(idx_s)
        idx_m = self.inp_metode.findText(r.metode_pembayaran)
        if idx_m >= 0:
            self.inp_metode.setCurrentIndex(idx_m)

    def _submit(self):
        data = self.get_raw_data()
        result = OrderValidator.validate(data)
        if not result.valid:
            QMessageBox.warning(self, "Validasi Form", result.error_text())
            return
        self.accept()

    def get_raw_data(self) -> dict:
        return {
            "nama_pelanggan": self.inp_nama.text().strip(),
            "product_id": self.inp_produk.currentData() or 0,
            "jumlah": self.inp_jumlah.value(),
            "total_harga": self.inp_total.value(),
            "status_pesanan": self.inp_status.currentText(),
            "metode_pembayaran": self.inp_metode.currentText(),
        }
