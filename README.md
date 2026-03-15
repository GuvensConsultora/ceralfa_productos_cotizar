# Productos a Cotizar — ceralfa_productos_cotizar

## 1. Introducción

### Qué hace Odoo nativamente
Odoo permite crear presupuestos de venta y órdenes de compra, pero **no vincula** las líneas de un presupuesto de venta con solicitudes de cotización de compra. Tampoco ofrece un historial rápido de precios por producto y partner desde la línea del presupuesto.

### Limitación
- El vendedor no puede marcar qué productos necesitan cotización del área de compras.
- No hay visibilidad del historial de precios negociados con un cliente/proveedor desde la línea de venta/compra.
- No existe un flujo Kanban para seguimiento de productos pendientes de cotización.

### Qué mejora este módulo
1. **Toggle "Pedir Cotización"** en líneas de presupuesto de venta → crea registros en un modelo Kanban (`x_productos_a_cotizar`) para que Compras los gestione.
2. **Historial de precios** (últimas 10 operaciones) accesible con un botón en cada línea de venta y compra. Muestra el estado de cada operación (Cotización, Orden de venta, Cancelado).
3. **Vista Kanban, Lista, Formulario y Calendario** para gestionar productos pendientes de cotización con etapas configurables.
4. **Acciones masivas**: "Esperando precio", "Marcar como Listo", "Crear/Abrir Cotizaciones".

---

## 2. Funcionamiento para el usuario final

### 2.1 Pedir Cotización desde un Presupuesto de Venta

1. Abrir un presupuesto de venta.
2. En la columna **"Pedir Cotización"**, activar el toggle en las líneas que necesitan cotización.
3. Al guardar, se crean automáticamente registros en **Compras → Productos a Cotizar**.

| Acción del vendedor | Resultado automático |
|---------------------|---------------------|
| Activa toggle | Crea registro en Productos a Cotizar (etapa inicial) |
| Desactiva toggle | Archiva el registro vinculado |
| Reactiva toggle | Reactiva el registro (sin duplicar) |

### 2.2 Historial de Precios

1. En cualquier línea de presupuesto de venta o compra, hacer clic en el botón **🕐** (ícono reloj).
2. Se abre una ventana emergente con las **últimas 10 operaciones** de ese producto con ese cliente/proveedor.
3. Datos mostrados:

| Columna | Descripción |
|---------|-------------|
| Nro Cotización | Número del presupuesto/orden |
| Fecha | Fecha de la operación |
| Producto | Nombre del producto |
| Cantidad | Cantidad cotizada/vendida |
| Precio unitario | Precio por unidad |
| Precio total | Subtotal de la línea |
| **Estado** | Cotización / Cotización enviada / Orden de venta / Bloqueada / Cancelado |

> **Nota**: Se muestran operaciones en **todos los estados** (no solo confirmadas) para dar visibilidad completa del historial de negociación.

### 2.3 Gestión Kanban de Productos a Cotizar

Acceder desde **Compras → Productos a Cotizar**.

**Flujo típico:**

```
[Cotización] → Cotización cargada, esperando precio → [Listo]
```

**Acciones masivas** (seleccionar registros en vista lista):
- **Cotización cargada, esperando precio**: Marca como enviada al proveedor.
- **Marcar como Listo**: Mueve a la última etapa + registra fecha.
- **Cotizaciones**: Abre presupuestos vinculados o crea nuevos agrupados por cliente.

### 2.4 Crear Presupuestos desde Productos a Cotizar

1. Seleccionar uno o más registros en la vista lista.
2. Acción **"Cotizaciones"**:
   - Si la línea **ya tiene** presupuesto vinculado → lo abre.
   - Si **no tiene** → crea un presupuesto de venta por cliente con los productos seleccionados.

---

## 3. Parametrización

### 3.1 Etapas del Kanban

1. Ir a **Compras → Productos a Cotizar** (vista Kanban).
2. Crear etapas con nombre y secuencia. Ejemplo:

| Etapa | Secuencia |
|-------|-----------|
| Pendiente | 10 |
| En proceso | 20 |
| Listo | 30 |

> La primera etapa por secuencia es la etapa inicial. La última es donde se mueven los registros al "Marcar como Listo".

### 3.2 Permisos

| Grupo | Leer | Escribir | Crear | Eliminar |
|-------|------|----------|-------|----------|
| Administración (group_system) | ✅ | ✅ | ✅ | ✅ |
| Usuario interno (group_user) | ✅ | ✅ | ✅ | ❌ |

### 3.3 Dependencias

```
depends: ['mail', 'product', 'sale', 'purchase']
```

No requiere configuración adicional post-instalación.

---

## 4. Referencia técnica

### 4.1 Arquitectura

```
ceralfa_productos_cotizar/
├── __manifest__.py
├── __init__.py
├── models/
│   ├── x_productos_a_cotizar.py    ← Modelo principal + Stages
│   ├── sale_order_line.py          ← Toggle + sync + botón historial (ventas)
│   └── purchase_order_line.py      ← Botón historial (compras)
├── wizards/
│   ├── historial_precios_wizard.py ← Wizard historial de precios
│   └── historial_precios_wizard_views.xml
├── views/
│   ├── x_productos_a_cotizar_views.xml  ← List/Form/Kanban/Calendar/Search/Action/Menú
│   ├── sale_order_line_views.xml        ← Columna toggle + botón en SO lines
│   └── purchase_order_line_views.xml    ← Botón en PO lines
├── data/
│   └── server_actions.xml               ← Acciones masivas (3)
└── security/
    └── ir.model.access.csv
```

### 4.2 Modelos

#### `x_productos_a_cotizar` (modelo principal)

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `x_name` | Char | Descripción del producto a cotizar |
| `x_active` | Boolean | Archivado (active_name custom) |
| `x_studio_producto` | Many2one(product.template) | Producto vinculado |
| `x_studio_cantidad` | Float | Cantidad solicitada |
| `x_studio_cliente` | Many2one(res.partner) | Cliente |
| `x_studio_vendedor` | Many2one(res.users) | Vendedor (related SO.user_id) |
| `x_studio_presupuesto_de_vtas` | Many2one(sale.order) | Presupuesto de venta vinculado |
| `x_studio_ppto_comp` | Many2one(purchase.order) | Presupuesto de compra vinculado |
| `x_studio_linea_ppto_vtas` | Integer | ID de la línea de venta |
| `x_studio_stage_id` | Many2one(stage) | Etapa Kanban |
| `x_studio_kanban_state` | Selection | Estado (draft/sent/sale/cancel) |
| `x_studio_currency_id` | Many2one(res.currency) | Moneda |
| `x_studio_val_vtas_calc` | Monetary | Valor de venta calculado |
| `x_studio_valor_cpra` | Monetary | Valor compra inicial |
| `x_studio_val_cpra_final` | Monetary | Valor compra final |
| `x_studio_margen` | Float | Margen |

Hereda: `mail.thread`, `mail.activity.mixin`

#### `x_productos_a_cotizar_stage`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `x_name` | Char | Nombre de la etapa |
| `x_studio_sequence` | Integer | Orden de la etapa |

#### `sale.order.line` (heredado)

| Campo/Método | Descripción |
|--------------|-------------|
| `x_pedir_cotizacion` | Boolean toggle para solicitar cotización |
| `action_ver_historial_precios()` | Abre wizard con últimas 10 operaciones (ventas) |
| `create()` / `write()` | Override para sync automático con x_productos_a_cotizar |
| `_sync_productos_a_cotizar()` | Crea/archiva/reactiva registros según toggle |

#### `purchase.order.line` (heredado)

| Método | Descripción |
|--------|-------------|
| `action_ver_historial_precios()` | Abre wizard con últimas 10 operaciones (compras) |

### 4.3 Wizard: `historial.precios.wizard`

**Flujo:**
1. `action_open_historial(product_id, partner_id, origin)` → crea wizard + computa líneas
2. `_compute_lines()` → busca últimas 10 líneas de SO/PO sin filtro de estado
3. Muestra resultado en ventana emergente con columna Estado

**Dominio de búsqueda (ventas):**
```python
[('product_id', '=', product_id), ('order_id.partner_id', '=', partner_id)]
# Sin filtro de state → incluye cotizaciones, confirmadas y canceladas
```

**Mapeo de estados:**

| State técnico (sale) | Label mostrado |
|---------------------|----------------|
| draft | Cotización |
| sent | Cotización enviada |
| sale | Orden de venta |
| done | Bloqueada |
| cancel | Cancelado |

| State técnico (purchase) | Label mostrado |
|--------------------------|----------------|
| draft | Solicitud de cotización |
| sent | Solicitud enviada |
| purchase | Orden de compra |
| done | Bloqueada |
| cancel | Cancelado |

### 4.4 Sincronización toggle → x_productos_a_cotizar

```
Vendedor activa toggle → _sync_productos_a_cotizar()
  ├── Si no existe registro → crea nuevo (etapa inicial)
  ├── Si existe archivado → reactiva (x_active = True)
  └── Si existe activo → no hace nada

Vendedor desactiva toggle → _sync_productos_a_cotizar()
  └── Si existe activo → archiva (x_active = False)
```

**Optimización**: Una sola búsqueda batch para todas las líneas, indexada por `(order_id, line_id)` para lookup O(1).

#### `purchase.order.line` (heredado)

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `x_studio_pto_de_vta` | Many2one(sale.order) | Ppto de venta vinculado |
| `x_studio_id_linea_or_vta` | Integer | ID línea orden venta |
| `x_studio_id_prod_a_coti` | Integer | ID producto a cotizar |

### 4.5 Acciones masivas (server actions)

| Acción | Método | Efecto |
|--------|--------|--------|
| Cotización cargada, esperando precio | `action_esperando_precio()` | `kanban_state = 'sent'` |
| Marcar como Listo | `action_marcar_listo()` | `fecha_en_listo = hoy` + última etapa |
| Cotizaciones | `action_cotizaciones()` | Abre/crea presupuestos venta por cliente |
| **Crear Cotización de Compra** | `action_crear_cotizacion_compra()` | Crea PO agrupada por moneda + compañía |

### 4.6 Decisiones técnicas

1. **Nombres `x_studio_*`**: Se mantienen los nombres originales de Studio v17 para reutilizar las columnas existentes en la DB (8499+ registros preservados).
2. **`_active_name = 'x_active'`**: Studio usaba `x_active` en vez de `active`. Sin esta directiva, `active_test=False` no funciona.
3. **`_rec_name = 'x_name'`**: Sin esto, los dropdowns Many2one muestran IDs en vez de nombres.
4. **Server actions con `type="action"`**: Más robusto que `type="object"` durante el upgrade, ya que no valida el método Python al parsear la vista.
5. **Batch sync**: `_sync_productos_a_cotizar()` usa una sola búsqueda + map para evitar N+1 queries.

### 4.7 Seguridad

```csv
# Modelo principal + stages
Administrador: CRUD completo
Usuario interno: lectura, escritura, creación (sin eliminar)

# Wizard historial
Todos los usuarios internos: CRUD completo (TransientModel, se auto-limpia)
```

### 4.8 Verificación

#### Test 1: Toggle Pedir Cotización
1. Crear presupuesto → activar toggle en una línea → guardar.
2. Ir a Compras → Productos a Cotizar.
3. **Esperado**: aparece registro con producto, cliente, cantidad y moneda de la SO.

#### Test 2: Historial de Precios
1. En una línea de presupuesto, clic en botón 🕐 (reloj).
2. **Esperado**: wizard con últimas 10 operaciones del producto + cliente, con columna Estado.

#### Test 3: Acciones masivas (Kanban)
1. Seleccionar registros en vista lista.
2. Ejecutar "Cotización cargada, esperando precio" → verificar `kanban_state = sent`.
3. Ejecutar "Marcar como Listo" → verificar etapa = última + fecha_en_listo = hoy.

#### Test 4: Cotizaciones de Venta
1. Seleccionar registros sin presupuesto vinculado.
2. Ejecutar acción "Cotizaciones".
3. **Esperado**: se crea un SO por cliente con los productos seleccionados.

#### Test 5: Crear Cotización de Compra
1. Seleccionar registros en vista lista (con producto y compañía asignados).
2. En dropdown "Acción" → **"Crear Cotización de Compra"**.
3. **Esperado**: se crea PO agrupada por moneda + compañía, sin error.
4. Los registros se vinculan al PO creado y avanzan de etapa.

#### Test 6: Acción Studio vieja desactivada
1. Ir a Ajustes → Técnico → Acciones de servidor.
2. Buscar la acción que contiene `uom_po_id` en su código (ID 1043).
3. **Acción requerida**: desactivarla o eliminarla.
4. Verificar que solo aparece "Crear Cotización de Compra" (la nueva) en el dropdown.
