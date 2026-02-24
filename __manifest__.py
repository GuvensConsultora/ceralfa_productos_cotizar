{
    'name': 'Productos a Cotizar',
    'version': '19.0.1.0.0',
    'category': 'Sales',
    'summary': 'Gestión de productos a cotizar con vinculación compra/venta',
    'author': 'Guvens Consultora',
    'license': 'LGPL-3',
    'depends': ['mail', 'product', 'sale', 'purchase'],
    'data': [
        'security/ir.model.access.csv',
        'views/x_productos_a_cotizar_views.xml',
        'data/server_actions.xml',
    ],
    'installable': True,
}
