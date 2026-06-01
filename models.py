from dataclasses import dataclass, field, asdict
from datetime import datetime, date
from typing import Optional


@dataclass
class Customer:
    name: str
    phone: str = ''
    email: str = ''
    address: str = ''
    company: str = ''
    id: Optional[int] = None
    created_at: str = ''

    def to_dict(self):
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class Product:
    name: str
    category: str
    description: str = ''
    unit_price: float = 0.0
    cost_price: float = 0.0
    stock_qty: float = 0
    unit: str = 'pc'
    is_service: bool = False
    id: Optional[int] = None
    created_at: str = ''

    def to_dict(self):
        d = asdict(self)
        d['is_service'] = 'TRUE' if self.is_service else 'FALSE'
        return d


@dataclass
class Order:
    order_no: str
    customer_id: Optional[int] = None
    due_date: str = ''
    status: str = 'Pending'
    subtotal: float = 0.0
    tax: float = 0.0
    discount: float = 0.0
    total: float = 0.0
    amount_paid: float = 0.0
    payment_status: str = 'Unpaid'
    notes: str = ''
    order_date: str = ''
    id: Optional[int] = None
    created_at: str = ''

    def to_dict(self):
        customer_id = self.customer_id if self.customer_id else ''
        return {
            **{k: v for k, v in asdict(self).items() if v is not None},
            'customer_id': customer_id
        }


@dataclass
class OrderItem:
    order_id: int
    description: str
    quantity: float = 1
    unit_price: float = 0.0
    subtotal: float = 0.0
    product_id: Optional[int] = None
    id: Optional[int] = None

    def to_dict(self):
        d = asdict(self)
        d['product_id'] = self.product_id if self.product_id else ''
        return d


@dataclass
class Payment:
    order_id: int
    amount: float
    method: str = 'Cash'
    reference: str = ''
    payment_date: str = ''
    id: Optional[int] = None

    def to_dict(self):
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class Expense:
    date: str
    description: str
    category: str
    amount: float
    vendor: str = ''
    payment_method: str = ''
    receipt_ref: str = ''
    notes: str = ''
    id: Optional[int] = None
    created_at: str = ''

    def to_dict(self):
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class JournalEntry:
    date: str
    description: str
    entry_type: str
    account_name: str
    debit: float = 0.0
    credit: float = 0.0
    reference_type: str = ''
    reference_id: str = ''
    id: Optional[int] = None
    created_at: str = ''

    def to_dict(self):
        d = asdict(self)
        d['reference_id'] = str(self.reference_id) if self.reference_id else ''
        return d
