import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QComboBox, QLabel, QFileDialog, QFrame, QMessageBox,
)
from PySide6.QtCore import Qt

from utils import CHART_TYPES

PALETTE = ["#3b82f6", "#10b981", "#f59e0b", "#8b5cf6",
           "#ec4899", "#ef4444", "#06b6d4", "#84cc16"]


class ChartCanvas(FigureCanvas):
    def __init__(self, parent=None):
        self.fig = Figure(figsize=(8, 4.5), facecolor="#ffffff")
        super().__init__(self.fig)
        self.setParent(parent)

    def clear(self):
        self.fig.clear()
        self.draw()


class ChartWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("chartWidget")
        self._data: dict = {}
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        hdr = QFrame()
        hdr.setObjectName("panelHeader")
        h_lay = QHBoxLayout(hdr)
        h_lay.setContentsMargins(16, 10, 16, 10)
        h_lay.setSpacing(10)

        lbl = QLabel("Visualisasi Data")
        lbl.setObjectName("panelTitle")
        h_lay.addWidget(lbl)
        h_lay.addStretch()

        lbl_type = QLabel("Jenis Chart:")
        lbl_type.setObjectName("panelSubinfo")
        h_lay.addWidget(lbl_type)

        self.combo_chart = QComboBox()
        self.combo_chart.setObjectName("inputField")
        self.combo_chart.setMinimumWidth(280)
        self.combo_chart.addItems(CHART_TYPES)
        self.combo_chart.currentIndexChanged.connect(self.refresh)
        h_lay.addWidget(self.combo_chart)

        btn_export = QPushButton("Export PNG")
        btn_export.setObjectName("btnSecondary")
        btn_export.setFixedHeight(38)
        btn_export.clicked.connect(self._export_png)
        h_lay.addWidget(btn_export)

        root.addWidget(hdr)

        self.canvas = ChartCanvas(self)
        root.addWidget(self.canvas, 1)

    def set_data(self, agg_data: dict):
        self._data = agg_data
        self.refresh()

    def refresh(self):
        idx = self.combo_chart.currentIndex()
        self.canvas.fig.clear()
        ax = self.canvas.fig.add_subplot(111)
        ax.set_facecolor("#f9fafb")
        self.canvas.fig.patch.set_facecolor("#ffffff")

        chart_map = {
            0: self._draw_bar_kategori,
            1: self._draw_pie_status,
            2: self._draw_line_monthly,
            3: self._draw_bar_payment,
            4: self._draw_hbar_products,
        }
        draw_fn = chart_map.get(idx)
        if draw_fn and self._data:
            draw_fn(ax)

        self.canvas.fig.tight_layout(pad=2)
        self.canvas.draw()

    def _draw_bar_kategori(self, ax):
        data = self._data.get("revenue_by_kategori", {})
        if not data:
            ax.text(0.5, 0.5, "Belum ada data", ha="center", va="center",
                    transform=ax.transAxes, color="#9ca3af")
            return
        labels = list(data.keys())
        values = [data[k] / 1_000_000 for k in labels]
        colors = PALETTE[:len(labels)]

        bars = ax.bar(labels, values, color=colors, edgecolor="white",
                      linewidth=1.5, zorder=3)
        ax.set_title("Total Revenue per Kategori Produk", fontsize=13,
                     fontweight="bold", color="#1a1a1a", pad=12)
        ax.set_ylabel("Revenue (Juta Rp)", fontsize=10, color="#6b7280")
        ax.set_xlabel("Kategori", fontsize=10, color="#6b7280")
        ax.tick_params(colors="#6b7280", labelsize=8)
        ax.yaxis.grid(True, linestyle="--", alpha=0.5, color="#e5e7eb", zorder=0)
        ax.set_axisbelow(True)
        for spine in ax.spines.values():
            spine.set_edgecolor("#e5e7eb")
        for bar, val in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02,
                    f"Rp{val:.1f}Jt", ha="center", va="bottom",
                    fontsize=8, color="#374151", fontweight="600")

    def _draw_pie_status(self, ax):
        data = self._data.get("revenue_by_status", {})
        if not data:
            ax.text(0.5, 0.5, "Belum ada data", ha="center", va="center",
                    transform=ax.transAxes, color="#9ca3af")
            return
        labels = list(data.keys())
        values = list(data.values())
        colors = PALETTE[:len(labels)]
        explode = [0.03] * len(labels)

        wedges, texts, autotexts = ax.pie(
            values, labels=labels, colors=colors, explode=explode,
            autopct="%1.1f%%", startangle=140,
            textprops={"fontsize": 10, "color": "#374151"},
            wedgeprops={"edgecolor": "white", "linewidth": 2},
        )
        for at in autotexts:
            at.set_fontsize(9)
            at.set_fontweight("bold")
            at.set_color("white")
        ax.set_title("Distribusi Revenue per Status Pesanan", fontsize=13,
                     fontweight="bold", color="#1a1a1a", pad=12)

    def _draw_line_monthly(self, ax):
        data = self._data.get("revenue_by_month", {})
        if not data:
            ax.text(0.5, 0.5, "Belum ada data", ha="center", va="center",
                    transform=ax.transAxes, color="#9ca3af")
            return
        months = list(data.keys())
        values = [data[m] / 1_000_000 for m in months]

        ax.plot(months, values, color="#3b82f6", linewidth=2.5,
                marker="o", markersize=6, markerfacecolor="#ffffff",
                markeredgecolor="#3b82f6", markeredgewidth=2, zorder=3)
        ax.fill_between(months, values, alpha=0.1, color="#3b82f6")
        ax.set_title("Trend Pesanan per Bulan", fontsize=13,
                     fontweight="bold", color="#1a1a1a", pad=12)
        ax.set_ylabel("Revenue (Juta Rp)", fontsize=10, color="#6b7280")
        ax.set_xlabel("Bulan", fontsize=10, color="#6b7280")
        ax.tick_params(axis="x", rotation=45, colors="#6b7280", labelsize=8)
        ax.tick_params(axis="y", colors="#6b7280", labelsize=9)
        ax.yaxis.grid(True, linestyle="--", alpha=0.5, color="#e5e7eb", zorder=0)
        ax.set_axisbelow(True)
        for spine in ax.spines.values():
            spine.set_edgecolor("#e5e7eb")

    def _draw_bar_payment(self, ax):
        data = self._data.get("units_by_payment", {})
        if not data:
            ax.text(0.5, 0.5, "Belum ada data", ha="center", va="center",
                    transform=ax.transAxes, color="#9ca3af")
            return
        labels = list(data.keys())
        values = list(data.values())
        colors = PALETTE[:len(labels)]

        bars = ax.bar(labels, values, color=colors, edgecolor="white",
                      linewidth=1.5, zorder=3)
        ax.set_title("Total Unit Terjual per Metode Pembayaran", fontsize=13,
                     fontweight="bold", color="#1a1a1a", pad=12)
        ax.set_ylabel("Unit Terjual", fontsize=10, color="#6b7280")
        ax.tick_params(colors="#6b7280", labelsize=9)
        ax.yaxis.grid(True, linestyle="--", alpha=0.5, color="#e5e7eb", zorder=0)
        ax.set_axisbelow(True)
        for spine in ax.spines.values():
            spine.set_edgecolor("#e5e7eb")
        for bar, val in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                    str(val), ha="center", va="bottom",
                    fontsize=9, color="#374151", fontweight="600")

    def _draw_hbar_products(self, ax):
        data = self._data.get("top_products", {})
        if not data:
            ax.text(0.5, 0.5, "Belum ada data", ha="center", va="center",
                    transform=ax.transAxes, color="#9ca3af")
            return
        labels = list(data.keys())[::-1]
        values = [data[k] / 1_000_000 for k in list(data.keys())[::-1]]

        bars = ax.barh(labels, values, color="#3b82f6", edgecolor="white",
                       linewidth=1, zorder=3)
        ax.set_title("Top 10 Produk Miniatur by Revenue", fontsize=13,
                     fontweight="bold", color="#1a1a1a", pad=12)
        ax.set_xlabel("Revenue (Juta Rp)", fontsize=10, color="#6b7280")
        ax.tick_params(colors="#6b7280", labelsize=8)
        ax.xaxis.grid(True, linestyle="--", alpha=0.5, color="#e5e7eb", zorder=0)
        ax.set_axisbelow(True)
        for spine in ax.spines.values():
            spine.set_edgecolor("#e5e7eb")
        for bar, val in zip(bars, values):
            ax.text(val + 0.02, bar.get_y() + bar.get_height() / 2,
                    f"Rp{val:.1f}Jt", va="center", fontsize=8,
                    color="#374151", fontweight="600")

    def _export_png(self):
        chart_name = self.combo_chart.currentText()
        safe_name = chart_name.replace(" ", "_").replace("(", "").replace(")", "").replace("/", "-")
        path, _ = QFileDialog.getSaveFileName(
            self, "Simpan Chart sebagai PNG",
            f"{safe_name}.png",
            "PNG Images (*.png)",
        )
        if not path:
            return
        try:
            self.canvas.fig.savefig(path, dpi=150, bbox_inches="tight",
                                    facecolor="#ffffff")
            QMessageBox.information(self, "Export Berhasil",
                                    f"Chart berhasil disimpan:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Gagal", str(e))
