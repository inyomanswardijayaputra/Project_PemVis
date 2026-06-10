import matplotlib
#matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QRadioButton, QButtonGroup, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit,
    QTabWidget, QWidget, QProgressBar, QSizePolicy, QMessageBox,
    QScrollArea,
)
from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtGui import QFont, QColor

# ML engine
from ml.predictor import (
    predict_total_penjualan,
    predict_per_produk,
    daftar_produk_dari_orders,
    HarapanPrediksi,
    HasilPrediksi,
)

# Formatter 
try:
    from utils import Formatter
    _fmt_currency = Formatter.currency
except Exception:
    def _fmt_currency(v): return f"Rp {v:,.0f}"

# Background worker thread
class PrediksiWorker(QThread):
    finished = Signal(object) 
    error    = Signal(str)

    def __init__(self, orders, mode: str, nama_produk: str, n_bulan: int):
        super().__init__()
        self.orders      = orders
        self.mode        = mode          
        self.nama_produk = nama_produk
        self.n_bulan     = n_bulan

    def run(self):
        try:
            if self.mode == "semua":
                hasil = predict_total_penjualan(self.orders, self.n_bulan)
            else:
                hasil = predict_per_produk(self.orders, self.nama_produk, self.n_bulan)
            self.finished.emit(hasil)
        except Exception as e:
            self.error.emit(str(e))

# Chart Canvas
class PrediksiCanvas(FigureCanvas):
    def __init__(self, parent=None):
        self.fig = Figure(figsize=(9, 4), facecolor="#f8fafc")
        super().__init__(self.fig)
        self.setParent(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def plot_hasil(self, hasil: "HasilPrediksi", warna_pred: str = "#ef4444", judul: str = ""):
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        ax.set_facecolor("#ffffff")
        self.fig.patch.set_facecolor("#f8fafc")

        hist_labels = hasil.data_historis_label
        hist_values = hasil.data_historis_nilai
        pred_labels = hasil.bulan_labels
        pred_values = hasil.nilai_prediksi

        all_labels = hist_labels + pred_labels
        n_hist = len(hist_labels)

        ax.plot(
            range(n_hist),
            hist_values,
            color="#3b82f6", linewidth=2.5, marker="o", markersize=5,
            label="Historis", zorder=3,
        )
        ax.fill_between(range(n_hist), hist_values, alpha=0.12, color="#3b82f6")

        pred_x = range(n_hist - 1, n_hist + len(pred_values))
        pred_y = [hist_values[-1]] + pred_values if hist_values else pred_values
        ax.plot(
            pred_x, pred_y,
            color=warna_pred, linewidth=2.5, linestyle="--",
            marker="s", markersize=6, label=f"Proyeksi ({hasil.nama_model})", zorder=3,
        )
        ax.fill_between(pred_x, pred_y, alpha=0.10, color=warna_pred)

        if n_hist > 0:
            ax.axvline(x=n_hist - 1, color="#94a3b8", linestyle=":", linewidth=1.5, alpha=0.7)

        for i, (lbl, val) in enumerate(zip(pred_labels, pred_values)):
            ax.annotate(
                f"Rp {val/1_000_000:.1f}Jt" if val >= 1_000_000 else f"Rp {val:,.0f}",
                xy=(n_hist + i, val),
                xytext=(0, 10), textcoords="offset points",
                ha="center", fontsize=7.5, color=warna_pred, fontweight="bold",
            )

        ax.set_xticks(range(len(all_labels)))
        ax.set_xticklabels(all_labels, rotation=45, ha="right", fontsize=8)
        ax.yaxis.set_major_formatter(
            plt.FuncFormatter(lambda x, _: f"Rp {x/1_000_000:.1f}Jt" if x >= 1_000_000 else f"Rp {x:,.0f}")
        )
        ax.set_title(judul or f"Hasil Analisis — {hasil.nama_model}", fontsize=11, fontweight="bold", pad=10)
        ax.set_ylabel("Estimasi Revenue (Rp)", fontsize=9)
        ax.legend(fontsize=9, loc="upper left")
        ax.grid(axis="y", linestyle="--", alpha=0.4)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        self.fig.tight_layout()
        self.draw()

    def plot_perbandingan(self, hasil: "HarapanPrediksi"):
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        ax.set_facecolor("#ffffff")
        self.fig.patch.set_facecolor("#f8fafc")

        labels  = hasil.linear.bulan_labels
        lin_val = hasil.linear.nilai_prediksi
        rf_val  = hasil.random_forest.nilai_prediksi

        x = range(len(labels))
        width = 0.35

        bars1 = ax.bar([i - width/2 for i in x], lin_val, width,
                       label="Model Linear", color="#3b82f6", alpha=0.85, zorder=3)
        bars2 = ax.bar([i + width/2 for i in x], rf_val, width,
                       label="Model Dinamis", color="#10b981", alpha=0.85, zorder=3)

        for bar in bars1:
            h = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2, h + max(h*0.02, 100),
                    f"Rp {h/1_000_000:.1f}Jt" if h >= 1_000_000 else f"Rp {h:,.0f}",
                    ha="center", fontsize=7, color="#1d4ed8", fontweight="bold")
        for bar in bars2:
            h = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2, h + max(h*0.02, 100),
                    f"Rp {h/1_000_000:.1f}Jt" if h >= 1_000_000 else f"Rp {h:,.0f}",
                    ha="center", fontsize=7, color="#065f46", fontweight="bold")

        ax.set_xticks(list(x))
        ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=9)
        ax.yaxis.set_major_formatter(
            plt.FuncFormatter(lambda v, _: f"Rp {v/1_000_000:.1f}Jt" if v >= 1_000_000 else f"Rp {v:,.0f}")
        )
        ax.set_title("Perbandingan Estimasi Metode", fontsize=11, fontweight="bold", pad=10)
        ax.legend(fontsize=9)
        ax.grid(axis="y", linestyle="--", alpha=0.4)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        self.fig.tight_layout()
        self.draw()

# Main Dialog
class DialogPrediksi(QDialog):
    def __init__(self, parent=None, orders: list = None):
        super().__init__(parent)
        self.orders  = orders or []
        self._hasil: HarapanPrediksi | None = None
        self._worker: PrediksiWorker | None = None

        self.setWindowTitle("Proyeksi Penjualan")
        self.setMinimumSize(1100, 680)
        self.resize(1200, 720)
        self.setModal(True)

        self._daftar_produk = daftar_produk_dari_orders(self.orders)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._make_header())

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._make_sidebar(), 0)
        body.addWidget(self._make_content(), 1)

        body_widget = QWidget()
        body_widget.setLayout(body)
        root.addWidget(body_widget, 1)

    def _make_header(self) -> QFrame:
        hdr = QFrame()
        hdr.setObjectName("banner")
        hdr.setStyleSheet("""
            QFrame { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 #2c3e50, stop:1 #2980b9);
                border-bottom: 1px solid #2c3e50; }
        """)
        lay = QHBoxLayout(hdr)
        lay.setContentsMargins(25, 15, 25, 15)

        ttl = QLabel("Analisis Estimasi Pendapatan")
        ttl.setStyleSheet("font-size:18px;font-weight:700;color:#ffffff;")
        lay.addWidget(ttl)
        lay.addStretch()

        sub = QLabel("Sistem Proyeksi GriyaData")
        sub.setStyleSheet("font-size:12px;color:#ecf0f1;")
        lay.addWidget(sub)
        return hdr

    def _make_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setFixedWidth(260)
        sidebar.setStyleSheet("""
            QFrame { background:#f8fafc; border-right: 1px solid #e2e8f0; }
            QLabel { color: #334155; }
            QRadioButton { color: #334155; font-size: 13px; padding: 6px; }
            QComboBox, QSpinBox {
                border: 1.5px solid #cbd5e1; border-radius: 6px;
                padding: 6px 10px; background: white; color: #1e293b;
                font-size: 12px;
            }
            QPushButton#btnPrediksi {
                background: #2563eb; color: white; font-weight: 700;
                font-size: 14px; border-radius: 8px; padding: 12px;
                border: none;
            }
            QPushButton#btnPrediksi:hover { background: #1d4ed8; }
            QPushButton#btnPrediksi:disabled { background: #94a3b8; }
        """)

        lay = QVBoxLayout(sidebar)
        lay.setContentsMargins(20, 25, 20, 20)
        lay.setSpacing(15)

        lbl_target = QLabel("PARAMETER ANALISIS")
        lbl_target.setStyleSheet("font-weight:800;font-size:11px;color:#64748b;letter-spacing:1px;")
        lay.addWidget(lbl_target)

        self._radio_semua  = QRadioButton("Seluruh Inventori")
        self._radio_produk = QRadioButton("Spesifik Produk")
        self._radio_semua.setChecked(True)
        self._radio_semua.toggled.connect(self._on_mode_changed)

        btn_group = QButtonGroup(self)
        btn_group.addButton(self._radio_semua)
        btn_group.addButton(self._radio_produk)

        lay.addWidget(self._radio_semua)
        lay.addWidget(self._radio_produk)

        self._combo_produk = QComboBox()
        self._combo_produk.addItems(self._daftar_produk or ["- No Data -"])
        self._combo_produk.setEnabled(False)
        lay.addWidget(self._combo_produk)

        sep1 = QFrame(); sep1.setFrameShape(QFrame.HLine)
        sep1.setStyleSheet("color:#e2e8f0;"); lay.addWidget(sep1)

        lay.addWidget(QLabel("Rentang Waktu (Bulan):"))
        self._spin_bulan = QSpinBox()
        self._spin_bulan.setRange(1, 12); self._spin_bulan.setValue(3)
        lay.addWidget(self._spin_bulan)

        lay.addStretch()

        self._progress = QProgressBar()
        self._progress.setRange(0, 0); self._progress.setVisible(False)
        self._progress.setFixedHeight(4)
        lay.addWidget(self._progress)

        self._btn_prediksi = QPushButton("Mulai Proses")
        self._btn_prediksi.setObjectName("btnPrediksi")
        self._btn_prediksi.clicked.connect(self._run_prediksi)
        lay.addWidget(self._btn_prediksi)

        return sidebar

    def _make_content(self) -> QWidget:
        widget = QWidget()
        widget.setStyleSheet("background: #ffffff;")
        lay = QVBoxLayout(widget)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(15)

        self._placeholder = QLabel(
            "Silakan tentukan parameter di panel kiri dan klik 'Mulai Proses'.\n\n"
            "Sistem akan menganalisis tren penjualan historis Anda\n"
            "untuk memberikan estimasi performa di masa mendatang."
        )
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setStyleSheet(
            "color:#64748b;font-size:14px;line-height:2.0;"
            "border: 2px dashed #f1f5f9; border-radius:15px; padding:50px;"
        )
        lay.addWidget(self._placeholder)

        self._result_widget = QWidget()
        self._result_widget.setVisible(False)
        res_lay = QVBoxLayout(self._result_widget)
        res_lay.setContentsMargins(0, 0, 0, 0)
        res_lay.setSpacing(15)

        self._tabs_chart = QTabWidget()
        self._tabs_chart.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #f1f5f9; border-radius: 10px; background: white; }
            QTabBar::tab { padding: 10px 25px; font-size: 13px; color: #64748b; background: #f8fafc; }
            QTabBar::tab:selected { background: white; color: #2563eb; font-weight: 700; border-bottom: 2px solid #2563eb; }
        """)

        tab_lin = QWidget(); tl = QVBoxLayout(tab_lin)
        self._canvas_linear = PrediksiCanvas(); tl.addWidget(self._canvas_linear)
        self._tabs_chart.addTab(tab_lin, "Estimasi Tren")

        tab_rf = QWidget(); tr = QVBoxLayout(tab_rf)
        self._canvas_rf = PrediksiCanvas(); tr.addWidget(self._canvas_rf)
        self._tabs_chart.addTab(tab_rf, "Estimasi Dinamis")

        tab_cmp = QWidget(); tc = QVBoxLayout(tab_cmp)
        self._canvas_cmp = PrediksiCanvas(); tc.addWidget(self._canvas_cmp)
        self._tabs_chart.addTab(tab_cmp, "Komparasi Metode")

        res_lay.addWidget(self._tabs_chart, 4)

        self._txt_insight = QTextEdit()
        self._txt_insight.setReadOnly(True)
        self._txt_insight.setMaximumHeight(100)
        self._txt_insight.setStyleSheet("background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:12px; font-size:12px; color:#334155;")
        res_lay.addWidget(self._txt_insight)

        self._tabel = QTableWidget()
        self._tabel.setMaximumHeight(200)
        self._tabel.setColumnCount(4)
        self._tabel.setHorizontalHeaderLabels(["Bulan", "Metode Tren", "Metode Dinamis", "Selisih"])
        self._tabel.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._tabel.verticalHeader().setVisible(False)
        self._tabel.setShowGrid(False)
        res_lay.addWidget(self._tabel)

        lay.addWidget(self._result_widget, 1)
        return widget

    def _on_mode_changed(self):
        self._combo_produk.setEnabled(self._radio_produk.isChecked())

    @Slot()
    def _run_prediksi(self):
        if not self.orders:
            QMessageBox.warning(self, "Data Kosong", "Data pesanan tidak tersedia."); return

        mode = "produk" if self._radio_produk.isChecked() else "semua"
        nama_produk = self._combo_produk.currentText()
        n_bulan     = self._spin_bulan.value()

        self._btn_prediksi.setEnabled(False)
        self._progress.setVisible(True)
        self._placeholder.setText("Sedang menghitung estimasi...\nMohon tunggu.")

        self._worker = PrediksiWorker(self.orders, mode, nama_produk, n_bulan)
        self._worker.finished.connect(self._on_prediksi_selesai)
        self._worker.error.connect(self._on_prediksi_error)
        self._worker.start()

    @Slot(object)
    def _on_prediksi_selesai(self, hasil: HarapanPrediksi):
        self._hasil = hasil
        self._progress.setVisible(False)
        self._btn_prediksi.setEnabled(True)
        self._placeholder.setVisible(False)
        self._result_widget.setVisible(True)

        self._canvas_linear.plot_hasil(hasil.linear, warna_pred="#3498db", judul=f"Proyeksi: {hasil.nama_target}")
        self._canvas_rf.plot_hasil(hasil.random_forest, warna_pred="#2ecc71", judul=f"Proyeksi Dinamis: {hasil.nama_target}")
        self._canvas_cmp.plot_perbandingan(hasil)

        self._txt_insight.setPlainText(hasil.pesan_insight)

        self._tabel.setRowCount(0)
        for i, lbl in enumerate(hasil.linear.bulan_labels):
            r = self._tabel.rowCount(); self._tabel.insertRow(r)
            lin_v = hasil.linear.nilai_prediksi[i]
            rf_v  = hasil.random_forest.nilai_prediksi[i]
            sel   = rf_v - lin_v
            
            vals = [lbl, _fmt_currency(lin_v), _fmt_currency(rf_v), f"{'+' if sel >= 0 else ''}{_fmt_currency(sel)}"]
            for c, v in enumerate(vals):
                item = QTableWidgetItem(v)
                item.setTextAlignment(Qt.AlignCenter)
                self._tabel.setItem(r, c, item)

    @Slot(str)
    def _on_prediksi_error(self, msg: str):
        self._progress.setVisible(False); self._btn_predict.setEnabled(True)
        QMessageBox.critical(self, "Gagal", f"Sistem gagal melakukan analisis: {msg}")