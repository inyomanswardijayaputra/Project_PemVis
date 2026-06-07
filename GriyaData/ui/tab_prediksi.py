import matplotlib
matplotlib.use("Agg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
    QPushButton, QLabel, QFrame, QComboBox, QSpinBox,
    QProgressBar, QSizePolicy, QMessageBox,
    QTableWidget, QTableWidgetItem, QHeaderView,
)
from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtGui import QColor


# Worker
class PredictWorker(QThread):
    finished = Signal(object)
    error    = Signal(str)

    def __init__(self, predictor, mode, product_name, horizon, n_periods):
        super().__init__()
        self.predictor    = predictor
        self.mode         = mode
        self.product_name = product_name
        self.horizon      = horizon
        self.n_periods    = n_periods

    def run(self):
        try:
            if self.mode == "all":
                report = self.predictor.forecast_all(self.horizon, self.n_periods)
            else:
                report = self.predictor.forecast_product(
                    self.product_name, self.horizon, self.n_periods)
            self.finished.emit(report)
        except Exception as e:
            self.error.emit(str(e))


# Chart Canvas
class ForecastCanvas(FigureCanvas):
    def __init__(self):
        self.fig = Figure(facecolor="#ffffff")
        super().__init__(self.fig)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def plot_forecast(self, report):
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        ax.set_facecolor("#ffffff")
        self.fig.patch.set_facecolor("#ffffff")

        hist  = report.historical_df
        preds = report.predictions

        if hist.empty or not preds:
            ax.text(0.5, 0.5, "Tidak ada data untuk ditampilkan",
                    ha="center", va="center", fontsize=12, color="#9ca3af")
            self.draw(); return

        h_labels = [str(p)[:10] for p in hist["period"]]
        h_units  = hist["units"].tolist()
        h_x      = list(range(len(h_labels)))

        ax.plot(h_x, h_units, color="#3b82f6", lw=2.2, marker="o",
                markersize=5, label="Historis", zorder=3)
        ax.fill_between(h_x, h_units, alpha=0.07, color="#3b82f6")

        p_labels = [p.label for p in preds]
        p_units  = [p.predicted_units for p in preds]
        p_lower  = [p.lower_bound for p in preds]
        p_upper  = [p.upper_bound for p in preds]
        start    = len(h_x) - 1
        p_x      = list(range(start, start + len(p_labels) + 1))

        ax.plot(p_x, [h_units[-1]] + p_units, color="#10b981", lw=2.5,
                marker="D", markersize=6, ls="--", label="Prediksi", zorder=4)
        ax.fill_between(p_x,
                        [h_units[-1]] + p_lower,
                        [h_units[-1]] + p_upper,
                        alpha=0.14, color="#10b981", label="Confidence ±15%")
        ax.axvline(x=start, color="#d1d5db", ls=":", lw=1.5)

        for xi, val in zip(p_x[1:], p_units):
            ax.annotate(f"{val:.0f}", xy=(xi, val), xytext=(0, 10),
                        textcoords="offset points", ha="center",
                        fontsize=8, color="#065f46", fontweight="bold")

        all_lbl = h_labels + p_labels
        all_x   = list(range(len(all_lbl)))
        step    = max(1, len(all_lbl) // 10)
        ax.set_xticks(all_x[::step])
        ax.set_xticklabels(all_lbl[::step], rotation=30, ha="right", fontsize=7.5)
        ax.set_ylabel("Unit Terjual", fontsize=9)
        ax.set_title(
            f"Prediksi — {report.product_name}  "
            f"({'Mingguan' if report.horizon=='weekly' else 'Bulanan'})",
            fontsize=11, fontweight="bold", pad=8)
        ax.legend(fontsize=8, loc="upper left", framealpha=0.9)
        ax.spines[["top", "right"]].set_visible(False)
        self.fig.tight_layout(pad=1.5)
        self.draw()


# Metric Card
def _metric_card(title, value, sub, color):
    card = QFrame()
    card.setStyleSheet(f"""
        QFrame {{
            background: #fff;
            border: 1px solid #e5e7eb;
            border-left: 4px solid {color};
            border-radius: 8px;
        }}
        QLabel {{ border: none; }}
    """)
    lay = QVBoxLayout(card)
    lay.setContentsMargins(14, 10, 14, 10)
    lay.setSpacing(2)
    lv = QLabel(value); lv.setObjectName("__mv")
    lv.setStyleSheet(f"font-size:20px;font-weight:700;color:{color};")
    lt = QLabel(title)
    lt.setStyleSheet("font-size:11px;color:#4b5563;font-weight:600;")
    ls = QLabel(sub); ls.setObjectName("__ms")
    ls.setStyleSheet("font-size:10px;color:#9ca3af;")
    lay.addWidget(lv); lay.addWidget(lt); lay.addWidget(ls)
    return card


# Tab Utama
class TabPrediksi(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("tabPrediksi")
        self._predictor = None
        self._worker    = None
        self._build_ui()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setStyleSheet("QScrollArea { background-color: transparent; }")

        content_widget = QWidget()
        root = QVBoxLayout(content_widget)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(12)

        # Header
        hdr = QFrame()
        hdr.setStyleSheet("""QFrame{
            background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 #1e3a5f,stop:1 #0f766e);
            border-radius:10px;}""")
        hdr.setFixedHeight(56)
        hl = QHBoxLayout(hdr); hl.setContentsMargins(18, 0, 18, 0)
        rv = QVBoxLayout(); rv.setSpacing(1); rv.setAlignment(Qt.AlignVCenter)
        t1 = QLabel("Prediksi Penjualan — Random Forest ML")
        t1.setStyleSheet("font-size:14px;font-weight:700;color:#fff;")
        t2 = QLabel("Forecast unit & revenue per produk / semua produk")
        t2.setStyleSheet("font-size:10px;color:#94d3c8;")
        rv.addWidget(t1); rv.addWidget(t2)
        hl.addLayout(rv); hl.addStretch()
        badge = QLabel("PROYEKSI AKTIF")
        badge.setStyleSheet("""background:#10b981;color:#fff;font-size:10px;
            font-weight:700;padding:3px 10px;border-radius:12px;""")
        hl.addWidget(badge)
        root.addWidget(hdr)

        # Kontrol
        cl = QHBoxLayout(); cl.setContentsMargins(4, 0, 4, 0); cl.setSpacing(12)

        cl.addWidget(QLabel("Mode:"))
        self.combo_mode = QComboBox(); self.combo_mode.setObjectName("inputField")
        self.combo_mode.addItems(["Semua Produk", "Per Produk"])
        self.combo_mode.setMinimumWidth(150)
        self.combo_mode.currentIndexChanged.connect(self._on_mode_changed)
        cl.addWidget(self.combo_mode)

        self.lbl_prod   = QLabel("Produk:")
        self.combo_produk = QComboBox(); self.combo_produk.setObjectName("inputField")
        self.combo_produk.setMinimumWidth(200)
        self.lbl_prod.setVisible(False); self.combo_produk.setVisible(False)
        cl.addWidget(self.lbl_prod); cl.addWidget(self.combo_produk)

        cl.addWidget(QLabel("Horizon:"))
        self.combo_horizon = QComboBox(); self.combo_horizon.setObjectName("inputField")
        self.combo_horizon.addItems(["Bulanan", "Mingguan"])
        self.combo_horizon.setMinimumWidth(120)
        cl.addWidget(self.combo_horizon)

        cl.addWidget(QLabel("Periode:"))
        self.spin_periods = QSpinBox(); self.spin_periods.setObjectName("inputField")
        self.spin_periods.setButtonSymbols(QSpinBox.PlusMinus)
        self.spin_periods.setRange(1, 6); self.spin_periods.setValue(3)
        self.spin_periods.setSuffix(" periode"); self.spin_periods.setMinimumWidth(100)
        cl.addWidget(self.spin_periods)

        cl.addStretch()
        self.btn_predict = QPushButton("Jalankan Prediksi")
        self.btn_predict.setObjectName("btnPrimary")
        self.btn_predict.setMinimumWidth(160)
        self.btn_predict.clicked.connect(self._run_prediction)
        cl.addWidget(self.btn_predict)
        
        root.addLayout(cl)

        self.metrics_wrap = QWidget()
        ml = QHBoxLayout(self.metrics_wrap)
        ml.setContentsMargins(0, 0, 0, 0); ml.setSpacing(8)
        self._c_r2   = _metric_card("R² Score",  "—", "Akurasi model",       "#3b82f6")
        self._c_mae  = _metric_card("MAE",        "—", "Mean Absolute Error", "#f59e0b")
        self._c_rmse = _metric_card("RMSE",       "—", "Root Mean Sq Err",    "#8b5cf6")
        self._c_acc  = _metric_card("Kualitas",   "—", "Evaluasi model RF",   "#10b981")
        for c in (self._c_r2, self._c_mae, self._c_rmse, self._c_acc):
            c.setMinimumHeight(70)
            ml.addWidget(c)
        root.addWidget(self.metrics_wrap)
        self.metrics_wrap.setVisible(False) 

        # Chart
        self.chart_wrap = QWidget()
        cw_lay = QVBoxLayout(self.chart_wrap)
        cw_lay.setContentsMargins(0, 0, 0, 0)
        self._canvas = ForecastCanvas()
        self._canvas.setMinimumHeight(450) 
        cw_lay.addWidget(self._canvas)
        root.addWidget(self.chart_wrap)
        self.chart_wrap.setVisible(False) 

        # Tabel
        self.tbl_wrap = QWidget()
        tw_lay = QVBoxLayout(self.tbl_wrap)
        tw_lay.setContentsMargins(0, 16, 0, 0); tw_lay.setSpacing(8)
        lbl_t = QLabel("Hasil Prediksi")
        lbl_t.setStyleSheet("font-size:14px;font-weight:700;color:#374151;")
        tw_lay.addWidget(lbl_t)
        
        self.tbl_result = QTableWidget()
        self.tbl_result.setObjectName("dataTable")
        self.tbl_result.setColumnCount(5)
        self.tbl_result.setHorizontalHeaderLabels([
            "Periode", "Prediksi Unit", "Confidence Range",
            "Prediksi Revenue (Rp)", "±"
        ])
        
        self.tbl_result.setStyleSheet("""
            QTableWidget { border: 1px solid #d1d5db; border-radius: 4px; background-color: #ffffff; }
            QHeaderView::section { background-color: #f3f4f6; font-weight: bold; color: #374151; padding: 6px; border: none; border-bottom: 1px solid #d1d5db; }
            QTableWidget::item:selected { background-color: #3b82f6; color: white; }
        """)
        
        self.tbl_result.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_result.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl_result.setAlternatingRowColors(True)
        self.tbl_result.setSelectionBehavior(QTableWidget.SelectRows)
        self.tbl_result.verticalHeader().setVisible(False)
        self.tbl_result.setShowGrid(False)
        
        self.tbl_result.setMinimumHeight(140)
        self.tbl_result.setMaximumHeight(165) 

        tw_lay.addWidget(self.tbl_result)
        root.addWidget(self.tbl_wrap)
        self.tbl_wrap.setVisible(False) 

        root.addStretch()

        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)

        # Status bar
        sb = QFrame()
        sb.setFixedHeight(28)
        sb.setStyleSheet("background:#f1f5f9;border-radius:5px;")
        sl = QHBoxLayout(sb); sl.setContentsMargins(12, 0, 12, 0)
        self.lbl_status = QLabel("  Siap. Pilih mode & klik Jalankan Prediksi.")
        self.lbl_status.setStyleSheet("font-size:10px;color:#6b7280;")
        sl.addWidget(self.lbl_status); sl.addStretch()
        self.progress = QProgressBar()
        self.progress.setRange(0, 0); self.progress.setVisible(False)
        self.progress.setMaximumWidth(120); self.progress.setMaximumHeight(12)
        sl.addWidget(self.progress)
        
        main_layout.addWidget(sb)

    # Data 
    def load_orders(self, orders: list):
        try:
            from ml.predictor import SalesPredictor
        except ImportError:
            from ml.predictor import SalesPredictor
        self._predictor = SalesPredictor(orders)
        prods = self._predictor.get_product_list()
        self.combo_produk.clear()
        self.combo_produk.addItems(prods)
        self.lbl_status.setText(f"{len(orders)} pesanan dimuat. Model siap dilatih.")

    # Slots 
    @Slot(int)
    def _on_mode_changed(self, idx):
        show = (idx == 1)
        self.lbl_prod.setVisible(show)
        self.combo_produk.setVisible(show)

    @Slot()
    def _run_prediction(self):
        if self._predictor is None:
            QMessageBox.warning(self, "Belum Ada Data",
                                "Data pesanan belum dimuat. Refresh data dulu."); return
        mode    = "all" if self.combo_mode.currentIndex() == 0 else "product"
        product = self.combo_produk.currentText()
        horizon = "weekly" if self.combo_horizon.currentIndex() == 1 else "monthly"
        n       = self.spin_periods.value()
        if mode == "product" and not product:
            QMessageBox.warning(self, "Pilih Produk", "Pilih produk dulu."); return

        self.btn_predict.setEnabled(False)
        self.progress.setVisible(True)
        self.lbl_status.setText("Melatih model Random Forest...")
        self._worker = PredictWorker(self._predictor, mode, product, horizon, n)
        self._worker.finished.connect(self._on_done)
        self._worker.error.connect(self._on_err)
        self._worker.start()

    @Slot(object)
    def _on_done(self, report):
        self.btn_predict.setEnabled(True)
        self.progress.setVisible(False)
        if not report.has_enough_data:
            QMessageBox.information(self, "Data Kurang", report.warning_msg)
            self.lbl_status.setText(f"  {report.warning_msg}"); return
            
        self.metrics_wrap.setVisible(True)
        self.chart_wrap.setVisible(True)
        self.tbl_wrap.setVisible(True)

        self._update_metrics(report.metrics)
        self._update_table(report.predictions)
        self._canvas.plot_forecast(report)
        h = "Mingguan" if report.horizon == "weekly" else "Bulanan"
        self.lbl_status.setText(
            f"{report.product_name}  |  {h}  |  {report.n_periods} periode  |  "
            f"R²={report.metrics.r2:.3f}  |  Train:{report.metrics.n_train} periode")

    @Slot(str)
    def _on_err(self, msg):
        self.btn_predict.setEnabled(True)
        self.progress.setVisible(False)
        self.lbl_status.setText(f"{msg}")
        QMessageBox.critical(self, "Prediksi Gagal", msg)

    #Updaters 
    def _update_metrics(self, m):
        def _s(card, val, sub=None):
            lbl = card.findChild(QLabel, "__mv")
            if lbl: lbl.setText(val)
            if sub:
                ls = card.findChild(QLabel, "__ms")
                if ls: ls.setText(sub)

        _s(self._c_r2,   f"{m.r2:.3f}", f"Train:{m.n_train}  Test:{m.n_test}")
        _s(self._c_mae,  f"{m.mae:.1f}", "unit")
        _s(self._c_rmse, f"{m.rmse:.1f}", "unit")
        _s(self._c_acc,  m.accuracy_label, "Evaluasi RF")

        c = "#10b981" if m.r2 >= 0.7 else "#f59e0b" if m.r2 >= 0.5 else "#ef4444"
        lv = self._c_r2.findChild(QLabel, "__mv")
        if lv: lv.setStyleSheet(f"font-size:20px;font-weight:700;color:{c}; border: none;")

    def _update_table(self, predictions):
        self.tbl_result.setRowCount(0)
        for p in predictions:
            r = self.tbl_result.rowCount()
            self.tbl_result.insertRow(r)
            vals = [
                p.label,
                f"{p.predicted_units:.0f} unit",
                f"{p.lower_bound:.0f} – {p.upper_bound:.0f} unit",
                f"Rp {p.predicted_revenue:,.0f}",
                f"±{((p.upper_bound - p.lower_bound) / 2):.0f}",
            ]
            for c, v in enumerate(vals):
                item = QTableWidgetItem(v)
                item.setTextAlignment(Qt.AlignCenter)
                self.tbl_result.setItem(r, c, item)