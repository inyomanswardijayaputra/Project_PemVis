from __future__ import annotations
from dataclasses import dataclass

# Konstanta Data 
KATEGORI_PRODUK = [
    "Gundam / Mecha",
    "Action Figure",
    "Scale Model",
    "Diecast",
    "Gacha / Blind Box",
    "Lainnya",
]

STATUS_PESANAN = [
    "Pending",
    "Diproses",
    "Dikirim",
    "Selesai",
    "Dibatalkan",
]

METODE_PEMBAYARAN = [
    "Offline/COD",
    "Transfer Bank",
    "QRIS",
    "OVO",
    "GoPay",
    "ShopeePay",
]

CHART_TYPES = [
    "Revenue by Kategori (Bar)",
    "Revenue by Status Pesanan (Pie)",
    "Trend Pesanan per Bulan (Line)",
    "Unit by Metode Pembayaran (Bar)",
    "Top 10 Produk (Horizontal Bar)",
]

STATUS_COLORS = {
    "Gundam / Mecha":   "#3b82f6",
    "Action Figure":    "#10b981",
    "Scale Model":      "#f59e0b",
    "Diecast":          "#8b5cf6",
    "Gacha / Blind Box":"#ec4899",
    "Lainnya":          "#6b7280",
}


# Validation
@dataclass
class ValidationResult:
    valid: bool
    errors: list[str]

    def error_text(self) -> str:
        return "\n".join(self.errors)


class OrderValidator:

    @staticmethod
    def validate(data: dict) -> ValidationResult:
        errors = []

        if not data.get("nama_pelanggan", "").strip():
            errors.append("• Nama Pelanggan wajib diisi.")

        try:
            pid = int(data.get("product_id", 0))
            if pid <= 0:
                errors.append("• Produk wajib dipilih.")
        except (ValueError, TypeError):
            errors.append("• Product ID tidak valid.")

        try:
            jumlah = int(data.get("jumlah", 0))
            if jumlah <= 0:
                errors.append("• Jumlah harus lebih dari 0.")
        except (ValueError, TypeError):
            errors.append("• Jumlah harus berupa angka bulat.")

        try:
            harga = float(data.get("total_harga", 0))
            if harga < 0:
                errors.append("• Total harga tidak boleh negatif.")
        except (ValueError, TypeError):
            errors.append("• Total harga harus berupa angka.")

        if not data.get("status_pesanan", "").strip():
            errors.append("• Status pesanan wajib dipilih.")

        if not data.get("metode_pembayaran", "").strip():
            errors.append("• Metode pembayaran wajib dipilih.")

        return ValidationResult(valid=len(errors) == 0, errors=errors)

    @staticmethod
    def calc_total(jumlah: int, harga_satuan: float) -> float:
        return round(jumlah * harga_satuan, 2)


# Formatter
class Formatter:

    @staticmethod
    def currency(value: float) -> str:
        return f"Rp {value:,.0f}"

    @staticmethod
    def number(value: int | float) -> str:
        return f"{int(value):,}"

    @staticmethod
    def short_currency(value: float) -> str:
        if value >= 1_000_000_000:
            return f"Rp {value / 1_000_000_000:.1f}M"
        if value >= 1_000_000:
            return f"Rp {value / 1_000_000:.1f}Jt"
        if value >= 1_000:
            return f"Rp {value / 1_000:.1f}K"
        return f"Rp {value:.0f}"
