from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.sql import func
from database import Base


class Product(Base):
    __tablename__ = "products"

    id           = Column(Integer, primary_key=True, index=True)
    product_name = Column(String, index=True)
    category     = Column(String)
    price        = Column(Float)


class Order(Base):
    __tablename__ = "orders"

    id                     = Column(Integer, primary_key=True, index=True)
    order_id               = Column(String, index=True)          # e.g. "ORD00001"
    customer_name          = Column(String)
    product_id             = Column(Integer, ForeignKey("products.id"))
    quantity               = Column(Integer)
    discount               = Column(Float, default=0)
    total                  = Column(Float)                       # setelah diskon
    shipping_fee           = Column(Float, default=0)
    total_sales            = Column(Float)                       # total + shipping_fee
    status                 = Column(String, default="Pending")
    shipping_address       = Column(String, default="")
    customer_gender        = Column(String, default="")
    customer_city          = Column(String, default="")
    payment_method         = Column(String, default="Offline/COD")
    courier                = Column(String, default="")
    estimated_delivery_days = Column(Integer, default=0)
    sales_channel          = Column(String, default="")
    customer_rating        = Column(Float, default=0)
    sales_date             = Column(DateTime(timezone=True), server_default=func.now())


class User(Base):
    __tablename__ = "users"

    id       = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password = Column(String)
