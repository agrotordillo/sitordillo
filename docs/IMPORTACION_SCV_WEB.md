# Importación del historial de scv_web

Procedimiento para cargar en sitordillo el historial del sistema anterior (scv_web):
ventas, compras, comisiones e inventario inicial. Se corre en **QA** con el corte del
26/10/2026 y se **repite completo** el día que se salga a producción.

## Qué se importa

| Qué | De dónde (scv_web) | A dónde (sitordillo) |
|---|---|---|
| Productos nuevos | `producto` y catálogos (volcado actual) | `Producto`, solo los SKU que no existen |
| Compras desde 2025-01-01 | `gasto` cuenta 2999 + `gasto_detalles` | `OrdenCompra` ya Recibida, sin lotes ni cuenta por pagar |
| Ventas desde 2025-01-01 | `documento` (notas y remisiones) + `documento_productos` + `documento_metodos_pago` | `Venta`, `VentaDetalle` (con costo histórico), `VentaPago` |
| Devoluciones | `documento` NOTA_DEVOLUCION | `DevolucionCliente` |
| Vendedores | `slz_users` | Usuarios **inactivos** (sin acceso) en `Venta.created_by` |
| Comisiones | `datos/COMISIONES P43.xlsx` (el más reciente) | Reglas de `ComisionColaboradorLinea` |
| Inventario inicial | entradas − salidas de `movimiento_almacen` | Un lote "INICIAL" por producto y almacén |

Lo histórico no mueve inventario, no genera cuentas por cobrar o pagar, ni facturas, ni turnos.

## Archivos que hay que copiar al servidor

La carpeta `datos/` no está en git: se copia a mano a `datos/` del servidor (junto a `backend/`).

- `datos/scv_web/*.tsv` y `datos/scv_web/catalogos/*.sql`: los genera `exportar_scv_web`.
- `datos/scv_web/correcciones_proveedores.csv`: RFC y régimen corregidos de 9 proveedores
  (salió de `compras_no_importadas_scv_web_corregido.xlsx`). **Sin este archivo esas 116
  compras no entran.**
- `datos/COMISIONES P43.xlsx` (o el Excel de comisiones más reciente: `--archivo`).

Si en el servidor no hay copia de scv_web, se pueden generar los archivos en otro equipo con
`exportar_scv_web` y copiar la carpeta completa.

## Pasos en QA

Desde `backend/`, con el entorno virtual del proyecto. Cada comando de importación acepta
`--dry-run` para revisar antes de escribir.

1. Respaldar la base de datos de QA (`pg_dump -Fc`).
2. Actualizar el código y aplicar migraciones:
   `python manage.py migrate`
3. Solo si QA tiene ventas/compras de prueba:
   `python manage.py depurar_transacciones_prueba` (revisa) y luego con `--aplicar`.
   Se niega si ya hay historial importado.
4. Exportar de la copia de scv_web (si se hace en el servidor):
   `python manage.py exportar_scv_web --mariadb <ruta>\mariadb.exe [--puerto 3307]`
5. Productos nuevos de scv_web:
   `python manage.py import_legacy_productos --solo-nuevos --directorio ../datos/scv_web/catalogos`
6. `python manage.py import_legacy_compras`
7. `python manage.py import_legacy_ventas` (unos 10 minutos)
8. Reglas de comisión (reemplazan solo las que vinieron de un Excel):
   `python manage.py import_comisiones_excel` (por defecto el P43) y, como MIGUEL no viene en el
   P43, `python manage.py import_comisiones_excel --archivo "../datos/COMISIONES P36.xlsx" --hojas "MIGUEL RMZ"`
9. `python manage.py import_legacy_existencias --corte 2026-10-26`

Todos se pueden repetir sin duplicar: lo ya importado se salta y solo se agrega lo que falte.
La excepción es el inventario inicial, que se niega si ya hay lotes (para agregar solo lo que
faltó, mientras no haya operaciones: `--completar`).

### Resultado esperado (corte 26/10/2026)

- Compras: 5,742 y 38,796 renglones.
- Ventas: 703,331 (quedan fuera 16 renglones de cantidad menor a 0.01, $7.68).
- Inventario inicial: 5,952 lotes.
- El reporte **Ventas por producto** del 01 al 27/10/2026, todos los almacenes, debe dar
  56,495 registros y $16,693,462.64 con impuesto (scv_web: $16,693,463.15; la diferencia
  son centavos de redondeo).

## Día del corte a producción

1. Cerrar operaciones en scv_web.
2. En el mismo momento: respaldo completo de scv_web **y** su reporte de existencias por
   almacén a Excel (para conciliar el inventario al 100 %).
3. Restaurar el respaldo en la copia de MariaDB y correr los pasos 4 a 9 con la nueva
   fecha de `--corte`, usando el mismo `correcciones_proveedores.csv`.
4. Activar los usuarios y almacenes que vayan a operar (los móviles y los vendedores se
   importan inactivos) y abrir turnos.

## Decisiones tomadas

- El CEDIS es el antiguo 02 BODEGA SUR: sus compras van al CEDIS; sus ventas y su existencia,
  a la sucursal BODEGA SUR.
- 07 CEDIS TORDILLO y los 10 móviles se crean como almacenes inactivos; la existencia de
  cada móvil queda en su móvil.
- Las facturas de scv_web no se importan: agrupan notas que ya se importan.
- Costos de venta absurdos en scv_web (más de 3 veces el precio) se dejan vacíos y el análisis
  usa el costo de catálogo.
- Comisiones sobre el importe sin IVA, igual que el Excel con el que se pagan.
- Lo vendido con precio especial de sucursal (Precio 6 a 9 en scv_web) queda marcado en el
  renglón (`VentaDetalle.precio_especial`) y, como en el Excel, solo comisiona en las reglas
  sobre toda la venta (FRANKLIN, JUAN DANIEL, JUAN CARLOS, JHONY en IQUINUAPA).
- Las reglas de comisión pueden ser sobre sus ventas, sus ventas en una sucursal (JHONY) o toda
  la venta de una sucursal (médicos; LUIS GERARDO y MIGUEL por la clase de producto que llevan su
  nombre en scv_web: JOSE MANUEL y MIGUEL RAMIREZ). Cada regla tiene días de la semana (el día de
  descanso de quien cobra sobre toda la sucursal lo cobra quien lo cubre) y vigencia para
  suplencias (TARACENA en las vacaciones de MIGUEL). `import_comisiones_excel` las recarga del
  Excel semanal y no toca las capturadas a mano; las suplencias de cada semana se capturan en
  Ventas → Comisiones por colaborador.
- Tres proveedores quedaron con RFC ficticio por decisión del negocio (HEPE1234567H0,
  PROD1234567H0, CUCA1234567H0).
