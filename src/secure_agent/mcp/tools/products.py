PRODUCTS = {
    "P100": {
        "name": "Laptop",
        "price": 65000,
        "currency": "INR",
        "stock": 12,
    },
    "P200": {
        "name": "Monitor",
        "price": 15000,
        "currency": "INR",
        "stock": 20,
    },
    "P300": {
        "name": "Keyboard",
        "price": 2000,
        "currency": "INR",
        "stock": 35,
    },
}


def get_product(product_id: str) -> dict:
    """
    Look up a demo product by ID.
    P100 is a laptop, P200 is a monitor, P300 is a keyboard.
    """

    product_id = product_id.strip().upper()

    if product_id not in PRODUCTS:
        raise ValueError(
            "Unknown product ID. "
            "Available IDs: P100, P200, P300"
        )

    return {
        "product_id": product_id,
        **PRODUCTS[product_id],
    }