from pydantic import BaseModel
from typing import List, Optional


class LoginRequest(BaseModel):
    username: str
    password: str


class ProductCreate(BaseModel):
    product_name: str
    category:     str
    price:        float
    user_id:      Optional[int] = None

class ProductUpdate(BaseModel):
    product_name: Optional[str]   = None
    category:     Optional[str]   = None
    price:        Optional[float] = None
    user_id:      Optional[int]   = None


class OrderCreate(BaseModel):
    order_id:               Optional[str]   = None
    customer_name:          str
    product_id:             int
    user_id:                Optional[int]   = None
    quantity:               int
    discount:               Optional[float] = 0
    total:                  float
    shipping_fee:           Optional[float] = 0
    total_sales:            Optional[float] = None
    status:                 Optional[str]   = "Pending"
    shipping_address:       Optional[str]   = ""
    customer_gender:        Optional[str]   = ""
    customer_city:          Optional[str]   = ""
    payment_method:         Optional[str]   = "Offline/COD"
    courier:                Optional[str]   = ""
    estimated_delivery_days:Optional[int]   = 0
    sales_channel:          Optional[str]   = ""
    customer_rating:        Optional[float] = 0
    sales_date:             Optional[str]   = None

class OrderUpdate(BaseModel):
    status: str


class BulkOrderCreate(BaseModel):
    orders: List[OrderCreate]