document.addEventListener("DOMContentLoaded", () => {
  // Edición de producto: al cambiar el precio de costo aparece, debajo del
  // campo, un botón para confirmar que también se actualicen las listas de
  // precio con % de utilidad (Producto._recalcular_precios_por_utilidad).
  // La respuesta viaja en el campo oculto actualizar_precios_lista:
  //   confirmado    -> True: se recalculan las listas y el precio de venta
  //                    toma el de Público en general (también se precarga
  //                    aquí en el campo, con la misma fórmula y redondeo).
  //   sin confirmar -> False: solo se guarda el costo.
  // Si el producto no tiene listas con % de utilidad, el botón no aparece.
  const form = document.querySelector("form[data-costo-original]");
  if (!form) return;

  const datosEl = document.getElementById("precios-con-utilidad");
  const datos = datosEl ? JSON.parse(datosEl.textContent) : { filas: [], publico_general: null };
  const campoRespuesta = form.querySelector('input[name="actualizar_precios_lista"]');
  const campoCosto = form.querySelector("#id_precio_costo");
  const campoVenta = form.querySelector("#id_precio_venta");
  const contenedor = document.getElementById("confirmar-precios-lista");
  const boton = form.querySelector("[data-confirmar-precios-lista]");
  const estado = form.querySelector("[data-confirmar-precios-lista-estado]");
  if (!campoRespuesta || !campoCosto || !contenedor || !boton) return;

  const costoOriginal = parseFloat(form.dataset.costoOriginal);
  // Lo que tenía el precio de venta antes de confirmar, para regresarlo si
  // se deshace la confirmación (o deja de haber cambio de costo).
  let ventaPrevia = null;
  let confirmado = false;

  // Misma regla que apps.products.models.redondear_precio_venta: hacia
  // arriba al múltiplo de $0.50 (7.32 -> 7.50, 7.51 -> 8.00).
  function redondearPrecioVenta(valor) {
    const pasos = Math.round((valor / 0.5) * 1e6) / 1e6; // corrige ruido de punto flotante
    return Math.ceil(pasos) * 0.5;
  }

  // Tasas tomadas del mismo formulario: si en esta edición se cambió el IVA
  // o el IEPS, el backend recalcula ya con los valores nuevos.
  function factorImpuestos() {
    const tipoIva = form.querySelector("#id_tipo_iva")?.value;
    const tasaIva = tipoIva === "gravado" ? (parseFloat(form.querySelector("#id_tasa_iva")?.value) || 0) / 100 : 0;
    const aplicaIeps = form.querySelector("#id_aplica_ieps")?.checked;
    const tasaIeps = aplicaIeps ? (parseFloat(form.querySelector("#id_tasa_ieps")?.value) || 0) / 100 : 0;
    return (1 + tasaIeps) * (1 + tasaIva);
  }

  // Precio general de Público que tomará el precio de venta: el recalculado
  // si Público tiene % de utilidad, o el capturado a mano si no.
  function precioPublicoNuevo(costo) {
    const fila = datos.filas.find((f) => f.es_publico_general);
    if (fila) return redondearPrecioVenta(costo * (1 + parseFloat(fila.utilidad_pct) / 100) * factorImpuestos()).toFixed(2);
    return datos.publico_general;
  }

  function costoCambio() {
    const costo = parseFloat(campoCosto.value);
    return !isNaN(costo) && Math.round(costo * 10000) !== Math.round(costoOriginal * 10000);
  }

  function pintar() {
    const mostrar = datos.filas.length > 0 && costoCambio();
    contenedor.hidden = !mostrar;
    if (!mostrar) confirmado = false;

    // El precio de venta solo se toca mientras está confirmado; al dejar de
    // estarlo regresa a lo que tenía (aunque se haya capturado a mano).
    if (campoVenta && confirmado && ventaPrevia === null) ventaPrevia = campoVenta.value;
    if (campoVenta && !confirmado && ventaPrevia !== null) {
      campoVenta.value = ventaPrevia;
      ventaPrevia = null;
    }

    // Con JavaScript, solo se actualizan las listas si se confirmó con el
    // botón (el "True" con el que se pinta el campo es para cuando no hay JS).
    campoRespuesta.value = confirmado ? "True" : "False";
    boton.textContent = confirmado ? "✓ Se actualizarán los precios de lista" : "Actualizar también precios de lista";
    boton.classList.toggle("btn-primary", confirmado);
    boton.classList.toggle("btn-secondary", !confirmado);

    const publico = confirmado ? precioPublicoNuevo(parseFloat(campoCosto.value)) : null;
    if (estado) {
      estado.textContent = confirmado
        ? (publico ? `El precio de venta tomará el de Público: $${Number(publico).toLocaleString("es-MX", { minimumFractionDigits: 2 })}. Clic para deshacer.` : "Clic para deshacer.")
        : "Si no lo confirmas, solo se guarda el costo.";
    }
    if (campoVenta && confirmado && publico) campoVenta.value = publico;
  }

  campoCosto.addEventListener("input", pintar);
  form.addEventListener("change", (event) => {
    if (confirmado && event.target.matches("#id_tipo_iva, #id_tasa_iva, #id_aplica_ieps, #id_tasa_ieps")) pintar();
  });
  boton.addEventListener("click", () => {
    confirmado = !confirmado;
    pintar();
  });

  pintar();
});
