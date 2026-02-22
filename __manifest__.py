{
    "name": "Productos a Cotizar",
    "version": "19.0.2.7.0",
    "category": "Purchases",
    "summary": "Solicitudes de cotización desde ventas hacia compras",
    "description": """
        Reemplazo del modelo Studio x_productos_a_cotizar.
        Permite a vendedores solicitar cotizaciones al área de compras
        desde las líneas del presupuesto de ventas.
    """,
    "author": "Guvens Consultora",
    "license": "LGPL-3",
    "depends": [
        "sale",
        "purchase",
        "product",
        "mail",
        "studio_customization",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/productos_cotizar_views.xml",
        "views/x_productos_cotizar_views.xml",
        "views/sale_order_line_views.xml",
        "views/product_category_views.xml",
        "views/menu.xml",
    ],
    "installable": True,
    "application": False,
}
