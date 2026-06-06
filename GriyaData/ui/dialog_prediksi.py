"""
ui/dialog_prediksi.py
─────────────────────────────────────────────────────────────────────────────
Dialog Prediksi Penjualan — GriyaData ML Feature
─────────────────────────────────────────────────────────────────────────────

Tampilan:
  ┌─────────────────────────────────────────────────────────────┐
  │ 🤖  Prediksi Penjualan (Machine Learning)                   │
  ├───────────────┬─────────────────────────────────────────────┤
  │ [Sidebar]     │  [Chart: historis + prediksi]               │
  │  Target       │                                             │
  │  ○ Semua      │  [Tab: Linear | Random Forest | Perbandingan]│
  │  ○ Per Produk │                                             │
  │               ├─────────────────────────────────────────────┤
  │  Produk: [v]  │  [Insight Box]                              │
  │               │                                             │
  │  Bulan: [3]   │  [Tabel: Bulan | Linear | RF | Selisih]     │
  │               │                                             │
  │  [🔮 Prediksi]│                                             │
  └───────────────┴─────────────────────────────────────────────┘
"""

import matplotlib
matplotlib.use("Agg")
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

# ── ML engine ────────────────────────────────────────────────────────────────
from ml.predictor import (
    predict_total_penjualan,
    predict_per_produk,
    daftar_produk_dari_orders,
    HarapanPrediksi,
)

# ── Formatter (reuse dari utils) ─────────────────────────────────────────────
try:
    from utils import Formatter
    _fmt_currency = Formatter.currency
except Exception:
    def _fmt_currency(v): return f"Rp {v:,.0f}"


# ─────────────────────────────────────────────────────────────────────────────
# Background worker thread
# ─────────────────────────────────────────────────────────────────────────────

class PrediksiWorker(QThread):
    finished = Signal(object)   # HarapanPrediksi
    error    = Signal(str)

    def __init__(self, orders, mode: str, nama_produk: str, n_bulan: int):
        super().__init__()
        self.orders      = orders
        self.mode        = mode          # "semua" | "produk"
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


# ─────────────────────────────────────────────────────────────────────────────
# Chart Canvas
# ─────────────────────────────────────────────────────────────────────────────

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

        # Garis historis
        ax.plot(
            range(n_hist),
            hist_values,
            color="#3b82f6", linewidth=2.5, marker="o", markersize=5,
            label="Historis", zorder=3,
        )
        ax.fill_between(range(n_hist), hist_values, alpha=0.12, color="#3b82f6")

        # Garis prediksi (sambung dari titik terakhir historis)
        pred_x = range(n_hist - 1, n_hist + len(pred_values))
        pred_y = [hist_values[-1]] + pred_values if hist_values else pred_values
        ax.plot(
            pred_x, pred_y,
            color=warna_pred, linewidth=2.5, linestyle="--",
            marker="s", markersize=6, label=f"Prediksi ({hasil.nama_model})", zorder=3,
        )
        ax.fill_between(pred_x, pred_y, alpha=0.10, color=warna_pred)

        # Garis pemisah historis/prediksi
        if n_hist > 0:
            ax.axvline(x=n_hist - 1, color="#94a3b8", linestyle=":", linewidth=1.5, alpha=0.7)
            ax.text(n_hist - 1 + 0.1, ax.get_ylim()[1] * 0.95 if ax.get_ylim()[1] > 0 else 1,
                    "← Historis | Prediksi →", fontsize=8, color="#64748b")

        # Anotasi nilai prediksi
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
        ax.set_title(judul or f"Prediksi Revenue — {hasil.nama_model}", fontsize=11, fontweight="bold", pad=10)
        ax.set_ylabel("Revenue (Rp)", fontsize=9)
        ax.legend(fontsize=9, loc="upper left")
        ax.grid(axis="y", linestyle="--", alpha=0.4)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        self.fig.tight_layout()
        self.draw()

    def plot_perbandingan(self, hasil: "HarapanPrediksi"):
        """Plot perbandingan Linear vs Random Forest side by side."""
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
                       label="Linear Regression", color="#3b82f6", alpha=0.85, zorder=3)
        bars2 = ax.bar([i + width/2 for i in x], rf_val, width,
                       label="Random Forest", color="#10b981", alpha=0.85, zorder=3)

        # Anotasi di atas bar
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
        ax.set_title("Perbandingan Prediksi: Linear Regression vs Random Forest",
                     fontsize=11, fontweight="bold", pad=10)
        ax.legend(fontsize=9)
        ax.grid(axis="y", linestyle="--", alpha=0.4)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        # Tandai rekomendasi
        rekomendasi = hasil.rekomendasi_model
        rek_color = "#3b82f6" if rekomendasi == "Linear Regression" else "#10b981"
        ax.set_xlabel(f"⭐ Model Rekomendasi: {rekomendasi}", fontsize=9,
                      color=rek_color, fontweight="bold")

        self.fig.tight_layout()
        self.draw()


# ─────────────────────────────────────────────────────────────────────────────
# Main Dialog
# ─────────────────────────────────────────────────────────────────────────────

class DialogPrediksi(QDialog):
    """
    Dialog utama fitur prediksi ML GriyaData.
    Dipanggil dari MainWindow dengan parameter orders (list OrderRecord).
    """

    def __init__(self, parent=None, orders: list = None):
        super().__init__(parent)
        self.orders  = orders or []
        self._hasil: HarapanPrediksi | None = None
        self._worker: PrediksiWorker | None = None

        self.setWindowTitle("🤖  Prediksi Penjualan — Machine Learning GriyaData")
        self.setMinimumSize(1100, 680)
        self.resize(1200, 720)
        self.setModal(True)

        self._daftar_produk = daftar_produk_dari_orders(self.orders)
        self._build_ui()

    # ─────────────────────────────────────────────────────────────────────────
    # Build UI
    # ─────────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        root.addWidget(self._make_header())

        # Body: sidebar + konten
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
                stop:0 #1e40af, stop:1 #065f46);
                border-bottom: 1px solid #1e3a5f; }
        """)
        lay = QHBoxLayout(hdr)
        lay.setContentsMargins(20, 14, 20, 14)

        ico = QLabel("🤖")
        ico.setStyleSheet("font-size: 26px;")
        lay.addWidget(ico)

        ttl = QLabel("Prediksi Penjualan — Machine Learning")
        ttl.setStyleSheet("font-size:17px;font-weight:700;color:#ffffff;margin-left:8px;")
        lay.addWidget(ttl)
        lay.addStretch()

        sub = QLabel("Linear Regression & Random Forest (scikit-learn)")
        sub.setStyleSheet("font-size:11px;color:#bfdbfe;")
        lay.addWidget(sub)
        return hdr

    def _make_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setFixedWidth(240)
        sidebar.setStyleSheet("""
            QFrame { background:#f1f5f9; border-right: 1px solid #e2e8f0; }
            QLabel { color: #374151; }
            QRadioButton { color: #374151; font-size: 13px; padding: 4px; }
            QComboBox, QSpinBox {
                border: 1px solid #cbd5e1; border-radius: 6px;
                padding: 5px 8px; background: white; color: #1e293b;
                font-size: 12px;
            }
            QPushButton#btnPrediksi {
                background: #1d4ed8; color: white; font-weight: 700;
                font-size: 14px; border-radius: 8px; padding: 10px;
                border: none;
            }
            QPushButton#btnPrediksi:hover { background: #1e40af; }
            QPushButton#btnPrediksi:disabled { background: #94a3b8; }
        """)

        lay = QVBoxLayout(sidebar)
        lay.setContentsMargins(16, 20, 16, 16)
        lay.setSpacing(14)

        # ── Target prediksi ──
        lbl_target = QLabel("🎯  Target Prediksi")
        lbl_target.setStyleSheet("font-weight:700;font-size:12px;color:#1e293b;")
        lay.addWidget(lbl_target)

        self._radio_semua  = QRadioButton("Semua Produk")
        self._radio_produk = QRadioButton("Per Produk")
        self._radio_semua.setChecked(True)
        self._radio_semua.toggled.connect(self._on_mode_changed)

        btn_group = QButtonGroup(self)
        btn_group.addButton(self._radio_semua)
        btn_group.addButton(self._radio_produk)

        lay.addWidget(self._radio_semua)
        lay.addWidget(self._radio_produk)

        # ── Pilih produk ──
        lbl_produk = QLabel("📦  Pilih Produk:")
        lbl_produk.setStyleSheet("font-size:11px;color:#64748b;")
        lay.addWidget(lbl_produk)

        self._combo_produk = QComboBox()
        self._combo_produk.addItems(self._daftar_produk or ["(belum ada data)"])
        self._combo_produk.setEnabled(False)
        lay.addWidget(self._combo_produk)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.HLine)
        sep1.setStyleSheet("color:#cbd5e1;")
        lay.addWidget(sep1)

        # ── Jumlah bulan ──
        lbl_bulan = QLabel("📅  Prediksi (bulan ke depan):")
        lbl_bulan.setStyleSheet("font-size:11px;color:#64748b;")
        lay.addWidget(lbl_bulan)

        self._spin_bulan = QSpinBox()
        self._spin_bulan.setRange(1, 12)
        self._spin_bulan.setValue(3)
        self._spin_bulan.setSuffix(" bulan")
        lay.addWidget(self._spin_bulan)

        lay.addStretch()

        # ── Progress bar ──
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        self._progress.setStyleSheet("""
            QProgressBar { border: none; border-radius: 4px; background: #e2e8f0; height: 6px; }
            QProgressBar::chunk { background: #3b82f6; border-radius: 4px; }
        """)
        lay.addWidget(self._progress)

        # ── Tombol prediksi ──
        self._btn_prediksi = QPushButton("🔮  Jalankan Prediksi")
        self._btn_prediksi.setObjectName("btnPrediksi")
        self._btn_prediksi.clicked.connect(self._run_prediksi)
        lay.addWidget(self._btn_prediksi)

        btn_tutup = QPushButton("Tutup")
        btn_tutup.setStyleSheet("""
            QPushButton { background:#e2e8f0;color:#374151;border-radius:6px;
                padding:7px; font-size:12px; border:none; }
            QPushButton:hover { background:#cbd5e1; }
        """)
        btn_tutup.clicked.connect(self.accept)
        lay.addWidget(btn_tutup)

        return sidebar

    def _make_content(self) -> QWidget:
        widget = QWidget()
        widget.setStyleSheet("background: #ffffff;")
        lay = QVBoxLayout(widget)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        # ── Placeholder saat belum ada hasil ──
        self._placeholder = QLabel(
            "👈  Pilih target prediksi dan klik  🔮 Jalankan Prediksi\n\n"
            "Sistem akan melatih model Machine Learning (Linear Regression & Random Forest)\n"
            "menggunakan data penjualan historis, lalu memproyeksikan revenue ke depan."
        )
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setStyleSheet(
            "color:#94a3b8;font-size:14px;line-height:1.8;"
            "border: 2px dashed #e2e8f0; border-radius:12px; padding:40px;"
        )
        lay.addWidget(self._placeholder)

        # ── Konten hasil (tersembunyi awalnya) ──
        self._result_widget = QWidget()
        self._result_widget.setVisible(False)
        res_lay = QVBoxLayout(self._result_widget)
        res_lay.setContentsMargins(0, 0, 0, 0)
        res_lay.setSpacing(10)

        # Tab chart
        self._tabs_chart = QTabWidget()
        self._tabs_chart.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #e2e8f0; border-radius: 8px; background: white; }
            QTabBar::tab { padding: 7px 18px; font-size: 12px; color: #64748b; background: #f8fafc;
                border: 1px solid #e2e8f0; border-bottom: none; border-radius: 4px 4px 0 0; }
            QTabBar::tab:selected { background: white; color: #1e293b; font-weight: 700; }
        """)

        # Tab 1: Linear
        tab_lin = QWidget()
        tl = QVBoxLayout(tab_lin)
        tl.setContentsMargins(4, 4, 4, 4)
        self._canvas_linear = PrediksiCanvas()
        tl.addWidget(self._canvas_linear)
        self._tabs_chart.addTab(tab_lin, "📈  Linear Regression")

        # Tab 2: Random Forest
        tab_rf = QWidget()
        tr = QVBoxLayout(tab_rf)
        tr.setContentsMargins(4, 4, 4, 4)
        self._canvas_rf = PrediksiCanvas()
        tr.addWidget(self._canvas_rf)
        self._tabs_chart.addTab(tab_rf, "🌳  Random Forest")

        # Tab 3: Perbandingan
        tab_cmp = QWidget()
        tc = QVBoxLayout(tab_cmp)
        tc.setContentsMargins(4, 4, 4, 4)
        self._canvas_cmp = PrediksiCanvas()
        tc.addWidget(self._canvas_cmp)
        self._tabs_chart.addTab(tab_cmp, "⚖️  Perbandingan Model")

        res_lay.addWidget(self._tabs_chart, 3)

        # ── Insight box ──
        self._txt_insight = QTextEdit()
        self._txt_insight.setReadOnly(True)
        self._txt_insight.setMaximumHeight(120)
        self._txt_insight.setStyleSheet("""
            QTextEdit {
                background: #f0fdf4; border: 1px solid #bbf7d0;
                border-radius: 8px; padding: 10px;
                font-family: 'Consolas', monospace; font-size: 11px;
                color: #14532d;
            }
        """)
        res_lay.addWidget(self._txt_insight)

        # ── Tabel angka prediksi ──
        lbl_tbl = QLabel("📋  Tabel Nilai Prediksi")
        lbl_tbl.setStyleSheet("font-weight:700;font-size:12px;color:#1e293b;")
        res_lay.addWidget(lbl_tbl)

        self._tabel = QTableWidget()
        self._tabel.setMaximumHeight(160)
        self._tabel.setColumnCount(4)
        self._tabel.setHorizontalHeaderLabels([
            "Bulan", "Linear Regression", "Random Forest", "Selisih"
        ])
        self._tabel.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._tabel.setAlternatingRowColors(True)
        self._tabel.setEditTriggers(QTableWidget.NoEditTriggers)
        self._tabel.setSelectionBehavior(QTableWidget.SelectRows)
        self._tabel.verticalHeader().setVisible(False)
        self._tabel.setShowGrid(False)
        self._tabel.setStyleSheet("""
            QTableWidget { border: 1px solid #e2e8f0; border-radius: 6px; font-size:11px; }
            QHeaderView::section { background:#f8fafc; font-weight:700; border:none;
                border-bottom: 1px solid #e2e8f0; padding: 6px; }
        """)
        res_lay.addWidget(self._tabel)

        lay.addWidget(self._result_widget, 1)
        return widget

    # ─────────────────────────────────────────────────────────────────────────
    # Slot & logic
    # ─────────────────────────────────────────────────────────────────────────

    def _on_mode_changed(self):
        is_produk = self._radio_produk.isChecked()
        self._combo_produk.setEnabled(is_produk)

    @Slot()
    def _run_prediksi(self):
        if not self.orders:
            QMessageBox.warning(self, "Data Kosong",
                                "Tidak ada data pesanan untuk dianalisis.\n"
                                "Pastikan data pesanan sudah dimuat dari API.")
            return

        mode = "produk" if self._radio_produk.isChecked() else "semua"
        nama_produk = self._combo_produk.currentText()
        n_bulan     = self._spin_bulan.value()

        if mode == "produk" and not nama_produk:
            QMessageBox.warning(self, "Produk Kosong", "Pilih produk terlebih dahulu.")
            return

        # Tampilkan loading
        self._btn_prediksi.setEnabled(False)
        self._progress.setVisible(True)
        self._placeholder.setVisible(True)
        self._result_widget.setVisible(False)
        self._placeholder.setText("⏳  Melatih model Machine Learning...\nMohon tunggu sebentar.")

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

        # Plot chart
        self._canvas_linear.plot_hasil(
            hasil.linear,
            warna_pred="#3b82f6",
            judul=f"Prediksi Revenue: {hasil.nama_target} — Linear Regression"
        )
        self._canvas_rf.plot_hasil(
            hasil.random_forest,
            warna_pred="#10b981",
            judul=f"Prediksi Revenue: {hasil.nama_target} — Random Forest"
        )
        self._canvas_cmp.plot_perbandingan(hasil)

        # Insight
        self._txt_insight.setPlainText(hasil.pesan_insight)

        # Tabel
        self._tabel.setRowCount(0)
        lin_vals = hasil.linear.nilai_prediksi
        rf_vals  = hasil.random_forest.nilai_prediksi
        labels   = hasil.linear.bulan_labels

        for i, lbl in enumerate(labels):
            r = self._tabel.rowCount()
            self._tabel.insertRow(r)

            lin_v = lin_vals[i] if i < len(lin_vals) else 0
            rf_v  = rf_vals[i]  if i < len(rf_vals)  else 0
            sel   = rf_v - lin_v

            items = [
                lbl,
                _fmt_currency(lin_v),
                _fmt_currency(rf_v),
                f"{'▲' if sel >= 0 else '▼'} {_fmt_currency(abs(sel))}",
            ]
            colors = [None, "#dbeafe", "#dcfce7",
                      "#dcfce7" if sel >= 0 else "#fee2e2"]

            for c, (val, bg) in enumerate(zip(items, colors)):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignCenter)
                if bg:
                    item.setBackground(QColor(bg))
                self._tabel.setItem(r, c, item)

        # Tandai model rekomendasi di tab
        rek = hasil.rekomendasi_model
        if rek == "Linear Regression":
            self._tabs_chart.setTabText(0, "📈  Linear Regression  ⭐")
            self._tabs_chart.setTabText(1, "🌳  Random Forest")
        else:
            self._tabs_chart.setTabText(0, "📈  Linear Regression")
            self._tabs_chart.setTabText(1, "🌳  Random Forest  ⭐")

    @Slot(str)
    def _on_prediksi_error(self, msg: str):
        self._progress.setVisible(False)
        self._btn_prediksi.setEnabled(True)
        self._placeholder.setVisible(True)
        self._placeholder.setText(f"❌  Gagal menjalankan prediksi:\n\n{msg}")
        QMessageBox.critical(self, "Error Prediksi ML", f"Terjadi kesalahan:\n\n{msg}")
