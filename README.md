# ceralfa_productos_cotizar

## Descripción

Módulo Odoo 19 que reemplaza el modelo de Studio `x_productos_a_cotizar` con una implementación Python propia. Gestiona el flujo de solicitudes de cotización desde el área de ventas hacia compras.

### Problema que resuelve

En Studio, el modelo `x_productos_a_cotizar` tenía limitaciones de rendimiento, mantenimiento y extensibilidad. Este módulo lo reemplaza con un modelo nativo que ofrece:

- Pipeline kanban para que compradores gestionen solicitudes
- Botón directo en líneas de presupuesto para que vendedores soliciten cotización
- Generación automática de RFQs (`purchase.order`) agrupadas por proveedor + moneda
- Chatter con tracking de cambios
- Migración automática de datos históricos de Studio

---

## Funcionamiento nativo de Odoo utilizado

### `mail.thread` + `mail.activity.mixin`
Odoo provee estos mixins para agregar chatter (mensajes + actividades) a cualquier modelo. Al heredarlos, el modelo obtiene automáticamente:
- Historial de cambios (campos con `tracking=True`)
- Mensajes internos y notas
- Planificación de actividades

### `ir.sequence`
Mecanismo estándar de Odoo para generar referencias únicas automáticas (ej: `SOL/2026/00001`). Se define como data XML y se consume en el `create()` del modelo.

### `group_expand` en Selection
Patrón Odoo para vistas kanban tipo pipeline. Cuando el campo de agrupación tiene `group_expand`, Odoo llama al método indicado para obtener todas las columnas posibles, incluso las que no tienen registros.

### Herencia de vistas con `xpath`
Odoo permite extender vistas existentes sin modificarlas directamente. Usamos `xpath` para inyectar el botón "Solic. Coti." dentro de la lista embebida de `order_line` en el form de `sale.order`.

### `purchase.order` creation pattern
Creación programática de órdenes de compra usando `env["purchase.order"].create()` + `env["purchase.order.line"].create()`. Odoo se encarga de los onchanges y defaults internamente.

---

## Arquitectura del módulo

```
ceralfa_productos_cotizar/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── productos_cotizar.py      ← modelo principal
│   └── sale_order_line.py        ← botón en sale.order
├── views/
│   ├── productos_cotizar_views.xml  ← list, form, kanban, search, action, secuencia
│   ├── sale_order_line_views.xml    ← herencia vista sale.order
│   └── menu.xml                     ← menú en Compras
├── security/
│   └── ir.model.access.csv
└── migrations/
    └── 19.0.1.0.0/
        └── post-migrate.py       ← migración datos Studio
```

---

## Modelo `productos.cotizar`

### Etapas (pipeline kanban)

| Etapa | Descripción |
|-------|-------------|
| `borrador` | Solicitud creada manualmente, aún sin enviar |
| `solicitado` | Vendedor solicitó cotización (desde presupuesto) |
| `cotizado` | Comprador generó la orden de compra (RFQ) |
| `listo` | Proceso completado |

### Campos

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `name` | Char | Referencia automática (secuencia `SOL/YYYY/XXXXX`) |
| `stage` | Selection | Etapa del pipeline con `group_expand` |
| `priority` | Selection | Normal / Urgente |
| `date` | Datetime | Fecha de solicitud |
| `date_start` / `date_stop` | Date | Rango de fechas |
| `date_done` | Date | Fecha de finalización |
| `product_id` | Many2one → `product.product` | Producto a cotizar |
| `quantity` | Float | Cantidad solicitada |
| `supplier_id` | Many2one → `res.partner` | Proveedor (filtrado por `supplier_rank > 0`) |
| `currency_id` | Many2one → `res.currency` | Moneda de compra |
| `exchange_rate` | Float | Tipo de cambio |
| `lead_time` | Integer | Plazo de entrega en días |
| `purchase_order_id` | Many2one → `purchase.order` | OC generada (readonly) |
| `purchase_line_id` | Many2one → `purchase.order.line` | Línea de OC (readonly) |
| `purchase_price_initial` | Float | Precio de compra inicial |
| `margin` | Float | Margen en % |
| `purchase_price_final` | Float (computed, stored) | `precio_inicial * (1 + margen/100)` |
| `sale_currency_id` | Many2one → `res.currency` | Moneda de venta |
| `sale_order_id` | Many2one → `sale.order` | Presupuesto origen (readonly) |
| `sale_line_id` | Many2one → `sale.order.line` | Línea de presupuesto (readonly) |
| `sale_value_calc` | Float | Valor de venta calculado |
| `partner_id` | Many2one → `res.partner` | Cliente |
| `pricelist_id` | Many2one → `product.pricelist` | Lista de precios |
| `user_id` | Many2one → `res.users` | Vendedor |

---

## Métodos principales

### `create()` — Secuencia automática

```python
@api.model_create_multi
def create(self, vals_list):
    """Asigna secuencia automática al crear registros."""
    for vals in vals_list:
        if vals.get("name", _("Nuevo")) == _("Nuevo"):
            vals["name"] = self.env["ir.sequence"].next_by_code(
                "productos.cotizar"
            ) or _("Nuevo")
    return super().create(vals_list)
```

**Patrón:** Override de `create()` con `@api.model_create_multi` (Odoo 19). Asigna la secuencia `SOL/YYYY/XXXXX` solo si el name no fue seteado manualmente.

### `_compute_purchase_price_final()` — Campo computed stored

```python
@api.depends("purchase_price_initial", "margin")
def _compute_purchase_price_final(self):
    """Precio final = precio inicial * (1 + margen/100)"""
    for rec in self:
        if rec.purchase_price_initial and rec.margin:
            rec.purchase_price_final = rec.purchase_price_initial * (
                1 + rec.margin / 100
            )
        else:
            rec.purchase_price_final = rec.purchase_price_initial
```

**Patrón:** Computed + stored. Se persiste en DB para poder filtrar y agrupar en vistas list/kanban sin recalcular en cada lectura.

### `_group_expand_stage()` — Columnas kanban

```python
@api.model
def _group_expand_stage(self, stages, domain):
    return [key for key, _ in STAGE_SELECTION]
```

**Patrón:** `group_expand`. Odoo llama este método al agrupar por `stage` en kanban. Retorna todas las keys del selection para que se muestren columnas vacías.

### `action_create_purchase_orders()` — Generación de RFQs

```python
def action_create_purchase_orders(self):
    """Crea purchase.order agrupadas por proveedor + moneda.
    Cada solicitud se convierte en una línea de la PO correspondiente.
    """
    # Validar que todas tengan proveedor y moneda
    for rec in self:
        if not rec.supplier_id:
            raise UserError(
                _("La solicitud '%s' no tiene proveedor asignado.") % rec.name
            )
        if not rec.currency_id:
            raise UserError(
                _("La solicitud '%s' no tiene moneda de compra.") % rec.name
            )

    # Agrupar por (proveedor, moneda)
    groups = {}
    for rec in self:
        key = (rec.supplier_id.id, rec.currency_id.id)
        groups.setdefault(key, self.browse())
        groups[key] |= rec

    created_orders = self.env["purchase.order"]
    for (supplier_id, currency_id), recs in groups.items():
        # Crear PO
        po = self.env["purchase.order"].create(
            {
                "partner_id": supplier_id,
                "currency_id": currency_id,
            }
        )
        # Crear líneas
        for rec in recs:
            pol = self.env["purchase.order.line"].create(
                {
                    "order_id": po.id,
                    "product_id": rec.product_id.id,
                    "product_qty": rec.quantity,
                    "price_unit": rec.purchase_price_initial or 0.0,
                }
            )
            # Linkear solicitud → PO y línea
            rec.write(
                {
                    "purchase_order_id": po.id,
                    "purchase_line_id": pol.id,
                    "stage": "cotizado",
                }
            )
        created_orders |= po

    # Retornar acción para ver las POs creadas
    if len(created_orders) == 1:
        return {
            "type": "ir.actions.act_window",
            "res_model": "purchase.order",
            "res_id": created_orders.id,
            "view_mode": "form",
            "target": "current",
        }
    return {
        "type": "ir.actions.act_window",
        "res_model": "purchase.order",
        "domain": [("id", "in", created_orders.ids)],
        "view_mode": "list,form",
        "target": "current",
    }
```

**Patrón:** Agrupación por tupla `(proveedor, moneda)` → 1 PO por combinación. Evita crear múltiples POs al mismo proveedor. Después de crear, linkea cada solicitud con su PO + línea y avanza el stage a "cotizado".

---

## Extensión `sale.order.line`

### `action_solicitar_cotizacion()` — Botón en líneas de presupuesto

```python
class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def action_solicitar_cotizacion(self):
        """Crea un registro en productos.cotizar desde la línea de venta."""
        self.ensure_one()
        order = self.order_id
        vals = {
            "product_id": self.product_id.id,
            "quantity": self.product_uom_qty,
            "stage": "solicitado",
            # Datos de venta
            "sale_order_id": order.id,
            "sale_line_id": self.id,
            "partner_id": order.partner_id.id,
            "pricelist_id": order.pricelist_id.id,
            "sale_currency_id": order.currency_id.id,
            "user_id": order.user_id.id or self.env.user.id,
            "sale_value_calc": self.price_subtotal,
        }
        solicitud = self.env["productos.cotizar"].create(vals)

        # Retornar form de la solicitud creada
        return {
            "type": "ir.actions.act_window",
            "name": _("Solicitud de Cotización"),
            "res_model": "productos.cotizar",
            "res_id": solicitud.id,
            "view_mode": "form",
            "target": "current",
        }
```

**Patrón:** `_inherit` sin `_name` = herencia por extensión (no crea modelo nuevo). El método crea la solicitud pre-cargada con todos los datos disponibles de la línea y la orden, y abre el form para que el vendedor complete lo que falte (proveedor, moneda, etc.).

### Vista — xpath en `sale.order` form

```xml
<record id="sale_order_form_inherit_productos_cotizar" model="ir.ui.view">
    <field name="name">sale.order.form.inherit.productos.cotizar</field>
    <field name="model">sale.order</field>
    <field name="inherit_id" ref="sale.view_order_form"/>
    <field name="arch" type="xml">
        <xpath expr="//field[@name='order_line']//list//field[@name='price_subtotal']"
               position="after">
            <button name="action_solicitar_cotizacion"
                string="Solic. Coti."
                type="object"
                icon="fa-shopping-cart"
                title="Solicitar cotización al área de compras"
                class="btn-link"/>
        </xpath>
    </field>
</record>
```

**Patrón:** Herencia de vista con `xpath`. El `expr` navega dentro del campo `order_line` → su `<list>` embebida → después del campo `price_subtotal`. El botón se renderiza en cada fila de la lista de líneas.

---

## Seguridad

| Grupo | Leer | Escribir | Crear | Eliminar |
|-------|------|----------|-------|----------|
| Purchase User | ✓ | ✓ | ✓ | ✗ |
| Purchase Manager | ✓ | ✓ | ✓ | ✓ |
| Sale User | ✓ | ✓ | ✓ | ✗ |

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_productos_cotizar_purchase_user,productos.cotizar.purchase.user,model_productos_cotizar,purchase.group_purchase_user,1,1,1,0
access_productos_cotizar_purchase_manager,productos.cotizar.purchase.manager,model_productos_cotizar,purchase.group_purchase_manager,1,1,1,1
access_productos_cotizar_sale_user,productos.cotizar.sale.user,model_productos_cotizar,sales_team.group_sale_salesman,1,1,1,0
```

**Por qué:** Los vendedores necesitan crear y editar solicitudes pero no eliminarlas. Solo el manager de compras puede eliminar.

---

## Vistas

### Kanban (vista principal)

Agrupada por `stage` con `progressbar` de prioridad. Cada tarjeta muestra:
- Prioridad (estrella) + avatar vendedor
- Referencia + producto
- Cantidad + precio + moneda
- Proveedor y cliente (si existen)

### List

Vista con `multi_edit=1` para edición masiva. Campo `stage` con widget `badge` y decoraciones de color por etapa.

### Form

- **Header:** Botón "Crear Orden de Compra" (visible solo en stage `solicitado`, grupo `purchase_user`) + statusbar
- **General:** Producto, cantidad, prioridad, fechas
- **Proveedor:** Proveedor + plazo de entrega
- **Compras:** Moneda, TC, precios, margen, OC generada
- **Ventas:** Moneda venta, presupuesto, cliente, vendedor
- **Chatter:** Mensajes + actividades

### Search

Filtros predefinidos por etapa + urgentes. Agrupadores por etapa, proveedor, producto y vendedor. Filtro por defecto: `solicitado`.

### Menú

`Compras → Productos a Cotizar` (grupo: `purchase_user`, sequence: 15)

---

## Migración de datos (Studio → nuevo modelo)

Script `migrations/19.0.1.0.0/post-migrate.py`:

```python
def migrate(cr, version):
    """Migra registros de x_productos_a_cotizar a productos_cotizar."""
    env = api.Environment(cr, SUPERUSER_ID, {})

    # Verificar si la tabla Studio existe
    cr.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'x_productos_a_cotizar'
        )
    """)
    if not cr.fetchone()[0]:
        _logger.info(
            "Tabla x_productos_a_cotizar no encontrada. "
            "Saltando migración de datos."
        )
        return

    # Obtener columnas reales de la tabla Studio
    cr.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'x_productos_a_cotizar'
    """)
    existing_columns = {row[0] for row in cr.fetchall()}

    # Filtrar solo columnas que existen en la tabla
    valid_mappings = {}
    for studio_col, new_col in COLUMN_MAP.items():
        if studio_col in existing_columns and new_col:
            valid_mappings[studio_col] = new_col

    # Leer registros Studio y crear en nuevo modelo
    studio_cols = ", ".join(valid_mappings.keys())
    cr.execute(f"SELECT id, {studio_cols} FROM x_productos_a_cotizar")
    rows = cr.fetchall()
    col_names = ["id"] + list(valid_mappings.keys())

    migrated = 0
    for row in rows:
        record = dict(zip(col_names, row))
        vals = {}
        for studio_col, new_col in valid_mappings.items():
            value = record.get(studio_col)
            if value is not None:
                vals[new_col] = value
        if vals:
            try:
                env["productos.cotizar"].create(vals)
                migrated += 1
            except Exception as e:
                _logger.warning("Error migrando registro Studio id=%s: %s", record["id"], e)

    _logger.info("Migración completada: %d/%d registros migrados", migrated, len(rows))
```

**Estrategia:**
1. Verifica si la tabla Studio existe (no falla si no está)
2. Descubre dinámicamente las columnas reales de la tabla (los nombres `x_studio_*` pueden variar)
3. Mapea solo las columnas que encuentra
4. Crea registros uno a uno con manejo de errores individual
5. Loguea resultado de la migración

**IMPORTANTE:** Verificar los nombres reales de columnas `x_studio_*` en la DB de staging antes del deploy. El `COLUMN_MAP` en el script tiene nombres estimados que deben ajustarse.

---

## Flujo de uso

```
Vendedor                          Comprador
   │                                  │
   ├─ Presupuesto de venta            │
   │   └─ Click "Solic. Coti."       │
   │       en línea de producto       │
   │                                  │
   ├─ Se crea solicitud ──────────────┤
   │   (stage: solicitado)            │
   │                                  ├─ Ve solicitud en kanban
   │                                  │   (Compras → Productos a Cotizar)
   │                                  │
   │                                  ├─ Completa: proveedor, moneda,
   │                                  │   precio, margen, plazo
   │                                  │
   │                                  ├─ Click "Crear Orden de Compra"
   │                                  │   → Genera purchase.order
   │                                  │   → stage pasa a "cotizado"
   │                                  │
   │                                  ├─ Gestiona RFQ en módulo Compras
   │                                  │   (confirma, recibe, etc.)
   │                                  │
   │                                  └─ Marca como "listo"
   │
   └─ Ve la OC linkeada en la solicitud
```

---

## Dependencias

| Módulo | Motivo |
|--------|--------|
| `sale` | Herencia de `sale.order.line` + vistas |
| `purchase` | Creación de `purchase.order` + grupos de seguridad |
| `mail` | Chatter (`mail.thread` + `mail.activity.mixin`) |

---

## Compatibilidad Odoo 19

- `<list>` en lugar de `<tree>` (breaking change Odoo 19)
- Sin `<group>` dentro de `<search>` (RNG validation)
- `invisible` con expresión Python (no `attrs`)
- `@api.model_create_multi` (reemplaza `@api.model` para create)
- `license` declarado en manifest
