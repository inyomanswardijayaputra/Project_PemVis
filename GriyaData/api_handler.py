"""
api_handler.py
Menangani semua komunikasi dengan API FastAPI GriyaData.
Data diambil dari API (bukan SQLite lokal) agar sinkron dengan Supabase.
"""

import requests
from dataclasses import dataclass, field
from datetime import datetime

API_BASE = "https://griyadataapi-zv35m9ms.b4a.run"


@dataclass
class OrderRecord:
    id: int
    nama_pelanggan: str
    product_id: int
    jumlah: int
    total_harga: float
    tanggal_pesanan: str
    status_pesanan: str
    metode_pembayaran: str
    # Info produk (dari join lokal)
    nama_barang: str = ""
    kategori: str = ""
    harga_satuan: float = 0.0


@dataclass
class ProductRecord:
    id: int
    nama_barang: str
    kategori: str
    harga: float


class APIHandler:
    """Wrapper untuk memanggil REST API GriyaData."""

    def __init__(self, base_url: str = API_BASE):
        self.base = base_url.rstrip("/")
        self._products_cache: list[ProductRecord] = []

    # ─── Products ──────────────────────────────────────────────────────────────

    def get_products(self) -> list[ProductRecord]:
        """Ambil daftar produk dari API (dengan cache sederhana)."""
        try:
            r = requests.get(f"{self.base}/api/products", timeout=10)
            if r.status_code == 200:
                data = r.json().get("data", [])
                self._products_cache = [
                    ProductRecord(
                        id=p["id"],
                        nama_barang=p["nama_barang"],
                        kategori=p.get("kategori", "Lainnya"),
                        harga=float(p.get("harga", 0)),
                    )
                    for p in data
                ]
        except Exception:
            pass
        return self._products_cache

    def get_product_by_id(self, pid: int) -> ProductRecord | None:
        for p in self._products_cache:
            if p.id == pid:
                return p
        # refresh cache
        self.get_products()
        for p in self._products_cache:
            if p.id == pid:
                return p
        return None

    # ─── Orders ────────────────────────────────────────────────────────────────

    def get_all_orders(
        self,
        status: str = "All",
        metode: str = "All",
    ) -> list[OrderRecord]:
        try:
            r = requests.get(f"{self.base}/api/orders", timeout=10)
            if r.status_code != 200:
                return []
            raw = r.json().get("data", [])
        except Exception:
            return []

        # Pastikan cache produk terisi
        if not self._products_cache:
            self.get_products()

        product_map = {p.id: p for p in self._products_cache}

        orders: list[OrderRecord] = []
        for o in raw:
            prod = product_map.get(o.get("product_id", 0))
            rec = OrderRecord(
                id=o["id"],
                nama_pelanggan=o.get("nama_pelanggan", ""),
                product_id=o.get("product_id", 0),
                jumlah=o.get("jumlah", 0),
                total_harga=float(o.get("total_harga", 0)),
                tanggal_pesanan=o.get("tanggal_pesanan", "")[:10],
                status_pesanan=o.get("status_pesanan", "Pending"),
                metode_pembayaran=o.get("metode_pembayaran", ""),
                nama_barang=prod.nama_barang if prod else f"[ID {o.get('product_id')}]",
                kategori=prod.kategori if prod else "Lainnya",
                harga_satuan=prod.harga if prod else 0.0,
            )
            # Filter
            if status != "All" and rec.status_pesanan != status:
                continue
            if metode != "All" and rec.metode_pembayaran != metode:
                continue
            orders.append(rec)

        return orders

    def create_order(self, data: dict) -> dict:
        """POST /api/orders — data: {nama_pelanggan, product_id, jumlah, total_harga}"""
        r = requests.post(f"{self.base}/api/orders", json=data, timeout=10)
        r.raise_for_status()
        return r.json()

    def update_order_status(self, order_id: int, status: str) -> dict:
        """PUT /api/orders/{id}"""
        r = requests.put(
            f"{self.base}/api/orders/{order_id}",
            json={"status_pesanan": status},
            timeout=10,
        )
        r.raise_for_status()
        return r.json()

    def delete_order(self, order_id: int) -> dict:
        """DELETE /api/orders/{id}"""
        r = requests.delete(f"{self.base}/api/orders/{order_id}", timeout=10)
        r.raise_for_status()
        return r.json()

    # ─── Aggregasi untuk Chart & Stats ─────────────────────────────────────────

    def summary_stats(self, orders: list[OrderRecord] | None = None) -> dict:
        if orders is None:
            orders = self.get_all_orders()
        total_tx = len(orders)
        total_rev = sum(o.total_harga for o in orders)
        avg_rev = total_rev / total_tx if total_tx else 0
        total_units = sum(o.jumlah for o in orders)
        return {
            "total_tx": total_tx,
            "total_rev": total_rev,
            "avg_rev": avg_rev,
            "total_units": total_units,
        }

    def revenue_by_kategori(self, orders: list[OrderRecord]) -> dict[str, float]:
        result: dict[str, float] = {}
        for o in orders:
            result[o.kategori] = result.get(o.kategori, 0) + o.total_harga
        return dict(sorted(result.items(), key=lambda x: x[1], reverse=True))

    def revenue_by_status(self, orders: list[OrderRecord]) -> dict[str, float]:
        result: dict[str, float] = {}
        for o in orders:
            result[o.status_pesanan] = result.get(o.status_pesanan, 0) + o.total_harga
        return dict(sorted(result.items(), key=lambda x: x[1], reverse=True))

    def revenue_by_month(self, orders: list[OrderRecord]) -> dict[str, float]:
        result: dict[str, float] = {}
        for o in orders:
            month = o.tanggal_pesanan[:7] if len(o.tanggal_pesanan) >= 7 else "?"
            result[month] = result.get(month, 0) + o.total_harga
        return dict(sorted(result.items()))

    def units_by_payment(self, orders: list[OrderRecord]) -> dict[str, int]:
        result: dict[str, int] = {}
        for o in orders:
            result[o.metode_pembayaran] = result.get(o.metode_pembayaran, 0) + o.jumlah
        return dict(sorted(result.items(), key=lambda x: x[1], reverse=True))

    def top_products(self, orders: list[OrderRecord], n: int = 10) -> dict[str, float]:
        result: dict[str, float] = {}
        for o in orders:
            result[o.nama_barang] = result.get(o.nama_barang, 0) + o.total_harga
        sorted_items = sorted(result.items(), key=lambda x: x[1], reverse=True)
        return dict(sorted_items[:n])
