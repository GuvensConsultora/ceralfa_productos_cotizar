# ceralfa_productos_cotizar

## Bloque 1: Introducción

### Qué hace Odoo nativamente

Odoo gestiona presupuestos de venta (`sale.order`) y solicitudes de cotización a proveedores (`purchase.order`) como flujos independientes. No existe un mecanismo nativo que conecte una línea de presupuesto de venta con una solicitud de cotización de compra para que el vendedor pida precio al área de compras antes de cerrar el presupuesto.

### Limitación

Previamente se usaba un modelo de Studio (`x_productos_a_cotizar`) que tenía problemas de rendimiento, mantenimiento y extensibilidad. Además, el flujo requería navegar entre módulos manualmente.

### Qué mejora este módulo

Implementa un flujo integrado **Ventas → Compras → Ventas**:

1. El vendedor activa un toggle en la línea del presupuesto
2. Se crea automáticamente un registro en "Productos a Cotizar"
3. El comprador genera RFQs, obtiene precio del proveedor, aplica margen
4. El precio calculado vuelve automáticamente al presupuesto de venta

**Versión actual:** `19.0.2.0.0`

---

## Bloque 2: Funcionamiento para el usuario final

### Flujo completo paso a paso

```
Vendedor                              Comprador
   │                                      │
   ├─ Presupuesto de venta                │
   │   └─ Activa toggle "Soli. coti."     │
   │      en la línea del producto         │
   │                                      │
   ├─ Se crea registro automáticamente ───┤
   │   (estado: Nuevo)                    │
   │                                      ├─ Ve registros en lista
   │                                      │   (Compras → Productos a Cotizar)
   │                                      │
   │                                      ├─ Selecciona items en "Nuevo"
   │                                      │   → Actions → "Ceralfa -> Prod a Cot
   │                                      │   -> Cotizaciones"
   │                                      │   → Se crea RFQ con empresa propia
   │                                      │   → Estado pasa a "En progreso"
   │                                      │
   │                                      ├─ Edita RFQ: cambia proveedor,
   │                                      │   envía al proveedor, recibe respuesta
   │                                      │
   │                                      ├─ Actions → "Ceralfa: Importar
   │                                      │   Precio Compra"
   │                                      │   → Lee precio de la RFQ
   │                                      │
   │                                      ├─ Pone margen (ej: 1.20 = +20%)
   │                                      │
   │                                      └─ Actions → "Ceralfa: Botón Listo"
   │                                         → Calcula precio venta
   │                                         → Estado pasa a "Listo"
   │                                         → Precio vuelve al presupuesto
   │
   └─ Ve precio actualizado en su
      línea de presupuesto
```

### Qué ve el vendedor

En el formulario del presupuesto de venta, cada línea de producto tiene:

| Campo | Descripción |
|-------|-------------|
| **Soli. coti.** (toggle) | Al activarlo, crea automáticamente el registro en Productos a Cotizar |
| **Px actual.** (checkbox) | Indica que el item ya tiene precio vigente |

Si el vendedor desactiva el toggle y el registro está en estado "Nuevo", se elimina automáticamente. Si ya avanzó a "En progreso" o "Listo", no se borra.

### Qué ve el comprador

En **Compras → Productos a Cotizar**:

- **Vista lista** agrupable con todas las solicitudes (filtro por defecto: Nuevo)
- **3 server actions** en el menú "Acciones":
  - **Ceralfa -> Prod a Cot -> Cotizaciones**: crea RFQs desde items Nuevo
  - **Ceralfa: Importar Precio Compra**: trae precio de la RFQ respondida
  - **Ceralfa: Botón Listo**: calcula precio final y lo devuelve al presupuesto

### Cálculo del margen

El margen es un **multiplicador directo**, no un porcentaje aditivo:

| Valor Compra Inicial | Margen | Valor Compra Final | Explicación |
|---------------------|--------|-------------------|-------------|
| 100.00 | 1.20 | 120.00 | +20% |
| 100.00 | 1.50 | 150.00 | +50% |
| 100.00 | 2.00 | 200.00 | +100% |

Fórmula: `Valor Compra Final = Valor Compra Inicial × Margen`

### Estados del registro

| Estado | Significado | Cómo se llega |
|--------|-------------|---------------|
| **Nuevo** | Vendedor solicitó cotización | Toggle activado en SO line |
| **En progreso** | Comprador generó RFQ | Action "Crear Cotizaciones" |
| **Listo** | Precio devuelto al presupuesto | Action "Botón Listo" |

---

## Bloque 3: Parametrización

### Instalación

1. Colocar el módulo en la carpeta de addons
2. Actualizar lista de módulos: **Ajustes → Actualizar lista de módulos**
3. Buscar "Productos a Cotizar" e instalar

### Acceso al módulo

**Menú:** Compras → Productos a Cotizar

**Grupos requeridos:**
- Vendedores: necesitan grupo "Ventas / Usuario" para activar el toggle
- Compradores: necesitan grupo "Compras / Usuario" para gestionar solicitudes
- Solo "Compras / Administrador" puede eliminar registros

### Uso desde Ventas (vendedor)

1. Ir a **Ventas → Presupuestos**
2. Abrir o crear un presupuesto
3. En las líneas de producto, activar el toggle **"Soli. coti."** en los items que necesitan cotización
4. El registro se crea automáticamente en Productos a Cotizar

### Uso desde Compras (comprador)

1. Ir a **Compras → Productos a Cotizar** (se abre con filtro "Nuevo")
2. Seleccionar los items a cotizar (checkbox en lista)
3. **Acciones → "Ceralfa -> Prod a Cot -> Cotizaciones"**
   - Se crea una RFQ con la empresa propia como proveedor temporal
   - El comprador edita la RFQ y cambia el proveedor
   - Envía la RFQ al proveedor
4. Cuando el proveedor responde con precio:
   - Seleccionar los items en "En progreso"
   - **Acciones → "Ceralfa: Importar Precio Compra"**
   - El precio de la RFQ se copia al campo "Valor Compra Inicial"
5. Completar el campo **Margen** (ej: 1.20 para +20%)
6. **Acciones → "Ceralfa: Botón Listo"**
   - Calcula el precio de venta (compra × margen)
   - Actualiza el precio en la línea del presupuesto de venta
   - Estado pasa a "Listo"

---

## Bloque 4: Referencia técnica

### Arquitectura

```
ceralfa_productos_cotizar/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── productos_cotizar.py      ← modelo principal (productos.cotizar)
│   └── sale_order_line.py        ← extensión sale.order.line (toggle)
├── views/
│   ├── productos_cotizar_views.xml  ← list, form, kanban, search, action, server actions
│   ├── sale_order_line_views.xml    ← herencia vista sale.order (toggles)
│   └── menu.xml                     ← menú en Compras
├── security/
│   └── ir.model.access.csv
└── migrations/
    └── 19.0.1.0.0/
        └── post-migrate.py       ← migración datos Studio
```

### Modelo `productos.cotizar`

**Herencia:** `mail.thread`, `mail.activity.mixin`
**Orden:** `priority desc, date desc, id desc`

#### Campos

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `name` | Char | Referencia automática (secuencia `SOL/YYYY/XXXXX`) |
| `stage` | Selection | Etapa: nuevo, en_progreso, listo |
| `priority` | Selection | Normal / Urgente |
| `date` | Datetime | Fecha de creación |
| `date_start` | Datetime | Periodo inicio |
| `date_stop` | Datetime | Periodo fin |
| `date_done` | Date | Fecha en que pasó a Listo |
| `product_id` | Many2one → `product.product` | Producto a cotizar |
| `category_id` | Many2one → `product.category` | Categoría del producto (related stored) |
| `description` | Text | Nombre del producto (related) |
| `quantity` | Float | Cantidad solicitada |
| `company_id` | Many2one → `res.company` | Compañía |
| `currency_id` | Many2one → `res.currency` | Divisa de compra |
| `exchange_rate` | Float | Tipo de cambio |
| `lead_time` | Integer | Plazo de entrega en días |
| `date_delivery` | Date | Fecha de entrega |
| `purchase_order_id` | Many2one → `purchase.order` | RFQ generada (readonly) |
| `purchase_line_id` | Many2one → `purchase.order.line` | Línea de RFQ (readonly) |
| `purchase_price_initial` | Float | Valor Compra Inicial |
| `margin` | Float | Margen (multiplicador directo) |
| `purchase_price_final` | Float (computed, stored) | `purchase_price_initial × margin` |
| `sale_currency_id` | Many2one → `res.currency` | Divisa de venta |
| `sale_order_id` | Many2one → `sale.order` | Presupuesto de venta origen |
| `sale_line_id` | Many2one → `sale.order.line` | Línea del presupuesto |
| `sale_value_calc` | Float | Valor venta calculado |
| `partner_id` | Many2one → `res.partner` | Cliente |
| `pricelist_id` | Many2one → `product.pricelist` | Lista de precios |
| `user_id` | Many2one → `res.users` | Vendedor |

#### Métodos

**`create()`** — Secuencia automática

```python
@api.model_create_multi
def create(self, vals_list):
    for vals in vals_list:
        if vals.get("name", _("Nuevo")) == _("Nuevo"):
            vals["name"] = self.env["ir.sequence"].next_by_code(
                "productos.cotizar"
            ) or _("Nuevo")
    return super().create(vals_list)
```

**`_compute_purchase_price_final()`** — Multiplicador directo

```python
@api.depends("purchase_price_initial", "margin")
def _compute_purchase_price_final(self):
    for rec in self:
        if rec.purchase_price_initial and rec.margin:
            rec.purchase_price_final = rec.purchase_price_initial * rec.margin
        else:
            rec.purchase_price_final = rec.purchase_price_initial
```

**`action_create_purchase_orders()`** — Crear RFQs

- Filtra solo registros en estado "nuevo"
- Agrupa por moneda (no por proveedor: el proveedor se asigna después en la RFQ)
- Crea RFQ con `partner_id = self.env.company.partner_id` (empresa propia como vendor temporal)
- Cambia estado a "en_progreso"
- Retorna acción para ver las POs creadas

**`action_import_purchase_price()`** — Importar precio de PO

- Solo para registros en "en_progreso" con `purchase_line_id`
- Lee `purchase_line_id.price_unit` → `purchase_price_initial`
- Ignora si el precio es 0.0

**`action_boton_listo()`** — Devolver precio al presupuesto

- Solo para registros en "en_progreso"
- Calcula `sale_value_calc = purchase_price_initial × margin`
- Escribe `price_unit` en la `sale_line_id` vinculada
- Estado → "listo", registra `date_done`

### Extensión `sale.order.line`

#### Campos agregados

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `solicitar_cotizacion` | Boolean | Toggle que crea/elimina registro en productos.cotizar |
| `precio_actual` | Boolean | Indica si el item tiene precio vigente |

#### Lógica del toggle

```python
def write(self, vals):
    res = super().write(vals)
    if "solicitar_cotizacion" not in vals:
        return res
    for line in self:
        if vals["solicitar_cotizacion"]:
            # ON → crear solicitud si no existe
            existente = self.env["productos.cotizar"].search(
                [("sale_line_id", "=", line.id)], limit=1
            )
            if not existente and line.product_id:
                line._crear_solicitud_cotizacion()
        else:
            # OFF → eliminar solo si está en "nuevo"
            solicitud = self.env["productos.cotizar"].search(
                [("sale_line_id", "=", line.id), ("stage", "=", "nuevo")]
            )
            solicitud.unlink()
    return res
```

### Server Actions

| Action | Binding | Método |
|--------|---------|--------|
| Ceralfa -> Prod a Cot -> Cotizaciones | productos.cotizar | `action_create_purchase_orders()` |
| Ceralfa: Importar Precio Compra | productos.cotizar | `action_import_purchase_price()` |
| Ceralfa: Botón Listo | productos.cotizar | `action_boton_listo()` |

### Seguridad

| Grupo | Leer | Escribir | Crear | Eliminar |
|-------|------|----------|-------|----------|
| Purchase User | ✓ | ✓ | ✓ | ✗ |
| Purchase Manager | ✓ | ✓ | ✓ | ✓ |
| Sale User | ✓ | ✓ | ✓ | ✗ |

### Vistas

- **List**: columnas según requerimiento del cliente, `multi_edit=1`, badge con decoraciones por estado
- **Form**: header con botón "Pasar a Listo" + statusbar, secciones COMPRAS / VENTAS, chatter
- **Kanban**: agrupado por stage con progressbar de prioridad
- **Search**: filtros Nuevo/En progreso/Listo/Urgentes, group by Etapa/Producto/Vendedor/Cliente
- **Action**: vista por defecto lista, filtro `search_default_filter_nuevo`

### Dependencias

| Módulo | Motivo |
|--------|--------|
| `sale` | Herencia `sale.order.line` + vistas |
| `purchase` | Creación de `purchase.order` + grupos seguridad |
| `mail` | Chatter (`mail.thread` + `mail.activity.mixin`) |

### Compatibilidad Odoo 19

- `<list>` en lugar de `<tree>`
- Sin `<group>` dentro de `<search>`
- `invisible` con expresión Python (no `attrs`)
- `@api.model_create_multi` para `create()`
- `license` declarado en manifest

### Migración de datos (Studio → modelo nativo)

Script `migrations/19.0.1.0.0/post-migrate.py`:
1. Verifica si la tabla Studio `x_productos_a_cotizar` existe
2. Descubre dinámicamente las columnas reales `x_studio_*`
3. Mapea columnas encontradas al nuevo modelo
4. Crea registros uno a uno con manejo de errores individual

### Verificación

1. **Toggle SO:** Crear presupuesto → agregar línea → activar toggle → verificar registro en Compras > Productos a cotizar (Nuevo)
2. **Desactivar toggle:** Desactivar → verificar que se elimina (solo si Nuevo)
3. **Crear RFQ:** Seleccionar items Nuevo → Actions → Crear cotizaciones → verificar RFQ creada, estado En progreso
4. **Importar precio:** Poner precio en RFQ → Actions → Importar Precio → verificar Valor Compra Inicial
5. **Margen:** Poner margen 1.20 → verificar Valor Compra Final = Inicial × 1.20
6. **Botón Listo:** Actions → Botón Listo → verificar estado Listo y precio actualizado en sale.order.line
