"""Synthetic Stripe/PayPal/Amazon settlement data, fixed-seed.

Every backend (DuckDB, Snowflake, Databricks) gets seeded from this
same generator with the same seed, so a demo question asked against
any of them returns the identical answer — that's what makes the
backends interchangeable for the purposes of the demo.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, timedelta

from faker import Faker

SEED = 20260714
CHANNELS = ("stripe", "paypal", "amazon")
CATEGORIES = ("supplements", "skincare", "apparel", "electronics", "home")
FEE_RATE = {"stripe": 0.029, "paypal": 0.034, "amazon": 0.15}


@dataclass(frozen=True)
class Product:
    product_id: int
    name: str
    category: str


@dataclass(frozen=True)
class Order:
    order_id: int
    product_id: int
    customer_email: str
    channel: str
    order_amount: float
    order_date: date


@dataclass(frozen=True)
class Settlement:
    settlement_id: int
    order_id: int
    channel: str
    gross_amount: float
    fee_amount: float
    net_amount: float
    settlement_date: date


@dataclass(frozen=True)
class SyntheticDataset:
    products: list[Product]
    orders: list[Order]
    settlements: list[Settlement]


def generate(
    num_products: int = 20,
    num_orders: int = 600,
    start_date: date = date(2024, 1, 1),
    end_date: date = date(2024, 12, 31),
    seed: int = SEED,
) -> SyntheticDataset:
    """Generate a reproducible products/orders/settlements dataset.

    ~90% of orders have a matching settlement (a settlement lands 1-5
    days after the order); the rest are left "in flight" so the data
    isn't artificially tidy.
    """
    faker = Faker()
    faker.seed_instance(seed)
    rng = random.Random(seed)

    products = [
        Product(
            product_id=i,
            name=faker.unique.catch_phrase(),
            category=rng.choice(CATEGORIES),
        )
        for i in range(1, num_products + 1)
    ]

    span_days = (end_date - start_date).days
    orders: list[Order] = []
    settlements: list[Settlement] = []
    settlement_id = 1

    for order_id in range(1, num_orders + 1):
        product = rng.choice(products)
        channel = rng.choice(CHANNELS)
        order_date = start_date + timedelta(days=rng.randint(0, span_days))
        order_amount = round(rng.uniform(15, 250), 2)

        orders.append(
            Order(
                order_id=order_id,
                product_id=product.product_id,
                customer_email=faker.unique.email(),
                channel=channel,
                order_amount=order_amount,
                order_date=order_date,
            )
        )

        if rng.random() < 0.9:
            fee_amount = round(order_amount * FEE_RATE[channel], 2)
            net_amount = round(order_amount - fee_amount, 2)
            settlement_date = order_date + timedelta(days=rng.randint(1, 5))

            settlements.append(
                Settlement(
                    settlement_id=settlement_id,
                    order_id=order_id,
                    channel=channel,
                    gross_amount=order_amount,
                    fee_amount=fee_amount,
                    net_amount=net_amount,
                    settlement_date=settlement_date,
                )
            )
            settlement_id += 1

    return SyntheticDataset(products=products, orders=orders, settlements=settlements)
