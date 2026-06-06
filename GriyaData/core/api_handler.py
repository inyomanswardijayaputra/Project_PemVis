"""
core/api_handler.py
Komunikasi dengan REST API GriyaData — schema baru (20 kolom).
"""

import requests
from dataclasses import dataclass, field

API_BASE = "https://griyadata-backend-production.up.railway.app"


@dataclass
class ProductRecord:
    id:           int
    product_name: str
    category:     str
    price:        float


@dataclass
class OrderRecord:
    # ── dari tabel orders ──────────────────────────────────────────────────
    id:                      int
    order_id:                str
    customer_name:           str
    product_id:              int
    quantity:                int
    discount:                float
    total:                   float
    shipping_fee:            float
    total_sales:             float
    status:                  str
    shipping_address:        str
    customer_gender:         str
    customer_city:           str
    payment_method:          str
    courier:                 str
    estimated_delivery_days: int
    sales_channel:           str
    customer_rating:         float
    sales_date:              str
    # ── dari join products ─────────────────────────────────────────────────
    product_name: str = ""
    category:     str = ""
    price:        float = 0.0

    # ── backward-compat aliases (dipakai ml/predictor.py) ──────────────────
    @property
    def nama_barang(self):       return self.product_name
    @property
    def kategori(self):          return self.category
    @property
    def jumlah(self):            return self.quantity
    @property
    def total_harga(self):       return self.total_sales
    @property
    def tanggal_pesanan(self):   return self.sales_date
    @property
    def status_pesanan(self):    return self.status
    @property
    def metode_pembayaran(self): return self.payment_method


class APIHandler:
    def __init__(self, base_url: str = API_BASE):
        self.base = base_url.rstrip("/")
        self._products_cache: list[ProductRecord] = []

    # ── Products ──────────────────────────────────────────────────────────────

    def get_products(self) -> list[ProductRecord]:
        try:
            r = requests.get(f"{self.base}/api/products", timeout=10)
            if r.status_code == 200:
                self._products_cache = [
                    ProductRecord(
                        id=p["id"],
                        product_name=p["product_name"],
                        category=p.get("category", "Lainnya"),
                        price=float(p.get("price", 0)),
                    )
                    for p in r.json().get("data", [])
                ]
        except Exception:
            pass
        return self._products_cache

    def create_product(self, data: dict) -> dict:
        """data: {product_name, category, price}"""
        r = requests.post(f"{self.base}/api/products", json=data, timeout=10)
        r.raise_for_status()
        self._products_cache = []    # invalidate cache
        return r.json()

    def update_product(self, pid: int, data: dict) -> dict:
        r = requests.put(f"{self.base}/api/products/{pid}", json=data, timeout=10)
        r.raise_for_status()
        self._products_cache = []
        return r.json()

    def delete_product(self, pid: int) -> dict:
        r = requests.delete(f"{self.base}/api/products/{pid}", timeout=10)
        r.raise_for_status()
        self._products_cache = []
        return r.json()

    # ── Orders ────────────────────────────────────────────────────────────────

    def get_all_orders(self, status: str = "All",
                       channel: str = "All") -> list[OrderRecord]:
        try:
            r = requests.get(f"{self.base}/api/orders", timeout=15)
            if r.status_code != 200:
                return []
            raw = r.json().get("data", [])
        except Exception:
            return []

        if not self._products_cache:
            self.get_products()
        pmap = {p.id: p for p in self._products_cache}

        orders = []
        for o in raw:
            prod = pmap.get(o.get("product_id", 0))
            rec = OrderRecord(
                id=o["id"],
                order_id=o.get("order_id") or "",
                customer_name=o.get("customer_name", ""),
                product_id=o.get("product_id", 0),
                quantity=o.get("quantity", 0),
                discount=float(o.get("discount") or 0),
                total=float(o.get("total") or 0),
                shipping_fee=float(o.get("shipping_fee") or 0),
                total_sales=float(o.get("total_sales") or 0),
                status=o.get("status", "Pending"),
                shipping_address=o.get("shipping_address") or "",
                customer_gender=o.get("customer_gender") or "",
                customer_city=o.get("customer_city") or "",
                payment_method=o.get("payment_method") or "Offline/COD",
                courier=o.get("courier") or "",
                estimated_delivery_days=int(o.get("estimated_delivery_days") or 0),
                sales_channel=o.get("sales_channel") or "",
                customer_rating=float(o.get("customer_rating") or 0),
                sales_date=(o.get("sales_date") or "")[:10],
                product_name=prod.product_name if prod else f"[ID {o.get('product_id')}]",
                category=prod.category if prod else "Lainnya",
                price=prod.price if prod else 0.0,
            )
            if status  != "All" and rec.status != status:      continue
            if channel != "All" and rec.sales_channel != channel: continue
            orders.append(rec)
        return orders

    def create_order(self, data: dict) -> dict:
        r = requests.post(f"{self.base}/api/orders", json=data, timeout=10)
        r.raise_for_status()
        return r.json()

    def update_order_status(self, order_id: int, status: str) -> dict:
        r = requests.put(f"{self.base}/api/orders/{order_id}",
                         json={"status": status}, timeout=10)
        r.raise_for_status()
        return r.json()

    def update_order(self, order_id: int, data: dict) -> dict:
        """PUT /api/orders/{id} — update semua field order."""
        r = requests.put(f"{self.base}/api/orders/{order_id}", json=data, timeout=10)
        r.raise_for_status()
        return r.json()

    def delete_order(self, order_id: int) -> dict:
        r = requests.delete(f"{self.base}/api/orders/{order_id}", timeout=10)
        r.raise_for_status()
        return r.json()

    # ── Aggregasi untuk Dashboard & Chart ────────────────────────────────────

    def summary_stats(self, orders: list[OrderRecord]) -> dict:
        n = len(orders)
        rev   = sum(o.total_sales for o in orders)
        units = sum(o.quantity for o in orders)
        return {"total_tx": n, "total_rev": rev,
                "avg_rev": rev / n if n else 0, "total_units": units}

    def revenue_by_kategori(self, orders):
        r = {}
        for o in orders:
            r[o.category] = r.get(o.category, 0) + o.total_sales
        return dict(sorted(r.items(), key=lambda x: -x[1]))

    def revenue_by_status(self, orders):
        r = {}
        for o in orders:
            r[o.status] = r.get(o.status, 0) + o.total_sales
        return dict(sorted(r.items(), key=lambda x: -x[1]))

    def revenue_by_month(self, orders):
        r = {}
        for o in orders:
            m = o.sales_date[:7] if len(o.sales_date) >= 7 else "?"
            r[m] = r.get(m, 0) + o.total_sales
        return dict(sorted(r.items()))

    def units_by_payment(self, orders):
        r = {}
        for o in orders:
            r[o.payment_method] = r.get(o.payment_method, 0) + o.quantity
        return dict(sorted(r.items(), key=lambda x: -x[1]))

    def top_products(self, orders, n=10):
        r = {}
        for o in orders:
            r[o.product_name] = r.get(o.product_name, 0) + o.total_sales
        return dict(sorted(r.items(), key=lambda x: -x[1])[:n])