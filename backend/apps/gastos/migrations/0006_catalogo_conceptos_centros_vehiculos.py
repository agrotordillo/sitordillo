import random
import string
import uuid

from django.db import migrations
from django.utils.text import slugify

# Catálogo de conceptos de gasto tomado de
# datos/CATALOGO_DE_CUENTAS_CON_GUIA_CONTABILIZADORA.xlsx (hoja 1: lista de
# conceptos; hoja "Guía contabilizadora": qué registrar, ejemplos y
# criterio), organizado en grupos y ligado a la cuenta del plan de cuentas
# contable (datos/CATALAGO GASTO.xlsx). Reemplaza el catálogo de la
# migración 0003, que era el plan de cuentas a nivel subcuenta.
#
# Decisiones tomadas con el negocio al cargarlo:
# - Se conservan Gas, Recargos Fiscales, Servicios de Cable y Gastos Sobre
#   Compras aunque el catálogo nuevo no los traía.
# - "Derechos (predial)" se registra como "Impuesto Predial" (corrección
#   que marca la propia guía), en la cuenta 4101-017-002 del plan actual.
# - Se corrigen errores de captura del Excel (Aporataciones, Personales
#   Morales, isntalaciones, Sofware, mobliario, "Rerito x utilidad").
# - Los conceptos sin cuenta directa en el plan de cuentas (peajes, rastreo
#   satelital, vigilancia, fumigación, salud ocupacional, consumibles de
#   impresión, promoción) se ligan a la cuenta más cercana; los que no
#   tienen ninguna (consumo interno, retiros, transferencias) quedan sin
#   cuenta hasta que contabilidad la defina.
# - `naturaleza` (fijo/variable) es una propuesta editable, no viene del
#   Excel.
#
# Las categorías del catálogo anterior que no existen en el nuevo se
# borran si no tienen gastos; si ya tienen, se desactivan y se agrupan en
# "Catálogo anterior" para no perder el historial.

GASTO, INVERSION, NO_OPERATIVO = "gasto", "inversion", "no_operativo"

GRUPOS = [
    ("Nómina y prestaciones", GASTO),
    ("Impuestos patronales", GASTO),
    ("Combustibles y transporte", GASTO),
    ("Servicios", GASTO),
    ("Mantenimiento", GASTO),
    ("Materiales y consumibles", GASTO),
    ("Honorarios y arrendamientos", GASTO),
    ("Ventas, viajes y representación", GASTO),
    ("Otros gastos de operación", GASTO),
    ("Impuestos, derechos y multas", GASTO),
    ("Gastos financieros", GASTO),
    ("Depreciación y amortización", GASTO),
    ("Gastos personales", GASTO),
    ("Impuesto sobre la renta", GASTO),
    ("Activo fijo e inversiones", INVERSION),
    ("Movimientos no operativos", NO_OPERATIVO),
]
GRUPO_CATALOGO_ANTERIOR = "Catálogo anterior"

# (grupo, nombre, cuenta contable, naturaleza, qué registrar, ejemplos, criterio)
CONCEPTOS = [
    (
        'Nómina y prestaciones',
        'Sueldos y Salarios',
        '4101-001-001',
        'fijo',
        'Remuneración ordinaria pagada al personal por los servicios prestados.',
        'Sueldo semanal o quincenal; salario base.',
        'No incluir bonos, comisiones, vacaciones ni otras prestaciones si tienen cuenta propia.',
    ),
    (
        'Nómina y prestaciones',
        'Comisiones',
        '4101-001-002',
        'variable',
        'Remuneraciones variables al personal vinculadas a ventas, cobranza u objetivos.',
        'Comisión por ventas; comisión por recuperación de cartera.',
        'No confundir con comisiones bancarias.',
    ),
    (
        'Nómina y prestaciones',
        'Séptimo Día',
        '4101-001-003',
        'fijo',
        'Pago correspondiente al día de descanso semanal remunerado conforme al esquema de nómina.',
        'Pago de séptimo día a personal.',
        'Separarlo del sueldo ordinario si así lo controla la nómina.',
    ),
    (
        'Nómina y prestaciones',
        'Premios de Asistencia',
        '4101-001-004',
        'fijo',
        'Incentivos otorgados al trabajador por cumplimiento de asistencia.',
        'Bono o premio de asistencia.',
        'No registrar aquí premio de puntualidad.',
    ),
    (
        'Nómina y prestaciones',
        'Premios de Puntualidad',
        '4101-001-005',
        'fijo',
        'Incentivos otorgados por cumplimiento de horarios de entrada.',
        'Premio mensual/semanal de puntualidad.',
        'No mezclar con asistencia.',
    ),
    (
        'Nómina y prestaciones',
        'Despensa',
        '4101-001-006',
        'fijo',
        'Prestaciones de previsión social entregadas al personal para despensa.',
        'Vales de despensa; apoyo de despensa autorizado.',
        'No incluir alimentos de reuniones o atención a clientes.',
    ),
    (
        'Nómina y prestaciones',
        'Vacaciones',
        '4101-001-007',
        'fijo',
        'Remuneración correspondiente a días de vacaciones disfrutados por el trabajador.',
        'Pago de días de vacaciones.',
        'La prima vacacional debe ir separada.',
    ),
    (
        'Nómina y prestaciones',
        'Prima Vacacional',
        '4101-001-008',
        'fijo',
        'Prestación adicional pagada con motivo del periodo vacacional.',
        'Prima vacacional conforme a nómina.',
        'No registrar aquí el salario de los días de vacaciones.',
    ),
    (
        'Nómina y prestaciones',
        'Prima Dominical',
        '4101-001-009',
        'fijo',
        'Pago adicional por laborar en domingo cuando corresponda.',
        'Prima dominical de trabajador.',
        'No confundir con día festivo.',
    ),
    (
        'Nómina y prestaciones',
        'Días Festivos',
        '4101-001-010',
        'fijo',
        'Pagos asociados al trabajo realizado en días de descanso obligatorio, conforme a nómina.',
        'Pago por laborar en día festivo.',
        'Registrar según cálculo de nómina.',
    ),
    (
        'Nómina y prestaciones',
        'Gratificaciones',
        '4101-001-011',
        'variable',
        'Pagos extraordinarios al personal no clasificados como sueldo o bono específico.',
        'Gratificación extraordinaria autorizada.',
        'Debe documentarse el motivo; evitar usarla como cuenta genérica.',
    ),
    (
        'Nómina y prestaciones',
        'Primas de Antigüedad',
        '4101-001-012',
        'variable',
        'Pagos al trabajador derivados de la prima de antigüedad cuando proceda.',
        'Prima de antigüedad por terminación laboral.',
        'No confundir con indemnización.',
    ),
    (
        'Nómina y prestaciones',
        'Aguinaldo',
        '4101-001-013',
        'fijo',
        'Prestación anual pagada al personal por concepto de aguinaldo.',
        'Aguinaldo anual.',
        'Registrar separado de gratificaciones.',
    ),
    (
        'Nómina y prestaciones',
        'Indemnización',
        '4101-001-014',
        'variable',
        'Pagos derivados de terminación laboral que tengan naturaleza indemnizatoria.',
        'Indemnización por separación laboral.',
        'Debe sustentarse con cálculo y documentación laboral.',
    ),
    (
        'Nómina y prestaciones',
        'Otras Prestaciones',
        '4101-001-015',
        'variable',
        'Prestaciones al personal que no tengan una cuenta específica en el catálogo.',
        'Apoyo autorizado al personal; prestación adicional.',
        'Usar solo cuando no exista una categoría específica y describir el concepto.',
    ),
    (
        'Impuestos patronales',
        'Cuota IMSS',
        '4101-002-001',
        'fijo',
        'Cuotas patronales y demás importes a cargo de la empresa enterados al IMSS.',
        'Cuotas patronales IMSS.',
        'No incluir descuentos retenidos al trabajador como gasto propio.',
    ),
    (
        'Impuestos patronales',
        'Aportaciones al Infonavit',
        '4101-002-002',
        'fijo',
        'Aportaciones patronales al INFONAVIT.',
        'Aportación patronal de vivienda.',
        'Separar amortizaciones de créditos retenidas al trabajador.',
    ),
    (
        'Impuestos patronales',
        'Aportaciones al SAR',
        '4101-002-003',
        'fijo',
        'Aportaciones patronales al sistema de ahorro para el retiro.',
        'Aportaciones de retiro, cesantía y vejez según control de nómina.',
        'Registrar conforme a cédulas y pagos.',
    ),
    (
        'Impuestos patronales',
        'Impuesto Estatal sobre Nóminas',
        '4101-002-004',
        'fijo',
        'Impuesto local causado por las remuneraciones al trabajo personal.',
        'Impuesto sobre nóminas de Tabasco.',
        'No mezclar con cuotas de seguridad social.',
    ),
    (
        'Combustibles y transporte',
        'Combustibles y Lubricantes',
        '4101-003-000',
        'variable',
        'Combustible y lubricantes utilizados en vehículos o equipos de la operación.',
        'Gasolina; diésel; aceite para vehículo o maquinaria.',
        'Identificar vehículo/equipo y centro de costo cuando sea posible.',
    ),
    (
        'Combustibles y transporte',
        'Refacciones de equipo de transporte',
        '4101-006-000',
        'variable',
        'Partes y refacciones adquiridas para conservar o reparar vehículos.',
        'Balatas; filtros; bandas; piezas de suspensión.',
        'La mano de obra del taller puede ir a mantenimiento de transporte.',
    ),
    (
        'Combustibles y transporte',
        'Mantenimiento de equipo de transporte',
        '4101-041-000',
        'variable',
        'Mano de obra y servicios para conservar vehículos.',
        'Afinación; servicio mecánico; alineación; reparación.',
        'Refacciones pueden registrarse en su cuenta específica para análisis.',
    ),
    (
        'Combustibles y transporte',
        'Peajes de caseta',
        '4101-008-000',
        'variable',
        'Pagos de peaje derivados de traslados relacionados con la operación.',
        'Casetas por entrega; compras; traslado entre almacenes.',
        'Identificar motivo del viaje y, de ser posible, vehículo.',
    ),
    (
        'Combustibles y transporte',
        'Servicio de Rastreo Satelital',
        '4101-009-000',
        'fijo',
        'Servicios de GPS, localización o monitoreo vehicular.',
        'Mensualidad de GPS de unidades.',
        'Identificar unidad vehicular.',
    ),
    (
        'Combustibles y transporte',
        'Fletes y Acarreos',
        '4101-021-000',
        'variable',
        'Servicios de traslado de mercancías, materiales o bienes vinculados con la operación.',
        'Flete de proveedor; traslado de mercancía; acarreo de materiales.',
        'No confundir con peajes ni viáticos.',
    ),
    (
        'Servicios',
        'Servicio de Telefonía Móvil',
        '4101-009-000',
        'fijo',
        'Pagos por líneas celulares utilizadas para la operación.',
        'Plan celular empresarial; recarga autorizada.',
        'No incluir compra de teléfonos como servicio.',
    ),
    (
        'Servicios',
        'Servicio de Telefonía Fija',
        '4101-009-000',
        'fijo',
        'Pagos por líneas telefónicas fijas del establecimiento.',
        'Renta y consumo de línea fija.',
        'Separar internet si tiene cuenta propia y el proveedor lo desglosa.',
    ),
    (
        'Servicios',
        'Servicio de Internet',
        '4101-009-000',
        'fijo',
        'Pagos por conectividad de internet del establecimiento.',
        'Servicio mensual de internet; enlace empresarial.',
        'No incluir equipos de red adquiridos, salvo que la política los trate como gasto menor.',
    ),
    (
        'Servicios',
        'Servicios de Cable',
        '4101-027-000',
        'fijo',
        '',
        '',
        '',
    ),
    (
        'Servicios',
        'Agua',
        '4101-010-000',
        'fijo',
        'Consumo o suministro de agua utilizado por el establecimiento.',
        'Recibo de agua; compra de agua para uso operativo.',
        'Agua para hidratación del personal puede clasificarse en Salud Ocupacional si se desea medir ese fin.',
    ),
    (
        'Servicios',
        'Servicio de Energía Eléctrica',
        '4101-011-000',
        'fijo',
        'Consumo de energía eléctrica de establecimientos e instalaciones.',
        'Recibo CFE del almacén.',
        'Asignar al centro de costo que consume el servicio.',
    ),
    (
        'Servicios',
        'Gas',
        '4101-025-000',
        'variable',
        '',
        '',
        '',
    ),
    (
        'Servicios',
        'Servicio de Vigilancia',
        '4101-007-000',
        'fijo',
        'Servicios contratados para vigilancia y protección de instalaciones.',
        'Empresa de seguridad; guardia externo.',
        'Cámaras y alarmas corresponden a seguridad/mantenimiento según el caso.',
    ),
    (
        'Servicios',
        'Servicios de limpieza especializada (fumigación)',
        '4101-007-000',
        'variable',
        'Servicios especializados de higiene, fumigación, control de plagas o saneamiento.',
        'Fumigación; control profesional de roedores; desinfección especializada.',
        'Artículos de limpieza comprados directamente van en Artículos de Limpieza.',
    ),
    (
        'Servicios',
        'Recolección de Residuos Biológicos',
        '4101-044-000',
        'variable',
        'Servicios especializados para manejo, recolección y disposición de residuos biológicos o sanitarios.',
        'Recolección de RPBI cuando corresponda; disposición especializada.',
        'No incluir recolección ordinaria de basura.',
    ),
    (
        'Mantenimiento',
        'Mantenimiento y Conservación de edificios e instalaciones',
        '4101-015-000',
        'variable',
        'Trabajos para conservar inmuebles e instalaciones existentes en condiciones normales de uso.',
        'Pintura; reparación de techo; puertas; pisos; relleno periódico de patio de maniobras.',
        'Obras que amplíen o mejoren sustancialmente el inmueble deben evaluarse como proyecto/inversión.',
    ),
    (
        'Mantenimiento',
        'Mantenimiento eléctrico',
        '4101-015-000',
        'variable',
        'Reparación y conservación de instalaciones eléctricas existentes.',
        'Cambio de contactos; breakers; cableado dañado; reparación de luminarias.',
        'Instalación eléctrica de una ampliación nueva puede ser inversión/proyecto.',
    ),
    (
        'Mantenimiento',
        'Mantenimiento hidráulico y sanitario',
        '4101-015-000',
        'variable',
        'Reparación y conservación de tuberías, drenajes y servicios sanitarios.',
        'Reparación de fuga; WC; llaves; bomba; destape de drenaje.',
        'Obras nuevas o ampliaciones relevantes pueden ser inversión.',
    ),
    (
        'Mantenimiento',
        'Mantenimiento de climatización',
        '4101-015-000',
        'variable',
        'Servicios y refacciones para conservar equipos de aire acondicionado y ventilación.',
        'Servicio a minisplit; carga de gas; reparación de aire acondicionado.',
        'Compra de equipo nuevo puede requerir activo.',
    ),
    (
        'Mantenimiento',
        'Mantenimiento de maquinaria y equipo',
        '4101-015-000',
        'variable',
        'Reparaciones y servicios para conservar maquinaria/equipo operativo.',
        'Servicio preventivo; cambio de piezas; reparación de equipo.',
        'No incluir adquisición de maquinaria nueva.',
    ),
    (
        'Mantenimiento',
        'Mantenimiento de equipo de cómputo',
        '4101-015-000',
        'variable',
        'Servicios y reparaciones para conservar computadoras, impresoras y equipos informáticos.',
        'Reparación de PC; cambio de disco por falla; servicio a impresora.',
        'Software debe ir a mantenimiento/actualización de software o licencias según política.',
    ),
    (
        'Mantenimiento',
        'Mantenimiento de mobiliario de oficina',
        '4101-015-000',
        'variable',
        'Reparación y conservación de muebles existentes.',
        'Reparación de silla; escritorio; anaquel; mostrador.',
        'Mobiliario nuevo puede requerir activo o compra de mobiliario.',
    ),
    (
        'Mantenimiento',
        'Mantenimiento de seguridad',
        '4101-015-000',
        'variable',
        'Conservación y reparación de sistemas de seguridad.',
        'Reparación de cámaras; alarma; sensores; cerco eléctrico.',
        'Servicio de vigilancia humana va en Servicio de Vigilancia.',
    ),
    (
        'Mantenimiento',
        'Mantenimiento y Actualización de Software',
        '4101-022-000',
        'fijo',
        'Pagos para mantener, actualizar o dar soporte a software utilizado por la empresa.',
        'Actualización de sistema; soporte anual; mantenimiento de software.',
        'Licencias nuevas o desarrollos relevantes deben evaluarse por separado.',
    ),
    (
        'Materiales y consumibles',
        'Herramientas de Trabajo',
        '4101-030-000',
        'variable',
        'Herramientas menores y artículos reutilizables necesarios para las labores del personal.',
        'Martillos; pinzas; desarmadores; cutters; cintas métricas.',
        'Equipo de valor relevante o larga vida puede requerir tratamiento como activo.',
    ),
    (
        'Materiales y consumibles',
        'Artículos de Limpieza',
        '4101-013-000',
        'variable',
        'Materiales consumibles para limpieza e higiene de las instalaciones.',
        'Cloro; detergente; escobas; bolsas de basura; desinfectante.',
        'No incluir fumigación o limpieza especializada contratada.',
    ),
    (
        'Materiales y consumibles',
        'Papelería y Artículos de Oficina',
        '4101-014-000',
        'variable',
        'Materiales de oficina de consumo corriente.',
        'Hojas; carpetas; plumas; libretas; clips.',
        'Tóner y cartuchos deben ir a Consumibles de impresión.',
    ),
    (
        'Materiales y consumibles',
        'Consumibles de Impresión',
        '4101-014-000',
        'variable',
        'Insumos consumidos por impresoras y equipos de impresión.',
        'Tóner; cartuchos; tinta; cintas de impresión.',
        'No incluir reparación de impresoras.',
    ),
    (
        'Materiales y consumibles',
        'Accesorios y componentes de equipo de cómputo',
        '4101-043-000',
        'variable',
        'Componentes, periféricos y accesorios de cómputo de bajo valor o reposición.',
        'Disco duro/SSD; RAM; teclado; mouse; adaptadores.',
        'Si el componente se compra como parte de una reparación, puede asociarse a mantenimiento de cómputo; equipo mayor puede requerir activo.',
    ),
    (
        'Materiales y consumibles',
        'Empaques y Envolturas',
        '4101-028-000',
        'variable',
        'Material utilizado para empacar, proteger o entregar mercancía al cliente.',
        'Bolsas; cajas; cinta de empaque; película; envolturas.',
        'No incluir empaque que forme parte del inventario/costo del producto si la política lo trata de otra manera.',
    ),
    (
        'Materiales y consumibles',
        'Uniformes',
        '4101-023-000',
        'variable',
        'Vestimenta proporcionada al personal para identificación, seguridad o desempeño del trabajo.',
        'Camisas; pantalones; batas; uniformes institucionales.',
        'Equipo de protección especializado puede controlarse aparte si se desea.',
    ),
    (
        'Materiales y consumibles',
        'Salud Ocupacional',
        '4101-012-000',
        'variable',
        'Gastos destinados a prevención, primeros auxilios y protección de la salud del personal durante el trabajo.',
        'Botiquín; gasas; vendas; sueros/electrolitos para prevenir deshidratación; exámenes ocupacionales.',
        'No incluir gastos médicos personales ajenos al trabajo.',
    ),
    (
        'Materiales y consumibles',
        'Consumo Interno de Mercancía (animales)',
        '',
        'variable',
        'Costo de mercancía tomada del inventario y utilizada para animales vinculados con la operación del establecimiento.',
        'Alimento para pollos; alimento para gatos de control de roedores; desparasitante para aves.',
        "Debe generar salida de inventario por 'consumo interno'; no registrar como venta.",
    ),
    (
        'Honorarios y arrendamientos',
        'Honorarios a Personas Físicas',
        '4101-005-001',
        'fijo',
        'Servicios profesionales independientes prestados por personas físicas.',
        'Contador externo; abogado; consultor persona física.',
        'No incluir reparaciones o servicios operativos si existe una categoría más específica.',
    ),
    (
        'Honorarios y arrendamientos',
        'Honorarios a Personas Morales',
        '4101-005-002',
        'fijo',
        'Servicios profesionales especializados facturados por personas morales.',
        'Despacho contable; consultoría; asesoría de empresa.',
        'No confundir con mantenimiento, vigilancia u otros servicios específicos.',
    ),
    (
        'Honorarios y arrendamientos',
        'Arrendamientos a Personas Físicas',
        '4101-026-001',
        'fijo',
        'Rentas pagadas a personas físicas por inmuebles, equipos u otros bienes.',
        'Renta de local a persona física.',
        'Identificar contrato, inmueble/bien y centro de costo.',
    ),
    (
        'Honorarios y arrendamientos',
        'Arrendamientos a Personas Morales',
        '4101-026-002',
        'fijo',
        'Rentas pagadas a personas morales por inmuebles, equipos u otros bienes.',
        'Renta de bodega a empresa.',
        'Separar del leasing cuando exista cuenta específica.',
    ),
    (
        'Honorarios y arrendamientos',
        'Arrendamientos (Leasing)',
        '4101-026-004',
        'fijo',
        'Pagos derivados de contratos de arrendamiento financiero u operativo identificados como leasing.',
        'Leasing de vehículo o equipo.',
        'El tratamiento contable/fiscal debe validarse según el contrato.',
    ),
    (
        'Ventas, viajes y representación',
        'Atención a Clientes',
        '4101-024-000',
        'variable',
        'Cortesías y consumos destinados a atender clientes, proveedores o visitantes durante reuniones o visitas de negocio.',
        'Café; agua; refrescos; galletas; botanas para clientes.',
        "No incluir degustaciones de mercancía; conviene crear 'Promoción y degustación' para ellas.",
    ),
    (
        'Ventas, viajes y representación',
        'Viáticos y Gastos de Viaje',
        '4101-008-000',
        'variable',
        'Gastos necesarios del personal durante viajes de trabajo autorizados.',
        'Hospedaje; alimentos; transporte local durante comisión.',
        "No duplicar con 'Gastos de viaje y representación'; definir una sola política.",
    ),
    (
        'Ventas, viajes y representación',
        'Gastos de Viaje y Representación',
        '4101-042-000',
        'variable',
        'Gastos autorizados para representar a la empresa ante clientes, proveedores, eventos o reuniones fuera de la operación habitual.',
        'Comida de negocios; evento comercial; representación institucional.',
        "Existe posible duplicidad con Viáticos y Gastos de Viajes: recomiendo definir 'Viáticos' para viaje del trabajador y 'Representación' para atención/relación comercial.",
    ),
    (
        'Ventas, viajes y representación',
        'Propaganda y Publicidad',
        '4101-020-000',
        'variable',
        'Gastos destinados a promocionar la empresa, sus marcas, productos o servicios.',
        'Anuncios; lonas; publicidad digital; volantes; campañas.',
        'Conviene separar degustaciones/muestras si se desea medirlas.',
    ),
    (
        'Ventas, viajes y representación',
        'Promoción y Degustación',
        '4101-020-000',
        'variable',
        'Mercancía o consumibles utilizados para que clientes conozcan o prueben productos con finalidad comercial.',
        'Muestra de producto; degustación; porción promocional.',
        'Si sale del inventario, registrar también la salida por degustación/promoción.',
    ),
    (
        'Otros gastos de operación',
        'Capacitación a Empleados',
        '4101-029-000',
        'variable',
        'Gastos de cursos, talleres y formación del personal relacionados con sus funciones.',
        'Curso de ventas; capacitación técnica; taller de seguridad.',
        'No incluir viáticos del curso si se controlan por separado.',
    ),
    (
        'Otros gastos de operación',
        'Cuotas y Suscripciones',
        '4101-019-000',
        'fijo',
        'Pagos periódicos por membresías, afiliaciones, publicaciones o servicios de suscripción.',
        'Cámara empresarial; plataforma profesional; revista especializada.',
        'Software recurrente puede ir aquí o en software, según política consistente.',
    ),
    (
        'Otros gastos de operación',
        'Seguros y Fianzas',
        '4101-016-000',
        'fijo',
        'Primas de seguros y fianzas contratadas para proteger bienes, operaciones u obligaciones de la empresa.',
        'Seguro de vehículo; seguro de inmueble; fianza.',
        'Identificar póliza, vigencia y bien/obligación protegida.',
    ),
    (
        'Otros gastos de operación',
        'Cuota IEPS',
        '4101-004-000',
        'variable',
        'Importes identificados internamente como cuota o componente de IEPS cuando proceda su control separado.',
        'Cuota IEPS identificada en operación/documentación.',
        'Validar con contabilidad el tratamiento fiscal; no usar como cuenta genérica.',
    ),
    (
        'Otros gastos de operación',
        'Gastos Sobre Compras',
        '4114-001-000',
        'variable',
        '',
        '',
        '',
    ),
    (
        'Impuestos, derechos y multas',
        'Otros Impuestos y Derechos',
        '4101-017-000',
        'variable',
        'Impuestos o derechos a cargo de la empresa que no tengan cuenta específica.',
        'Derechos por licencias o permisos; impuesto local no clasificado.',
        'No registrar aquí predial, hospedaje o nómina si cuentan con categoría propia.',
    ),
    (
        'Impuestos, derechos y multas',
        'Impuesto sobre Hospedaje',
        '4101-017-001',
        'variable',
        'Impuesto local asociado a servicios de hospedaje cuando corresponda a la operación registrada.',
        'Impuesto sobre hospedaje desglosado en factura.',
        'No confundir con el costo del hospedaje del viajero.',
    ),
    (
        'Impuestos, derechos y multas',
        'Impuesto Predial',
        '4101-017-002',
        'fijo',
        'Impuesto municipal/local relacionado con la propiedad o posesión del inmueble, según corresponda.',
        'Pago anual o bimestral del predial del almacén.',
        'CORRECCIÓN: no es un derecho. Identificar el inmueble y centro de costo.',
    ),
    (
        'Impuestos, derechos y multas',
        'Refrendos',
        '4101-017-003',
        'fijo',
        'Pagos periódicos de refrendos, renovaciones o derechos similares requeridos para vehículos, permisos o registros.',
        'Refrendo vehicular; renovación anual de permiso cuando aplique.',
        'Especificar qué bien, permiso o registro se refrenda.',
    ),
    (
        'Impuestos, derechos y multas',
        'Recargos Fiscales',
        '4101-018-000',
        'variable',
        '',
        '',
        '',
    ),
    (
        'Impuestos, derechos y multas',
        'Multas de impuestos',
        '4101-039-002',
        'variable',
        'Sanciones impuestas por autoridades fiscales por incumplimientos.',
        'Multa fiscal.',
        'Mantener separada de impuestos ordinarios y recargos.',
    ),
    (
        'Impuestos, derechos y multas',
        'Gastos por Actualización de impuestos',
        '4101-039-003',
        'variable',
        'Importes de actualización derivados de contribuciones pagadas fuera de plazo u otros supuestos fiscales.',
        'Actualización de contribución extemporánea.',
        'Separar de recargos/multas si el sistema requiere análisis detallado.',
    ),
    (
        'Impuestos, derechos y multas',
        'Gastos de Ejecución',
        '4101-039-004',
        'variable',
        'Importes cobrados por la autoridad derivados de procedimientos de cobro o ejecución.',
        'Gastos de ejecución incluidos en línea de captura/resolución.',
        'Registrar con soporte de autoridad.',
    ),
    (
        'Gastos financieros',
        'Comisiones Bancarias',
        '4103-001-000',
        'variable',
        'Cargos cobrados por bancos por servicios financieros.',
        'Comisión por manejo de cuenta; SPEI; terminal; anualidad bancaria.',
        'No confundir con comisiones pagadas a vendedores.',
    ),
    (
        'Gastos financieros',
        'Intereses a Cargo Bancario',
        '4103-002-000',
        'variable',
        'Costo financiero por créditos, préstamos, sobregiros u otros financiamientos bancarios.',
        'Intereses de crédito bancario; intereses de línea de crédito.',
        'Separar capital pagado del crédito.',
    ),
    (
        'Gastos financieros',
        'Otros Gastos Financieros',
        '4103-003-000',
        'variable',
        'Costos financieros que no sean comisiones o intereses bancarios y estén debidamente identificados.',
        'Costo financiero específico no clasificado; diferencia financiera autorizada.',
        'Evitar usar como cuenta genérica; describir claramente el origen.',
    ),
    (
        'Gastos financieros',
        'Ajuste en centavos',
        '4103-004-000',
        'variable',
        'Diferencias mínimas de redondeo originadas en cobros, pagos o conciliaciones.',
        'Diferencia de $0.01 o $0.02 por redondeo.',
        'Usar solo para diferencias inmateriales de redondeo, no para cuadrar faltantes.',
    ),
    (
        'Gastos financieros',
        'Intereses por Financiamiento',
        '4103-005-000',
        'variable',
        '',
        '',
        '',
    ),
    (
        'Gastos financieros',
        'Intereses Ordinarios',
        '4103-006-000',
        'variable',
        '',
        '',
        '',
    ),
    (
        'Gastos financieros',
        'Comisiones TPV',
        '4103-080-000',
        'variable',
        '',
        '',
        '',
    ),
    (
        'Depreciación y amortización',
        'Depreciación de Edificio',
        '4104-001-000',
        'fijo',
        '',
        '',
        '',
    ),
    (
        'Depreciación y amortización',
        'Depreciación de Maquinaria y Equipo',
        '4104-002-000',
        'fijo',
        '',
        '',
        '',
    ),
    (
        'Depreciación y amortización',
        'Depreciación de Equipo de Reparto',
        '4104-003-000',
        'fijo',
        '',
        '',
        '',
    ),
    (
        'Depreciación y amortización',
        'Depreciación de Mobiliario y Equipo de Oficina',
        '4104-004-000',
        'fijo',
        '',
        '',
        '',
    ),
    (
        'Depreciación y amortización',
        'Depreciación de Equipo de Cómputo',
        '4104-005-000',
        'fijo',
        '',
        '',
        '',
    ),
    (
        'Depreciación y amortización',
        'Depreciación de Equipo de Comunicación',
        '4104-006-000',
        'fijo',
        '',
        '',
        '',
    ),
    (
        'Depreciación y amortización',
        'Depreciación de Otros Activos Fijos',
        '4104-007-000',
        'fijo',
        '',
        '',
        '',
    ),
    (
        'Depreciación y amortización',
        'Amortización de Gastos de Instalación',
        '4105-001-000',
        'fijo',
        '',
        '',
        '',
    ),
    (
        'Gastos personales',
        'Gastos Médicos',
        '4106-001-000',
        'variable',
        '',
        '',
        '',
    ),
    (
        'Gastos personales',
        'Retiros Personales',
        '',
        'variable',
        '',
        '',
        '',
    ),
    (
        'Gastos personales',
        'Tarjeta Personal',
        '4106-002-000',
        'variable',
        '',
        '',
        '',
    ),
    (
        'Gastos personales',
        'Colegiatura',
        '4106-003-000',
        'fijo',
        '',
        '',
        '',
    ),
    (
        'Gastos personales',
        'Retiro por Utilidad de Arrendamiento',
        '4106-004-000',
        'variable',
        '',
        '',
        '',
    ),
    (
        'Impuesto sobre la renta',
        'ISR por Actividad Empresarial',
        '4107-001-000',
        'variable',
        '',
        '',
        '',
    ),
    (
        'Impuesto sobre la renta',
        'ISR por Retención de Salarios',
        '4107-001-000',
        'variable',
        '',
        '',
        '',
    ),
    (
        'Impuesto sobre la renta',
        'ISR por Actividad de Arrendamiento',
        '4107-001-000',
        'variable',
        '',
        '',
        '',
    ),
    (
        'Activo fijo e inversiones',
        'Terrenos',
        '1201-000-000',
        'fijo',
        '',
        '',
        '',
    ),
    (
        'Activo fijo e inversiones',
        'Edificio',
        '1202-000-000',
        'fijo',
        '',
        '',
        '',
    ),
    (
        'Activo fijo e inversiones',
        'Mobiliario y Equipo de Oficina',
        '1204-000-000',
        'fijo',
        '',
        '',
        '',
    ),
    (
        'Activo fijo e inversiones',
        'Equipo de Transporte',
        '1206-000-000',
        'fijo',
        '',
        '',
        '',
    ),
    (
        'Activo fijo e inversiones',
        'Maquinaria y Equipo',
        '1208-000-000',
        'fijo',
        '',
        '',
        '',
    ),
    (
        'Activo fijo e inversiones',
        'Equipo de Cómputo',
        '1210-000-000',
        'fijo',
        '',
        '',
        '',
    ),
    (
        'Activo fijo e inversiones',
        'Equipo de Radiocomunicación',
        '1212-000-000',
        'fijo',
        '',
        '',
        '',
    ),
    (
        'Activo fijo e inversiones',
        'Depósitos en Garantía',
        '1303-000-000',
        'fijo',
        '',
        '',
        '',
    ),
    (
        'Movimientos no operativos',
        'Retiros y movimientos de la propietaria',
        '',
        'variable',
        'Salidas de efectivo que corresponden a la propietaria y no al gasto operativo del establecimiento.',
        'Retiro personal; compra personal pagada con caja de la empresa.',
        'No debe mezclarse con gastos operativos; identificar tratamiento contable correspondiente.',
    ),
    (
        'Movimientos no operativos',
        'Transferencias a proyectos u otros negocios',
        '',
        'variable',
        'Recursos que salen de un establecimiento para financiar proyectos u otras unidades/negocios.',
        'Aportación a proyecto; recurso para remodelar otro negocio; préstamo a otra unidad.',
        'No asumir que es gasto operativo. Identificar proyecto beneficiario y si es aportación, préstamo, anticipo o inversión.',
    ),
]

# Centros de costo reales encontrados en los Excel de pólizas y en la
# bitácora de combustible. Las sucursales se ligan a su almacén por nombre;
# si el almacén no existe en esta base, esa sucursal se omite.
# (código, nombre, tipo, nombre del almacén o None, descripción)
CENTROS = [
    ("BSU", "Bodega Sur", "sucursal", "BODEGA SUR", ""),
    ("LER", "Lerdo", "sucursal", "LERDO", ""),
    ("ALD", "Aldama", "sucursal", "ALDAMA", ""),
    ("TEC", "Tecolutilla", "sucursal", "TECOLUTILLA", ""),
    ("IQU", "Iquinuapa", "sucursal", "IQUINUAPA", ""),
    ("MER", "Mercado", "sucursal", "MERCADO", ""),
    ("HUI", "Huimanguillo", "sucursal", "HUIMANGUILLO", ""),
    ("ADM", "Administración", "administrativo", None, "Gasto corporativo o de oficina que no es de una sucursal."),
    ("MOB", "Mobiliario", "unidad_negocio", None, "Renta de mobiliario para eventos."),
    ("TRA", "Transportes Grappin", "unidad_negocio", None, "Flotilla y servicio de fletes."),
    ("ARR", "Arrendamiento", "unidad_negocio", None, "Renta de departamentos y locales."),
    ("PER", "Gasto personal", "personal", None, "Gastos personales de los dueños."),
    ("CPL", "Casa Playa", "personal", None, ""),
    ("SJU", "Salón de juntas", "personal", None, ""),
    ("PSV", "Sembrando Vida", "proyecto", None, ""),
    ("PVI", "Proyecto Vigalta", "proyecto", None, ""),
    ("PCI", "Proyecto Cítricos", "proyecto", None, ""),
    ("PJA", "Proyecto Jardín", "proyecto", None, ""),
    ("PBE", "Proyecto Becerros", "proyecto", None, ""),
    ("PBO", "Proyecto Bovino", "proyecto", None, ""),
    ("PCA", "Proyecto Cacao", "proyecto", None, ""),
    ("RAN", "Rancho (CDIS)", "proyecto", None, ""),
]

# Unidades que aparecen en la bitácora de combustible (CENTRO DE COSTO
# 2025.xlsx), con el nombre normalizado. Placas, responsable y centro
# habitual se completan desde la pantalla.
VEHICULOS = [
    ("Nissan 2011", "vehiculo"),
    ("Nissan 2014", "vehiculo"),
    ("Nissan 2016", "vehiculo"),
    ("Nissan 2023", "vehiculo"),
    ("March 2019", "vehiculo"),
    ("March 2023", "vehiculo"),
    ("March 2024", "vehiculo"),
    ("Isuzu 2018", "vehiculo"),
    ("Isuzu 2023", "vehiculo"),
    ("Kenworth 2010", "vehiculo"),
    ("Kenworth 2017", "vehiculo"),
    ("International", "vehiculo"),
    ("RAM 2009", "vehiculo"),
    ("RAM 4000", "vehiculo"),
    ("Renault 2024", "vehiculo"),
    ("Motocarro", "vehiculo"),
    ("Montacargas", "maquinaria"),
    ("Komatsu", "maquinaria"),
    ("Tractor", "maquinaria"),
    ("Desbrozadora", "maquinaria"),
    ("Chapeadora", "maquinaria"),
    ("Podadora", "maquinaria"),
    ("Motosierra", "maquinaria"),
    ("Planta de luz", "maquinaria"),
]


def _folio_unico(Model, prefijo):
    caracteres = string.ascii_uppercase + string.digits
    while True:
        candidato = f"{prefijo}-{''.join(random.choices(caracteres, k=8))}"
        if not Model.objects.filter(folio=candidato).exists():
            return candidato


def _slug_unico(Model, nombre):
    base = slugify(nombre) or str(uuid.uuid4())
    slug = base
    contador = 2
    while Model.objects.filter(slug=slug).exists():
        slug = f"{base}-{contador}"
        contador += 1
    return slug


def _crear(Model, prefijo, nombre, **campos):
    # apps.get_model() da el modelo histórico, sin los métodos de
    # BaseAbstractModel que generan folio/slug; se generan aquí a mano.
    return Model.objects.create(
        uuid=uuid.uuid4(),
        folio=_folio_unico(Model, prefijo),
        slug=_slug_unico(Model, nombre),
        nombre=nombre,
        **campos,
    )


def cargar_catalogo(apps, schema_editor):
    GrupoGasto = apps.get_model("gastos", "GrupoGasto")
    CategoriaGasto = apps.get_model("gastos", "CategoriaGasto")
    CentroCosto = apps.get_model("gastos", "CentroCosto")
    Vehiculo = apps.get_model("gastos", "Vehiculo")
    Almacen = apps.get_model("products", "Almacen")

    grupos = {}
    for orden, (nombre, clasificacion) in enumerate(GRUPOS, start=1):
        grupo = GrupoGasto.objects.filter(nombre=nombre).first()
        if grupo is None:
            grupo = _crear(GrupoGasto, "GRG", nombre, clasificacion=clasificacion, orden=orden)
        grupos[nombre] = grupo

    ids_vigentes = set()
    for grupo, nombre, cuenta, naturaleza, descripcion, ejemplos, criterio in CONCEPTOS:
        campos = {
            "grupo": grupos[grupo],
            "cuenta_contable": cuenta,
            "naturaleza": naturaleza,
            "descripcion": descripcion,
            "ejemplos": ejemplos,
            "criterio": criterio,
        }
        # Sin distinguir mayúsculas para reaprovechar la categoría anterior
        # del mismo nombre (p. ej. "Ajuste en Centavos") en vez de duplicarla.
        concepto = CategoriaGasto.objects.filter(nombre__iexact=nombre).first()
        if concepto is None:
            concepto = _crear(CategoriaGasto, "CAT", nombre, **campos)
        else:
            concepto.nombre = nombre
            for campo, valor in campos.items():
                setattr(concepto, campo, valor)
            concepto.is_active = True
            concepto.save()
        ids_vigentes.add(concepto.pk)

    anteriores = CategoriaGasto.objects.exclude(pk__in=ids_vigentes)
    anteriores.filter(gastos__isnull=True).delete()
    if anteriores.exists():
        grupo_anterior = GrupoGasto.objects.filter(nombre=GRUPO_CATALOGO_ANTERIOR).first() or _crear(
            GrupoGasto, "GRG", GRUPO_CATALOGO_ANTERIOR, clasificacion=GASTO, orden=99
        )
        anteriores.update(grupo=grupo_anterior, is_active=False)

    for codigo, nombre, tipo, nombre_almacen, descripcion in CENTROS:
        if CentroCosto.objects.filter(nombre=nombre).exists() or CentroCosto.objects.filter(codigo=codigo).exists():
            continue
        almacen = None
        if nombre_almacen:
            almacen = Almacen.objects.filter(nombre__iexact=nombre_almacen, tipo="sucursal").first()
            if almacen is None or CentroCosto.objects.filter(almacen=almacen).exists():
                continue
        _crear(CentroCosto, "CCO", nombre, codigo=codigo, tipo=tipo, almacen=almacen, descripcion=descripcion)

    for nombre, tipo in VEHICULOS:
        if not Vehiculo.objects.filter(nombre=nombre).exists():
            _crear(Vehiculo, "VEH", nombre, tipo=tipo)


def quitar_catalogo(apps, schema_editor):
    # Solo quita lo que esta migración creó y nadie usa todavía; el
    # catálogo anterior no se reconstruye (se regenera con la 0003 si se
    # regresa hasta antes de ella).
    Vehiculo = apps.get_model("gastos", "Vehiculo")
    CentroCosto = apps.get_model("gastos", "CentroCosto")
    CategoriaGasto = apps.get_model("gastos", "CategoriaGasto")
    Vehiculo.objects.filter(nombre__in=[n for n, _ in VEHICULOS], gastos__isnull=True).delete()
    CentroCosto.objects.filter(
        nombre__in=[c[1] for c in CENTROS], gastos__isnull=True, distribuciones_gasto__isnull=True,
        vehiculos__isnull=True,
    ).delete()
    CategoriaGasto.objects.filter(gastos__isnull=True).delete()
    CategoriaGasto.objects.update(grupo=None)


class Migration(migrations.Migration):

    dependencies = [
        ("gastos", "0005_grupos_conceptos_vehiculos"),
        ("products", "0027_almacen_puntoventa_numero"),
    ]

    operations = [
        migrations.RunPython(cargar_catalogo, quitar_catalogo),
    ]
