# Auditoría de código · sitordillo

**Fecha:** 2026-10-01 · **Rama:** `main` (con los cambios sin commit de ese día)

## Alcance y método

- Se revisaron las 19 apps de `backend/apps` (modelos, servicios, vistas, formularios y API), la configuración (`config/settings`), los widgets JS de búsqueda y las plantillas que inyectan datos en JavaScript.
- Las 50 pruebas existentes (`inventario`, `pedidos`, `gastos`, `accounts`) pasan.
- Los hallazgos marcados **Confirmado** se reprodujeron con pruebas automáticas temporales (15 pruebas, fuera del repo). Los marcados **Por lectura** salen de leer el código y no se ejecutaron.
- Severidad: **Crítica** (dinero, fiscal o inventario quedan mal), **Alta** (seguridad o pérdida de datos), **Media** (regla de negocio rota o error 500 en un flujo normal), **Baja** (robustez o detalle).

Al corregir una fase, marca la casilla de cada bug, convierte su prueba de reproducción en una prueba real dentro del `tests.py` de la app, y anota el commit.

## Avance

| Fase | Estado | Notas |
|---|---|---|
| 1 · Dinero, fiscal e inventario | **Corregida** (2026-10-01, sin commit) | Requiere `manage.py migrate` (`compras.0012`, `facturacion.0005`). 88 pruebas en verde. |
| 2 · Seguridad y permisos | **Corregida** (2026-10-02, sin commit) | Migraciones sin SQL (`pagos.0007`, `cobros.0002`, `gastos.0013`). **Producción:** nginx ya no debe servir `/media/` directamente (ver B11). 115 pruebas en verde. |
| 3 · Concurrencia y doble envío | **Corregida** (2026-10-02, sin commit) | Migración `core.0001` (tabla `EnvioUnico`). **Producción:** programar `manage.py depurar_envios_unicos` a diario (cron). 127 pruebas en verde, 6 de concurrencia real. |
| 4 · Reglas de negocio | **Corregida** (2026-10-02, sin commit) | Migraciones `accounts.0021` (deja una sola principal por usuario, sin borrar asignaciones), `accounts.0022` (restricción en la BD) e `inventario.0010` (solo texto de ayuda). 152 pruebas en verde. |
| 5 · Configuración y robustez | **Corregida** (2026-10-02, sin commit) | Migración sin SQL (`products.0030`). **Producción:** en cada deploy correr `collectstatic` (ahora con manifiesto: si falta un estático, falla ahí y no en el navegador). 172 pruebas en verde. |

## Resumen

| ID | Bug | Severidad | Módulo | Evidencia |
|---|---|---|---|---|
| B01 ✅ | Orden de compra desde CFDI: el descuento del proveedor se resta dos veces | Crítica | compras / pagos | Confirmado |
| B02 ✅ | El total de órdenes ya capturadas cambia si se edita el descuento del proveedor | Crítica | compras | Confirmado |
| B03 ✅ | Corregir una recepción duplica el total de la orden y la deja "parcial" | Crítica | inventario / compras | Confirmado |
| B04 ✅ | Una factura se puede timbrar dos veces (CFDI duplicado ante el SAT) | Crítica | facturación | Confirmado |
| B05 ✅ | Conversión y ensamble de paquete truenan siempre (error 500) | Crítica | inventario | Confirmado |
| B06 ✅ | La devolución de cliente truena y reingresa productos distintos a los vendidos | Crítica | ventas | Confirmado (a) / Por lectura (b) |
| B07 ✅ | XSS almacenado en los buscadores de producto, cliente, proveedor y claves SAT | Alta | JS / facturación | Por lectura |
| B08 ✅ | Cualquier usuario autenticado cambia el costo de un producto vía API | Alta | api / products | Confirmado |
| B09 ✅ | Gastos: un usuario restringido abre cualquier gasto por URL | Alta | gastos | Confirmado |
| B10 ✅ | Costeo por producto: `?almacen=` salta la restricción de sucursal | Media | inventario | Confirmado |
| B11 ✅ | Los archivos subidos (`/media/`) no piden sesión | Alta | accounts / config | Confirmado |
| B12 ✅ | Redirección abierta con `?next=` | Baja | products / pagos | Por lectura |
| B13 ✅ | Con solo "ver pagos" se envían correos con cualquier adjunto | Media | pagos | Por lectura |
| B14 ✅ | Traspaso: enviar o recibir dos veces a la vez duplica inventario | Alta | traspasos | Por lectura |
| B15 ✅ | Convertir una cotización con doble clic genera dos ventas | Alta | cotizaciones | Por lectura |
| B16 ✅ | Pagos y cobros sin bloqueo permiten pagar de más | Media | pagos / cobros | Por lectura |
| B17 ✅ | El folio de facturas se asigna sin bloqueo | Media | facturación | Por lectura |
| B18 ✅ | Recepción de compra con doble envío da error 500; FIFO sin bloqueo | Baja | inventario | Por lectura |
| B19 ✅ | Convertir cotización o pedido acepta efectivo menor al total | Media | cotizaciones / pedidos | Confirmado |
| B20 ✅ | Órdenes de compra recibidas se pueden editar, borrar líneas o cancelar | Media | compras | Por lectura |
| B21 ✅ | Usuarios: dos sucursales principales; cambiar la principal exige dos guardados | Media | accounts | Confirmado |
| B22 ✅ | La merma de recepción no ajusta IVA/IEPS de la cuenta por pagar | Media | inventario / pagos | Por lectura (a confirmar) |
| B23 ✅ | Recepción de compra sin restricción de sucursal y sobre órdenes en borrador | Media | inventario | Por lectura (a confirmar) |
| B24 ✅ | El cobro dividido conserva el "efectivo recibido" | Baja | ventas | Por lectura |
| B25 ✅ | El ensamble rechaza un costo de paquete igual al de sus componentes | Baja | inventario | Por lectura |
| B26 ✅ | Producción: `STATICFILES_STORAGE` se ignora en Django 5.2 | Media | config | Confirmado |
| B27 ✅ | Abrir un turno ya abierto muestra un mensaje técnico | Baja | products | Confirmado |
| B28 ✅ | Parámetros GET/JSON no numéricos dan error 500 | Baja | varios | Por lectura |
| B29 ✅ | `ValidationError` no atrapada en vistas que llaman servicios (error 500) | Baja | varios | Por lectura |
| B30 ✅ | El análisis de compra por producto incluye órdenes canceladas | Baja | compras | Por lectura |
| B31 ✅ | El descuento en el CFDI está mal calculado (latente) | Baja | facturación | Por lectura |
| B32 ✅ | Endurecimiento menor (CSP, `x-data`, adjuntos, QZ) | Baja | varios | Por lectura |

Además hay 5 **decisiones pendientes** al final: comportamientos que podrían ser bugs o reglas de negocio, y que hay que confirmar antes de tocarlos.

---

## Fase 1 · Dinero, fiscal e inventario incorrectos

### B01 · Orden de compra desde CFDI: el descuento del proveedor se resta dos veces
- [x] Corregido (Fase 1) · **Crítica** · **Confirmado**
- **Solución:** se resuelve junto con B02. Las órdenes con `cfdi_uuid` congelan un % base de 0, así que `total` y `precio_neto` ya no restan nada. Al corregirlo apareció un segundo descuento doble, este en el JS: `proveedor-search.js` copiaba el % base del proveedor al campo de descuento *adicional* de toda orden nueva, y el backend ya lo suma por su cuenta. Se quitó esa copia. Pruebas en `apps/compras/tests.py`.
- **Dónde:** [compras/models.py:255](../backend/apps/compras/models.py#L255) (`descuento_pct_total`), [compras/models.py:279](../backend/apps/compras/models.py#L279) (`total`), [compras/services.py:164](../backend/apps/compras/services.py#L164)
- **Qué pasa:** `importar_cfdi_compra` guarda el precio ya neto y deja `descuento_pct=0` para no restar el descuento dos veces. Pero `descuento_pct_total` siempre suma `Proveedor.descuento`, así que `total` lo resta otra vez. `precio_neto` sí excluye las órdenes con `cfdi_uuid`; `total` no.
- **Ejemplo:** proveedor con 10 %, CFDI con un concepto de $90 neto → `subtotal` $90, `total` **$81**. La cuenta por pagar (`generar_cuenta_por_pagar` usa `orden.total`) queda $9 corta.
- **Propuesta:** en `descuento_pct_total`, si la orden tiene `cfdi_uuid` usar solo `descuento_pct`. Después, un script de diagnóstico que liste las cuentas por pagar ya generadas de órdenes CFDI con proveedor con descuento.

### B02 · El total de órdenes ya capturadas cambia si se edita el descuento del proveedor
- [x] Corregido (Fase 1) · **Crítica** · **Confirmado**
- **Solución:** campo nuevo `OrdenCompra.descuento_base_pct`. Se congela en `save()` al registrar la orden o al cambiarle el proveedor, y vale 0 en las de CFDI. Lo usan `descuento_pct_total`, `precio_neto` y el formulario (`data-descuento`, para que el total en pantalla cuadre). La migración `compras.0012` llenó las órdenes existentes con el % actual de su proveedor en un solo `UPDATE`; la tabla de proveedores solo se lee.
- **Dónde:** [compras/models.py:255](../backend/apps/compras/models.py#L255), `precio_neto` en [compras/models.py:377](../backend/apps/compras/models.py#L377)
- **Qué pasa:** el % base se lee del proveedor en vivo cada vez que se calcula el total. Editar el descuento del proveedor reescribe el total de todas sus órdenes históricas, el costo sugerido al recibir y el monto que se resincroniza en la cuenta por pagar al editar la orden.
- **Ejemplo:** orden de $100 con proveedor al 10 % → $90; el proveedor pasa a 20 % → la misma orden muestra **$80**.
- **Propuesta:** congelar el % base en la orden (campo nuevo, p. ej. `descuento_base_pct`, llenado al crearla) con migración de datos que copie el valor actual.

### B03 · Corregir una recepción duplica el total de la orden y la deja "parcial"
- [x] Corregido (Fase 1) · **Crítica** · **Confirmado**
- **Solución:** `corregir_recepcion` conserva la cantidad total ordenada. Lo recibido pasa a la línea correcta, y a la equivocada solo se le quita de lo ordenado lo que excede lo que ya se había pedido del producto correcto. Si la línea equivocada queda en 0 se elimina (decisión del usuario). Bloquea línea, orden y lote; no corrige unidades ya dadas de baja como merma; recalcula el estatus con `OrdenCompra.actualizar_estatus_por_recepcion()` (compartido con la recepción) y la cuenta por pagar con `pagos.services.resincronizar_cuenta_por_pagar()` (compartido con la merma y la edición de la orden). Pruebas en `apps/inventario/tests.py`.
- **Dónde:** [inventario/services.py:109](../backend/apps/inventario/services.py#L109) (`corregir_recepcion`), [compras/models.py:361](../backend/apps/compras/models.py#L361) (`cantidad_facturable`)
- **Qué pasa:** la línea del producto equivocado queda con `cantidad_recibida=0`. Con eso `cantidad_facturable` vuelve a la cantidad ordenada, así que se cobra completa, y la línea nueva del producto correcto también. Como la línea equivocada ya no está "recibida", la orden pasa a **Parcial** y la pantalla de recepción ofrece volver a recibir el producto equivocado. Tampoco se ajusta la cuenta por pagar si ya existía.
- **Ejemplo:** 10 piezas a $10 corregidas completas → subtotal pasa de **$100 a $200**, estatus `parcial`.
- **Propuesta:** reducir también `cantidad` de la línea equivocada (o quitarla si queda en 0) y recalcular la cuenta por pagar como ya hace `registrar_merma_recepcion`, rechazando si tiene pagos.

### B04 · Una factura se puede timbrar dos veces (CFDI duplicado ante el SAT)
- [x] Corregido (Fase 1) · **Crítica** · **Confirmado** (a) / **Por lectura** (b, c)
- **Solución:** un solo flujo para factura y factura global (`factura_service._timbrar`):
  1. Transacción corta que bloquea la fila, acepta solo Borrador o Error y la pasa al estatus nuevo **Timbrando**.
  2. Llamada a Facturama fuera de la transacción.
  3. Registro del resultado.
  Un rechazo seguro de Facturama deja la factura en Error (se puede reintentar). Un fallo incierto la deja en Timbrando y bloquea el reintento: timeout de lectura, conexión cortada, 502/504 o respuesta ilegible (`FacturamaError.incierto`). Si falla el guardado después de timbrar, se queda en Timbrando y el Id/UUID queda en el log. El Administrador puede liberarla con "Liberar para reintentar", y no antes de 2 minutos. La serie y el folio de Facturama van en campos aparte (`serie_facturama`, `folio_facturama`); el folio interno ya no se sobrescribe. Pantallas con `serie_folio`. `cancelar_factura` también bloquea y valida. Pruebas en `apps/facturacion/tests.py`.
- **Dónde:** [facturacion/views/factura_views.py:106](../backend/apps/facturacion/views/factura_views.py#L106), [facturacion/factura_service.py:168](../backend/apps/facturacion/factura_service.py#L168), [factura_views.py:253](../backend/apps/facturacion/views/factura_views.py#L253) (reintento de global)
- **Qué pasa:**
  - (a) `timbrar_factura_view` no valida el estatus: un POST sobre una factura **Timbrada** (o Cancelada) vuelve a llamar a Facturama y sobrescribe `facturama_id`/`uuid_fiscal`. El primer CFDI sigue vigente en el SAT y ya no queda registrado aquí.
  - (b) Sin bloqueo de fila: un doble clic en "Timbrar" (o en "Reintentar" de la global) con la factura en Borrador/Error timbra dos CFDI.
  - (c) Si algo falla después de que Facturama respondió bien (p. ej. `int(data["Folio"])`, o que el folio que devuelve Facturama choque con `unica_serie_folio`), el CFDI ya existe pero aquí queda sin timbrar, y el reintento genera otro.
- **Propuesta:** en el servicio, `select_for_update` + aceptar solo Borrador/Error. Guardar `facturama_id` y `uuid_fiscal` en cuanto llega la respuesta. Guardar el folio de Facturama en un campo aparte en vez de sobrescribir `numero_folio`.

### B05 · Conversión y ensamble de paquete truenan siempre (error 500)
- [x] Corregido (Fase 1) · **Crítica** · **Confirmado**
- **Solución:** se queda en 2 decimales (decisión del usuario). Nueva función `inventario.models.redondear_costo` (redondeo comercial). Conversión, ensamble, último costo y movimientos de almacén la usan explícitamente, y el valor generado se calcula con el mismo costo con el que queda el lote. Además, `Lote` redondea el costo en `clean_fields()` y en `save()`, como red de seguridad para cualquier otra ruta. Las vistas de conversión, ensamble, corrección y merma atrapan también `ValidationError` (helper `core.errores`).
- **Dónde:** [inventario/services.py:317](../backend/apps/inventario/services.py#L317) (conversión), [inventario/services.py:398](../backend/apps/inventario/services.py#L398) (ensamble). Viene del commit `79964f1` (precio de costo a 4 decimales).
- **Qué pasa:** `Lote.costo_unitario` admite 2 decimales y `Producto.precio_costo` 4. El valor llega de la BD como `Decimal('12.5000')` y `Lote.full_clean()` lo rechaza ("no más de 2 decimales"), aun con ceros a la derecha. Las vistas solo atrapan `ValueError`, así que el usuario ve un error 500. Afecta **toda** conversión y **todo** ensamble.
- **Propuesta:** `.quantize(TWO_PLACES)` al asignar el costo (como ya hace `ultimo_costo`), o subir `Lote.costo_unitario` a 4 decimales (decisión de diseño).

### B06 · La devolución de cliente truena y reingresa productos distintos a los vendidos
- [x] Corregido (Fase 1) · **Crítica** · (a) **Confirmado**, (b) **Por lectura**
- **Solución:** `registrar_devolucion` reconstruye lo devuelto a partir de `VentaDetalleLote` (lo que realmente salió), agrupado por producto real. Cada producto se reparte en proporción a lo devuelto de la línea, calculado como diferencia de acumulados, así que varias devoluciones parciales suman exacto lo vendido. El costo es el promedio con el que salió, redondeado. El lote de reingreso conserva el número de lote si salió de uno solo, y la caducidad más próxima de los lotes de origen. Las ventas sin registro de lotes usan la receta y el costo de catálogo. La vista muestra el error en vez de un 500 y no deja nada a medias. Pruebas en `apps/ventas/tests.py`.
- **Dónde:** [ventas/services.py:186](../backend/apps/ventas/services.py#L186) (`registrar_devolucion`)
- **Qué pasa:**
  - (a) `costo_promedio` no se redondea. Si la línea salió de lotes con costos distintos (1 a $10 + 2 a $11 = 10.6666…), `Lote.full_clean()` lo rechaza y la devolución da error 500. El respaldo `producto_real.precio_costo` tiene el mismo problema que B05.
  - (b) Reconstruye lo devuelto con `expandir_linea()` **al momento de devolver**, no con lo que de verdad salió (`VentaDetalleLote`). Si el paquete cambió de receta o ahora tiene existencia armada, se reingresan productos distintos a los vendidos (p. ej. se da de alta el "paquete" cuando se vendieron sus componentes).
- **Propuesta:** reconstruir desde `VentaDetalleLote`, agrupando por `lote.producto` y prorrateando la cantidad devuelta; `quantize` del costo.

---

## Fase 2 · Seguridad y permisos

### B07 · XSS almacenado en los buscadores
- [x] Corregido (Fase 2) · **Alta** · **Por lectura**
- **Solución:** los cinco buscadores construyen resultados y mensajes con `textContent` (helpers locales `crearOpcion`/`crearMensaje`). Ya no queda ningún `innerHTML` con datos: los demás solo clonan plantillas que renderiza el servidor. Agregar claves al catálogo SAT local exige poder crear o editar productos (`apps/products/permisos.py`, decisión del usuario); la búsqueda sigue abierta, pero el botón "Agregar" solo aparece con permiso. El cambio de JS se revisó con `node --check`, no en el navegador. La CSP con `'unsafe-inline'` sigue pendiente en B32.
- **Dónde:** `btn.innerHTML` en [producto-search.js:208](../backend/static/js/modules/forms/producto-search.js#L208), [cliente-search.js:62](../backend/static/js/modules/forms/cliente-search.js#L62), [proveedor-search.js:62](../backend/static/js/modules/forms/proveedor-search.js#L62), [clave-prod-serv-search.js:67](../backend/static/js/modules/forms/clave-prod-serv-search.js#L67), [clave-unidad-search.js:67](../backend/static/js/modules/forms/clave-unidad-search.js#L67); POST abierto en [catalogo_sat_views.py:21](../backend/apps/facturacion/views/catalogo_sat_views.py#L21) y [:52](../backend/apps/facturacion/views/catalogo_sat_views.py#L52)
- **Qué pasa:** los resultados se pintan interpolando nombre, RFC o descripción sin escapar. Un cliente, producto o proveedor llamado `<img src=x onerror=…>` ejecuta código en el navegador de quien lo busque (p. ej. el Administrador), con su sesión. La CSP permite `'unsafe-inline'`, así que no lo frena. Además, cualquier usuario autenticado puede crear o sobrescribir claves SAT por POST (`update_or_create`), y esas descripciones salen en el formulario de producto.
- **Propuesta:** construir los resultados con `textContent` (o una función `escapeHtml` compartida en `core/utils.js`) en los 5 widgets, y exigir un permiso para el POST del catálogo SAT.

### B08 · Cualquier usuario autenticado cambia el costo de un producto vía API
- [x] Corregido (Fase 2) · **Alta** · **Confirmado**
- **Solución:** nuevo `apps/api/permissions.py`. `ProductoActualizarCostoView` exige `products.change_producto` (`RequierePermisos`) y valida el valor con un serializer: rechaza texto, NaN, infinito, negativos y más de 4 decimales con 400. Las altas rápidas de marca, línea, clase y unidad exigen poder crear o editar productos (`PuedeEditarProductos`). Decisión del usuario: queda en "Compras - Completo" y Administrador; "Compras - Captura" ya no ve el botón de actualizar costo. Pruebas en `apps/api/tests.py`.
- **Dónde:** [api/views/products.py:246](../backend/apps/api/views/products.py#L246); altas rápidas en [products.py:32](../backend/apps/api/views/products.py#L32) a :62 y :273
- **Qué pasa:** las vistas usan el default `IsAuthenticated`. En la prueba, un usuario de "Mostrador y Cotización" cambió el costo de $100 a $1. `Producto.save()` ([products/models.py:766](../backend/apps/products/models.py#L766)) recalcula entonces los precios de las listas con % de utilidad, así que también cambia el precio de venta. Las altas rápidas de Marca, Línea, Clase y Unidad tampoco piden permiso.
- **Propuesta:** exigir `products.change_producto` (o el permiso de compras que corresponda) para el costo y `add_marca`/`add_linea`/`add_clase`/`add_unidadmedida` para las altas rápidas.

### B09 · Gastos: un usuario restringido abre cualquier gasto por URL
- [x] Corregido (Fase 2) · **Alta** · **Confirmado**
- **Solución:** `gastos.services.gastos_visibles(user)` es la única regla de alcance. La usan el listado, la edición (404 fuera de alcance) y la descarga de comprobantes (B11). Pruebas en `apps/gastos/tests.py`.
- **Dónde:** [gastos/views/gasto_views.py:115](../backend/apps/gastos/views/gasto_views.py#L115) (`GastoUpdateView` sin `get_queryset`)
- **Qué pasa:** el listado filtra por sucursal, pero `/gastos/<id>/editar/` no. En la prueba, un usuario de Gastos asignado a Sucursal A abrió un gasto de Dirección ("Bono confidencial", $50,000).
- **Propuesta:** `get_queryset` con el mismo filtro que `GastoListView`.

### B10 · Costeo por producto: `?almacen=` salta la restricción de sucursal
- [x] Corregido (Fase 2) · **Media** · **Confirmado**
- **Solución:** el almacén elegido se cruza con las sucursales visibles; uno ajeno o no numérico da un reporte vacío en vez de datos de otra sucursal o un error 500. Pruebas en `apps/inventario/tests.py`.
- **Dónde:** [inventario/views/costeo_views.py:33](../backend/apps/inventario/views/costeo_views.py#L33)
- **Qué pasa:** si viene `?almacen=`, se usa tal cual sin cruzarlo con `almacenes_visibles`. Un usuario de Sucursal A ve los costos de Sucursal B.
- **Propuesta:** intersectar el parámetro con las sucursales visibles.

### B11 · Los archivos subidos (`/media/`) no piden sesión
- [x] Corregido (Fase 2) · **Alta** · **Confirmado**
- **Solución:** `/media/` ya no está exento del login y, en todos los ambientes, pasa por `core.views.servir_archivo_protegido`. Un archivo solo se entrega si un registro registrado en `apps/core/archivos.py` lo tiene y el usuario puede ver ese registro, con el mismo permiso y sucursal que en su pantalla (decisión del usuario). Cada módulo declara sus archivos en el `ready()` de su `AppConfig`: pagos, cobros, gastos y productos. Sin permiso, o si el archivo no es de ningún registro, responde 404. Solo PDF e imágenes se muestran en el navegador; HTML, SVG o cualquier otro tipo se fuerza a descarga, con `nosniff` y `Cache-Control: private, no-store`. Los comprobantes nuevos se guardan en `<carpeta>/<uuid>/<nombre original>` (`RutaAleatoria`); los existentes siguen funcionando con su ruta. **Producción:** nginx no debe servir `/media/` por su cuenta. Si se quiere que nginx entregue los archivos, define `MEDIA_X_ACCEL_REDIRECT` con el prefijo de una location `internal` que apunte a `MEDIA_ROOT`; Django solo autoriza y responde con `X-Accel-Redirect`. Pruebas en `apps/core/tests.py` y `apps/gastos/tests.py`.
- **Dónde:** [accounts/middleware.py:4](../backend/apps/accounts/middleware.py#L4)
- **Qué pasa:** `MEDIA_URL` está exento del login. Con `DEBUG` Django sirve los archivos sin autenticación; en producción depende de nginx, y si los sirve quedan públicos. Son comprobantes de pagos, de cobros y de **gastos** (módulo confidencial), guardados con el nombre original del archivo, que suele ser predecible.
- **Propuesta:** servir media por una vista con permisos (con `X-Accel-Redirect` en nginx), quitar `MEDIA_URL` de los exentos y usar nombres aleatorios en `upload_to`.

### B12 · Redirección abierta con `?next=`
- [x] Corregido (Fase 2) · **Baja** · **Por lectura**
- **Solución:** `core.navegacion.url_de_regreso` acepta `next` solo si es del mismo sitio (la misma regla que el login de Django) y lo usan las cuatro vistas. También impide que el botón "Cancelar" lleve un `javascript:`. Pruebas en `apps/core/tests.py` y `apps/products/tests.py`.
- **Dónde:** [product_views.py:33](../backend/apps/products/views/product_views.py#L33) y [:90](../backend/apps/products/views/product_views.py#L90); [pago_views.py:265](../backend/apps/pagos/views/pago_views.py#L265) y [:298](../backend/apps/pagos/views/pago_views.py#L298)
- **Qué pasa:** después de guardar se redirige a lo que traiga `next` sin validarlo, así que un enlace preparado manda al usuario a un sitio externo.
- **Propuesta:** `url_has_allowed_host_and_scheme` antes de redirigir.

### B13 · Con solo "ver pagos" se envían correos con cualquier adjunto
- [x] Corregido (Fase 2) · **Media** · **Por lectura**
- **Solución:** el envío exige `pagos.add_pago` (decisión del usuario) y el modal de correo solo aparece con ese permiso. Límites: adjuntos PDF, XML, JPG o PNG validados por extensión y por contenido (`core.archivos.validar_archivo`), máximo 10 MB por archivo, 20 MB en total, 10 archivos y 10 correos en copia. El tipo MIME del adjunto se toma de la extensión validada, no del que declara el navegador. Pruebas en `apps/pagos/tests.py`.
- **Dónde:** [pagos/views/pago_views.py:293](../backend/apps/pagos/views/pago_views.py#L293)
- **Qué pasa:** `enviar_comprobante_view` pide `pagos.view_pago` y manda, desde la cuenta SMTP de la empresa, un correo a cualquier destinatario con cualquier adjunto, sin límite de tipo ni de tamaño.
- **Propuesta:** exigir `pagos.add_pago` o `change_pago` y validar tipo y tamaño de los adjuntos.

---

## Fase 3 · Concurrencia y doble envío

Los pedidos (`bloquear_pedido_abierto`) y los movimientos de almacén ya bloquean la fila y revalidan el estatus. Estos flujos no.

**Mecanismo común de la fase (doble envío):** decisión del usuario: token de un solo uso más botón deshabilitado, en ventas y conversiones, pagos y cobros, devoluciones y recepciones, y altas de pedido, gasto, orden de compra y traspaso.
- Cada formulario lleva `{% token_envio %}`.
- La vista lo reserva como llave primaria de `core.EnvioUnico` dentro de la misma transacción que guarda (`apps/core/envio_unico.py`). Un reenvío, aunque sea simultáneo, choca con esa llave y se manda al resultado ya guardado, con el aviso "ya se había registrado". Si el guardado falla, la reserva se revierte y el token sirve para reintentar.
- `modules/ui/envio-unico.js` deshabilita el botón de enviar de cualquier formulario con token.
- `depurar_envios_unicos` borra los tokens viejos.
- `PantallasProtegidasTests` verifica que las 12 pantallas traen su token.

### B14 · Traspaso: enviar o recibir dos veces a la vez duplica inventario
- [x] Corregido (Fase 3) · **Alta** · **Por lectura**
- **Solución:** `traspasos.services.bloquear_traspaso` relee la fila con `select_for_update` y revalida el estatus en enviar, recibir y cancelar (cancelar ahora también es atómico). Enviar además bloquea las existencias del origen y revalida el stock bajo el bloqueo. Hay prueba de concurrencia real: dos hilos reciben el mismo traspaso y solo se da de alta una vez; sin el bloqueo, la prueba falla.
- **Dónde:** [traspasos/services.py:34](../backend/apps/traspasos/services.py#L34) (`enviar_traspaso`), [:68](../backend/apps/traspasos/services.py#L68) (`recibir_traspaso`)
- **Qué pasa:** el estatus se revisa sobre el objeto en memoria. Dos POST simultáneos (doble clic o dos usuarios) pasan ambos: **recibir** crea dos veces los lotes en destino y **enviar** descuenta dos veces del origen.
- **Propuesta:** `Traspaso.objects.select_for_update().get(pk=…)` dentro de la transacción y revalidar el estatus.

### B15 · Convertir una cotización con doble clic genera dos ventas
- [x] Corregido (Fase 3) · **Alta** · **Por lectura**
- **Solución:** la conversión bloquea la cotización dentro de la transacción y revalida su estatus. Una segunda conversión simultánea, aunque traiga otro token (otra caja), muestra "ya fue convertida". Venta directa y conversión de pedido usan el token de un solo uso. Pruebas de concurrencia real con dos hilos, tanto con el mismo token como con tokens distintos: una sola venta.
- **Dónde:** [cotizaciones/views/conversion_views.py:56](../backend/apps/cotizaciones/views/conversion_views.py#L56) y [:125](../backend/apps/cotizaciones/views/conversion_views.py#L125)
- **Qué pasa:** se revisa `estatus == CONVERTIDA` fuera de la transacción y sin bloqueo, así que dos POST simultáneos crean dos ventas y descuentan inventario dos veces. `VentaCreateView` tampoco tiene protección contra doble envío.
- **Propuesta:** bloquear la cotización y revalidar dentro del `atomic` (igual que `bloquear_pedido_abierto`), y deshabilitar el botón al enviar.

### B16 · Pagos y cobros sin bloqueo permiten pagar de más
- [x] Corregido (Fase 3) · **Media** · **Por lectura**
- **Solución:** `pagos.services.bloquear_cuentas_por_pagar` (en orden de pk) y `cobros.services.bloquear_cuenta_por_cobrar`. El saldo se valida con la cuenta bloqueada en: registrar pago (individual y múltiple), editar pago, `registrar_pago`, registrar cobro y `registrar_cobro`. `generar_cuenta_por_pagar` también bloquea la orden: dos "Generar" a la vez ya no dan error 500. Registrar pago y cobro llevan token. Hay prueba de concurrencia real: dos pagos de $60 sobre un saldo de $100, uno se rechaza; sin el bloqueo, la prueba falla.
- **Dónde:** [pagos/views/pago_views.py:29](../backend/apps/pagos/views/pago_views.py#L29) (y pago múltiple y edición), [cobros/views/cobro_views.py:13](../backend/apps/cobros/views/cobro_views.py#L13)
- **Qué pasa:** el saldo se valida en `clean()` sin bloquear la cuenta, así que dos registros simultáneos pueden rebasar el saldo.
- **Propuesta:** `select_for_update` de la cuenta antes de `full_clean()`.

### B17 · El folio de facturas se asigna sin bloqueo
- [x] Corregido (Fase 3) · **Media** · **Por lectura**
- **Solución:** `Empresa.tomar_siguiente_folio` relee la fila con `select_for_update`. Si la factura no se crea, la transacción se revierte y el folio regresa, así que no quedan huecos; se quitó el "regreso" manual del folio, que sobraba. Además `generar_factura` bloquea la venta, y `generar_factura_global` el turno y sus ventas: ya no hay error 500 por la relación 1 a 1, ni una venta con factura individual y global a la vez. Prueba de concurrencia real: tres folios tomados a la vez salen 10, 11 y 12.
- **Dónde:** [facturacion/models.py:78](../backend/apps/facturacion/models.py#L78) (`tomar_siguiente_folio`)
- **Qué pasa:** dos facturas (o una factura y una global) generadas al mismo tiempo toman el mismo folio y la segunda falla con `IntegrityError` (error 500).
- **Propuesta:** leer `Empresa` con `select_for_update()` o incrementar con `F()`.

### B18 · Recepción de compra con doble envío da error 500; FIFO sin bloqueo
- [x] Corregido (Fase 3) · **Baja** · **Por lectura**
- **Solución:**
  - **Recepción:** bloquea la orden y cada línea, revalida lo pendiente bajo el bloqueo y avisa en la línea afectada si otra recepción se adelantó. Lleva token y atrapa `ValidationError`.
  - **FIFO:** `inventario.services.bloquear_existencias` bloquea de una vez, y en orden de pk, los lotes con existencia de todos los productos de la operación antes de planear la salida. Lo usan venta, apartado de pedido, envío de traspaso, conversión y ensamble (todos los componentes juntos), y las salidas de movimientos de almacén.
  - **Sin bloqueo mutuo:** `bloquear_lotes` hace lo mismo con los lotes ya conocidos al liberar o convertir un pedido y al cancelar un movimiento. Así dos operaciones no se bloquean entre sí (deadlock).
  - Hay prueba de concurrencia real: dos ventas simultáneas con existencia repartida en dos lotes; las dos se completan, cada una con un lote. Sin el bloqueo, una falla.
- **Dónde:** [recepcion_views.py:88](../backend/apps/inventario/views/recepcion_views.py#L88), [inventario/services.py:54](../backend/apps/inventario/services.py#L54)
- **Qué pasa:** el pendiente se valida antes del bloqueo; el segundo envío choca con `detalle.full_clean()`, que no se atrapa (error 500, sin corromper datos). `seleccionar_lotes_para_salida` planea con existencias sin bloquear: con concurrencia, una venta puede fallar con "cantidad negativa" aunque haya stock en otro lote.
- **Propuesta:** revalidar el pendiente después del `select_for_update`; bloquear los lotes al planear la salida.

---

## Fase 4 · Reglas de negocio y validaciones

### B19 · Convertir cotización o pedido acepta efectivo menor al total
- [x] Corregido (Fase 4) · **Media** · **Confirmado**
- **Solución:** `ventas.services.validar_efectivo_recibido(venta)` es la única regla y la usan las tres rutas: venta directa, conversión de cotización y conversión de pedido. Corre dentro de la transacción, con el total ya calculado, así que si falla no queda nada guardado: ni venta, ni movimientos, y el pedido sigue abierto con su mercancía apartada. Pruebas en `apps/ventas/tests.py` y `apps/pedidos/tests.py`.
- **Dónde:** [cotizaciones/views/conversion_views.py:125](../backend/apps/cotizaciones/views/conversion_views.py#L125), [pedidos/views/conversion_views.py:90](../backend/apps/pedidos/views/conversion_views.py#L90). La validación solo existe en [venta_views.py:223](../backend/apps/ventas/views/venta_views.py#L223).
- **Ejemplo:** total $500 y efectivo recibido $100 → la venta se guarda y el ticket muestra un cambio de **-$400**.
- **Propuesta:** pasar la validación a un servicio común que usen las tres rutas.

### B20 · Órdenes de compra recibidas se pueden editar, borrar líneas o cancelar
- [x] Corregido (Fase 4) · **Media** · **Por lectura**
- **Solución:** decisión del usuario: con mercancía recibida solo se editan precios y datos de la factura.
  - **Estatus:** a mano solo se elige Borrador, Enviada o Cancelada (Cancelada no aparece al crear). "Parcial" y "Recibida" los pone la recepción. Al guardar una orden con recepciones, el estatus se recalcula: si se sube lo pedido, pasa a Parcial. No se cancela una orden con cuenta por pagar.
  - **Orden con recepciones:** estatus, proveedor y almacén destino quedan fijos (campos deshabilitados; el buscador de proveedor queda de solo lectura).
  - **Línea recibida:** no cambia de producto, no se quita (no aparece el botón) y su cantidad no baja de lo recibido. Si llegó otro producto, se corrige en Lotes con "Corregir"; si llegó dañado, con "Reportar merma".
  - **Concurrencia:** el formulario toma una foto de lo recibido al cargar. Al guardar, con la orden bloqueada (el mismo candado que la recepción y que generar la cuenta por pagar), si algo cambió no se guarda nada y se pide volver a abrirla. Corrección y merma ahora bloquean primero la orden y luego la línea, el mismo orden que la recepción, para que no se esperen mutuamente.
  - `actualizar_estatus_por_recepcion` regresa a Enviada una orden a la que una corrección le quitó todo lo recibido (antes se quedaba en Recibida).
  - Pruebas en `apps/compras/tests.py`.
- **Dónde:** [compras/forms.py:59](../backend/apps/compras/forms.py#L59) (`estatus` editable), [orden_compra_views.py:152](../backend/apps/compras/views/orden_compra_views.py#L152)
- **Qué pasa:** el estatus es libre: una orden Recibida puede pasar a Borrador o Cancelada sin revertir inventario ni cuenta por pagar. Se pueden borrar líneas con lotes (`Lote.orden_compra_detalle` queda en NULL y se pierde la trazabilidad) o cambiar producto y precio de lo ya recibido.
- **Propuesta:** transiciones de estatus controladas, y bloquear borrar o cambiar producto en líneas con `cantidad_recibida > 0`.

### B21 · Usuarios: dos sucursales principales; cambiar la principal exige dos guardados
- [x] Corregido (Fase 4) · **Media** · **Confirmado** (a, b) / **Por lectura** (c)
- **Solución:**
  - El formset de sucursales del usuario valida sobre todas sus filas juntas que haya como máximo una principal, tanto en el alta como en la edición. La validación por fila contra la BD se apaga solo ahí; la pantalla suelta de asignaciones la conserva.
  - La regla vive en la BD: `UniqueConstraint` condicional `asu_una_principal_por_usuario`. Como una restricción condicional no se puede diferir, al guardar se desmarca primero la principal anterior; así se mueve de A a B en un solo guardado. Si dos personas guardan lo mismo a la vez, la BD rechaza el segundo guardado completo con un mensaje claro, no un error 500.
  - `accounts.0021` deja una sola principal por usuario antes de crear la restricción (la más antigua; las demás quedan como adicionales, sin borrar nada). En desarrollo no había duplicados.
  - Un Administrador no puede quitarse su propio "Es Administrador": el campo aparece deshabilitado con el aviso, y además se valida en el servidor. A otro Administrador sí se lo puede quitar.
  - Pruebas en `apps/accounts/tests.py`.
- **Dónde:** [accounts/models.py:85](../backend/apps/accounts/models.py#L85), [accounts/forms.py:194](../backend/apps/accounts/forms.py#L194)
- **Qué pasa:**
  - (a) Al **crear** un usuario con dos sucursales, ambas quedan como principales (el `clean()` no ve al usuario porque aún no existe), y `almacen_principal()` toma cualquiera.
  - (b) Al **editar**, mover la principal de A a B en un solo guardado da "ya tiene otra sucursal principal", porque A sigue principal en la BD mientras se valida B.
  - (c) Un Administrador puede quitarse su propio "Es Administrador" (desactivarse sí está bloqueado).
- **Propuesta:** validar en el `clean()` del formset que haya como máximo una principal, más una `UniqueConstraint` condicional en la BD; impedir la auto-degradación.

### B22 · La merma de recepción no ajusta IVA/IEPS de la cuenta por pagar
- [x] Corregido (Fase 4) · **Media** · **Por lectura (a confirmar con contabilidad)**
- **Solución:** decisión del usuario: se captura en la merma, con una sugerencia.
  - "Reportar merma" pide el IVA y el IEPS a descontar, que son los de la nota de crédito del proveedor. La pantalla propone lo que corresponde a la cantidad dañada y la propuesta sigue a la cantidad hasta que se edita a mano: precio × (1 − % de descuento de la orden), por las tasas del producto, con el IEPS dentro de la base del IVA.
  - Si se deja en blanco, el servidor aplica esa misma propuesta (`inventario.services.sugerir_impuestos_de_merma`). Nunca se descuenta más de lo que la orden trae: una orden sin IVA no descuenta nada.
  - Se restan de `OrdenCompra.iva`/`ieps` y se resincroniza la cuenta por pagar. El movimiento de merma anota cuánto se descontó.
  - Las retenciones no se ajustan solas. En recepciones parciales, el IVA es un dato de la factura y se corrige editando la orden, lo que B20 permite.
  - Pruebas en `apps/inventario/tests.py`.
- **Dónde:** [inventario/services.py:284](../backend/apps/inventario/services.py#L284), [compras/models.py:295](../backend/apps/compras/models.py#L295)
- **Qué pasa:** el subtotal baja por la merma, pero `iva`/`ieps` son montos capturados en el encabezado y no se recalculan: la cuenta por pagar queda con el IVA completo. Pasa lo mismo con las recepciones parciales.
- **Propuesta:** confirmar cómo factura el proveedor el ajuste; recalcular el IVA proporcional o pedir que se capture el ajustado.

### B23 · Recepción de compra sin restricción de sucursal y sobre órdenes en borrador
- [x] Corregido (Fase 4) · **Media** · **Por lectura (a confirmar)**
- **Solución:** decisión del usuario: primero debe estar Enviada.
  - `OrdenCompra.admite_recepcion`: Enviada o con algo ya recibido. Un Borrador manda a marcarla como Enviada; se revisa al abrir la pantalla y otra vez con la orden bloqueada al guardar. El listado solo muestra "Recibir" en Enviada y Parcial.
  - El almacén de cada línea solo ofrece las sucursales asignadas al usuario; sin asignaciones (Compras central, Administrador) ve todas.
  - Pruebas en `apps/inventario/tests.py`.
- **Dónde:** [recepcion_views.py:21](../backend/apps/inventario/views/recepcion_views.py#L21), [inventario/forms.py:20](../backend/apps/inventario/forms.py#L20)
- **Qué pasa:** cualquier usuario con `add_lote` recibe cualquier orden en cualquier almacén (el select no respeta `almacenes_visibles`), y se puede recibir una orden en Borrador.
- **Propuesta:** filtrar el almacén por sucursales visibles; decidir si una orden en Borrador puede recibirse.

### B24 · El cobro dividido conserva el "efectivo recibido"
- [x] Corregido (Fase 4) · **Baja** · **Por lectura**
- **Solución:** `VentaForm.clean()` descarta `forma_pago` y `efectivo_recibido` cuando se divide el cobro, antes de la validación del modelo. Así lo oculto ya no provoca el error "solo se captura con Efectivo" ni un cambio que no corresponde. La vista lo vuelve a limpiar como respaldo. El "recibido" de cada parte sigue en `VentaPago`. Prueba en `apps/ventas/tests.py`.
- **Dónde:** [venta_views.py:170](../backend/apps/ventas/views/venta_views.py#L170)
- **Qué pasa:** al dividir el cobro se limpia `forma_pago` pero no `efectivo_recibido`. Si quedó Efectivo seleccionado (oculto) con un monto, la venta guarda ese efectivo y el ticket calcula un cambio que no corresponde.
- **Propuesta:** `form.instance.efectivo_recibido = None` en esa rama.

### B25 · El ensamble rechaza un costo de paquete igual al de sus componentes
- [x] Corregido (Fase 4) · **Baja** · **Por lectura**
- **Solución:** decisión del usuario: el paquete puede valer igual o menos que sus partes, y se vende siempre con la lista PROMOCION.
  - **Ensamble:** el paquete entra al costo real de sus componentes, el valor consumido entre la cantidad redondeado a 2 decimales. Armar ya no se compara contra el costo de catálogo ni mueve el valor del inventario. La lista de ensambles muestra "Costo por paquete".
  - **Venta:** `products.services.resolver_precio_linea` cobra un paquete con PROMOCION sin importar la lista del cliente y registra esa lista en la línea, porque de ella depende la comisión. Si el paquete aún no tiene precio en PROMOCION, se resuelve como cualquier producto.
  - Lo usan venta, cotización, conversión de pedido y la API de búsqueda de ventas, que pinta el mismo precio que se cobra.
  - Pruebas en `apps/products/tests.py` e `apps/inventario/tests.py`.
- **Dónde:** [inventario/services.py:429](../backend/apps/inventario/services.py#L429)
- **Qué pasa:** el docstring dice que el costo del paquete debe reflejar "al menos" lo que costaron los componentes, pero `<=` rechaza la igualdad, que es el caso típico (combo = suma de sus partes).
- **Propuesta:** usar `<` en el ensamble (confirmar la regla).

---

## Fase 5 · Configuración, robustez y deuda técnica

### B26 · Producción: `STATICFILES_STORAGE` se ignora en Django 5.2
- [x] Corregido (Fase 5) · **Media** · **Confirmado**
- **Solución:** `prod.py` usa `STORAGES` (WhiteNoise con manifiesto y compresión). Al probarlo, `collectstatic` real destapó dos fallas que habrían roto el siguiente deploy:
  - `flowbite.min.js` apuntaba a un `.map` que nunca estuvo en el repo; se quitó esa referencia.
  - `static/src/input.css`, la fuente de Tailwind, se intentaba procesar como estático. `config/estaticos.py` lo excluye de `collectstatic` (sigue en su lugar para `npm run build:css`).
  - `EstaticosDeProduccionTests` lee el almacenamiento de `prod.py`, corre `collectstatic` y comprueba que cada `{% static %}` de las plantillas está en el manifiesto.
- **Dónde:** [config/settings/prod.py:15](../backend/config/settings/prod.py#L15)
- **Qué pasa:** desde Django 5.1 ese setting ya no existe y se ignora sin avisar. WhiteNoise no comprime ni versiona los estáticos, así que después de un deploy los navegadores pueden seguir usando JS y CSS viejos.
- **Propuesta:** `STORAGES = {"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"}, "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"}}`.

### B27 · Abrir un turno ya abierto muestra un mensaje técnico
- [x] Corregido (Fase 5) · **Baja** · **Confirmado**
- **Solución:** `violation_error_message` en la restricción: "Este punto de venta ya tiene un turno abierto." La migración `products.0030` no ejecuta SQL. Prueba en `apps/products/tests.py`.
- **Dónde:** [products/services.py:117](../backend/apps/products/services.py#L117)
- **Qué pasa:** `full_clean()` valida la `UniqueConstraint` antes del `save()` y muestra `No se cumple la restricción "trn_un_turno_abierto_por_punto_venta"` en lugar del mensaje que el código prepara para el `IntegrityError`.
- **Propuesta:** `violation_error_message` en la constraint.

### B28 · Parámetros GET/JSON no numéricos dan error 500
- [x] Corregido (Fase 5) · **Baja** · **Por lectura**
- **Solución:** `apps/core/parametros.py` es la única forma de leer parámetros: `id_valido`, `ids_validos`, `entero` (con rango), `fecha` (atrapa el 30 de febrero) y `filtrar_por_id`. Criterio: vacío no filtra, un id inválido no muestra nada y una fecha inválida se ignora.
  - **Dónde se aplica:** filtros de producto y sucursal, compras (listado y análisis), comisiones, cuentas por cobrar y por pagar, recibos, pago múltiple, lotes, existencias, kardex, movimientos con costo y de almacén, surtimiento, existencia sin movimiento, costeo, abrir turno y la API (buscar, precios por cliente, resolver SKU, subcategorías, promoción vigente; un cuerpo JSON que no es objeto ya no truena).
  - Los montos del pago múltiple rechazan `NaN` e `Infinity`.
  - De paso, el análisis anual y el de compra por producto ahora limitan los datos a las sucursales del usuario, no solo el selector (mismo criterio que B10).
  - `ParametrosInvalidosTests` pide cada pantalla con valores basura.
- **Dónde:** [core/filtros_producto.py:44](../backend/apps/core/filtros_producto.py#L44) y :54, costeo, kardex, existencia sin movimiento, surtimiento, análisis anual, `LoteListView ?orden=`, API (`?almacen=abc`, `ids` no numéricos).
- **Propuesta:** validar con `int()` o con un form antes de filtrar.

### B29 · `ValidationError` no atrapada en vistas que llaman servicios (error 500)
- [x] Corregido (Fase 5) · **Baja** · **Por lectura**
- **Solución:** todas las vistas que llaman servicios atrapan `ERRORES_DE_NEGOCIO` y muestran sus mensajes: movimientos de almacén (aplicar y cancelar), venta, conversiones de cotización y pedido, pedido (alta, edición, cancelación), traspasos (enviar, recibir, cancelar), facturas (generar, timbrar, liberar, cancelar, global), generar cuenta por pagar y edición de orden de compra. Ya no queda ninguna vista con solo `except ValueError`. Prueba en `apps/inventario/tests.py`.
- **Dónde:** [movimiento_almacen_views.py:223](../backend/apps/inventario/views/movimiento_almacen_views.py#L223) y [:236](../backend/apps/inventario/views/movimiento_almacen_views.py#L236); conversión, ensamble, devolución y recepción siguen el mismo patrón.
- **Qué pasa:** los servicios lanzan `ValidationError` desde `full_clean()`, pero las vistas solo atrapan `ValueError`.
- **Propuesta:** atrapar también `ValidationError` y mostrar sus mensajes.

### B30 · El análisis de compra por producto incluye órdenes canceladas
- [x] Corregido (Fase 5) · **Baja** · **Por lectura**
- **Solución:** excluye Borrador y Cancelada, igual que el análisis anual (constante `ESTATUS_SIN_COMPRA`). Prueba en `apps/compras/tests.py`.
- **Dónde:** [analisis_views.py:32](../backend/apps/compras/views/analisis_views.py#L32) (solo excluye borrador; el análisis anual excluye ambas).

### B31 · El descuento en el CFDI está mal calculado (latente)
- [x] Corregido (Fase 5) · **Baja** · **Por lectura**
- **Solución:** `_desglosar_linea` separa `importe` (sin impuestos, antes del descuento), `descuento` (sin impuestos, por diferencia para que cuadre al centavo) y `base` (sobre la que se calculan IVA e IEPS). Factura y factura global mandan `Subtotal = importe`, `Discount = descuento` y `Total = importe - descuento + impuestos`. Sin descuento el CFDI sale idéntico al de antes. D5 (aplicar `Cliente.descuento`) sigue pendiente; esto solo deja lista la parte fiscal. Pruebas en `apps/facturacion/tests.py`.
- **Dónde:** [factura_service.py:32](../backend/apps/facturacion/factura_service.py#L32) a :43 y [:80](../backend/apps/facturacion/factura_service.py#L80)
- **Qué pasa:** hoy el descuento siempre es 0, así que no se nota. Si se reactiva, `base` ya viene neta del descuento y se le vuelve a restar, y el descuento enviado incluye impuestos.
- **Propuesta:** corregirlo antes de habilitar descuentos en ventas: `Subtotal` = base bruta, `Discount` = descuento sin impuestos.

### B32 · Endurecimiento menor
- [x] Corregido (Fase 5) · **Baja** · **Por lectura**
- **Solución:**
  - **CSP** (decisión del usuario: quitar los scripts en línea): `script-src` ya no permite `'unsafe-inline'`. El script del ticket pasó a `static/js/pages/venta-ticket.js`, y los 8 `onsubmit`/`onchange`/`onclick` a atributos `data-confirmar`, `data-enviar-al-cambiar` y `data-imprimir` (`static/js/modules/ui/acciones.js`, que corre antes que `envio-unico.js` para que una confirmación rechazada no deshabilite el botón). `'unsafe-eval'` sigue porque Alpine lo necesita. `SinJavaScriptEnLineaTests` falla si una plantilla vuelve a traer un script o un `on*=`.
  - **`x-data`:** el concepto inicial del movimiento de almacén llega con `json_script`. Al revisar los demás apareció un caso real: `?subcategoria=` se pintaba dentro del `x-data` de los filtros de producto, y con un enlace preparado ejecutaba JavaScript. Ahora va con `escapejs` y los ids del contexto se normalizan.
  - **Comprobantes** (decisión del usuario: PDF, XML, JPG o PNG, 10 MB): `core.archivos.ComprobanteFormMixin` en pagos (individual, edición, múltiple), cobros y gastos. Revisa extensión y contenido, y solo de archivos recién subidos: editar un registro con un comprobante viejo no exige cambiarlo. El listado de gastos muestra el enlace al comprobante (descarga protegida, B11).
  - **QZ Tray:** firmar y obtener el certificado exige `ventas.view_venta` (el mismo permiso que el ticket), y solo se firma un hash SHA-256 en hexadecimal, que es lo único que QZ Tray 2.2 pide firmar. La llave ya no sirve para firmar cualquier texto.
  - Pruebas en `apps/core/tests.py`, `apps/pagos/tests.py` y `apps/ventas/tests.py`.
- [movimiento_almacen_form.html:29](../backend/apps/inventario/templates/inventario/movimiento_almacen_form.html#L29) mete `form.concepto.value` dentro de un `x-data` (código JS). Usar `json_script`.
- La CSP permite `'unsafe-inline'` y `'unsafe-eval'` ([base.py:245](../backend/config/settings/base.py#L245)); evaluar la build CSP de Alpine.
- Los comprobantes subidos (pagos, cobros, gastos) no validan tipo ni tamaño. El comprobante de gasto se sube pero no se muestra en ninguna pantalla.
- `qz_firmar_view` firma cualquier mensaje para cualquier usuario autenticado.

---

## Decisiones pendientes (confirmar antes de tocar)

- **D1 · Las devoluciones no tocan el dinero.** No reducen la cuenta por cobrar de una venta a crédito, no aparecen en el corte de caja y no generan nota de crédito (CFDI de egreso) si la venta estaba facturada. El texto de ayuda de "Reingresa a inventario" ([ventas/models.py:486](../backend/apps/ventas/models.py#L486)) dice que si no se reingresa se registra como merma, pero no se registra nada.
- **D2 · La factura global solo incluye ventas a "Público en general"** ([factura_service.py:361](../backend/apps/facturacion/factura_service.py#L361)). Las ventas a clientes registrados que no pidieron factura no entran a ningún CFDI. Confirmar con el contador.
- **D3 · Una factura cancelada no se puede volver a facturar** (relación 1 a 1 venta-factura), no hay sustitución (motivo 01, siempre se cancela con 02) y la factura global no tiene cancelación.
- **D4 · La conversión sube el valor del inventario.** El lote destino entra al costo de catálogo, que por regla es mayor al costo consumido; la diferencia aparece como valor nuevo. Confirmar si es intencional. *(El ensamble ya no: desde B25 entra al costo real de sus componentes.)*
- **D5 · `Cliente.descuento` se captura pero nunca se aplica.** `fijar_precios_autorizados` fija siempre el descuento en 0. *(Si se activa, el CFDI ya lo declara bien desde B31.)*
