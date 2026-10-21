document.addEventListener("DOMContentLoaded", () => {
  // Calculo dinamico en la edicion de precios por lista (apps.products:
  // /productos/<id>/precios/). Replica en JS la misma formula que usa
  // ProductoPrecio en el backend (precio_sin_impuesto, importe_iva,
  // importe_ieps, importe_utilidad), mas la relacion costo <-> % utilidad:
  //   utilidad% = (precio_sin_impuesto - costo) / costo * 100
  //   precio_sin_impuesto = costo * (1 + utilidad% / 100)
  //
  // Arriba de la tabla tambien se editan el precio de costo y el de venta
  // ([data-precios-base], ver producto_precios_view):
  // - Al cambiar el costo aparece un boton para confirmar que se
  //   recalculen las filas con % de utilidad (igual que en la edicion del
  //   producto); al confirmarlo se recalculan aqui mismo en la tabla, que es
  //   lo que se guarda, y se puede deshacer. Sin confirmar, los precios se
  //   quedan como estan.
  // - El precio de venta es el de Publico general: cambiarlo cambia esa
  //   fila, y cambiar esa fila (a mano o por el recalculo) lo cambia a el.
  const tabla = document.querySelector("[data-producto-costo]");
  if (!tabla) return;

  const base = document.querySelector("[data-precios-base]");
  const campoCosto = base?.querySelector('input[name$="precio_costo"]');
  const campoVenta = base?.querySelector('input[name$="precio_venta"]');
  const confirmarCaja = base?.querySelector("[data-confirmar-costo]");
  const confirmarBoton = base?.querySelector("[data-confirmar-costo-boton]");
  const confirmarEstado = base?.querySelector("[data-confirmar-costo-estado]");
  const costoOriginal = parseFloat(base?.dataset.costoOriginal ?? tabla.dataset.productoCosto) || 0;

  const tasaIva = tabla.dataset.tipoIva === "gravado" ? (parseFloat(tabla.dataset.tasaIva) || 0) / 100 : 0;
  const tasaIeps = tabla.dataset.aplicaIeps === "true" ? (parseFloat(tabla.dataset.tasaIeps) || 0) / 100 : 0;
  const factor = (1 + tasaIeps) * (1 + tasaIva);

  // Precios que tenian las filas antes de confirmar el recalculo por costo,
  // para poder deshacerlo.
  let preciosAntesDeConfirmar = null;

  function costoActual() {
    const valor = parseFloat(campoCosto?.value);
    return isNaN(valor) ? costoOriginal : valor;
  }

  // Redondea hacia arriba (nunca hacia abajo) al múltiplo de $0.50 más
  // cercano -misma regla que apps.products.models.redondear_precio_venta-:
  // 7.32 y 7.51 suben a 7.50 y 8.00; 7.00 y 7.50 se quedan igual. Solo se
  // usa para el precio SUGERIDO al escribir el % de utilidad, nunca para
  // un precio con impuesto capturado directamente a mano.
  function redondearPrecioVenta(valor) {
    const pasos = Math.round((valor / 0.5) * 1e6) / 1e6; // corrige ruido de punto flotante
    return Math.ceil(pasos) * 0.5;
  }

  function filas() {
    return Array.from(tabla.querySelectorAll(".formset-row")).filter(
      (row) => !row.querySelector('input[name$="-DELETE"]')?.checked
    );
  }

  function esPublicoGeneral(row) {
    const lista = row.querySelector('select[name$="-lista_precio"]');
    const almacen = row.querySelector('select[name$="-almacen"]');
    return lista?.selectedOptions[0]?.text.trim().toUpperCase() === "PUBLICO" && !almacen?.value;
  }

  function filasConUtilidad() {
    return filas().filter((row) => row.querySelector(".pp-utilidad")?.value.trim() !== "");
  }

  document.addEventListener("input", (event) => {
    if (event.target.matches(".pp-precio")) {
      recalcularDesdePrecio(event.target);
    } else if (event.target.matches(".pp-utilidad")) {
      recalcularDesdeUtilidad(event.target);
    } else if (campoCosto && event.target === campoCosto) {
      alCambiarCosto();
    } else if (campoVenta && event.target === campoVenta) {
      alCambiarVenta();
    }
  });

  confirmarBoton?.addEventListener("click", () => {
    if (preciosAntesDeConfirmar) {
      deshacerRecalculo();
    } else {
      preciosAntesDeConfirmar = new Map(filasConUtilidad().map((row) => [row, row.querySelector(".pp-precio").value]));
      aplicarRecalculo();
    }
    pintarConfirmacion();
  });

  function fila(input) {
    return input.closest(".formset-row");
  }

  function actualizarCeldas(row, sinImpuesto) {
    const importeIeps = sinImpuesto * tasaIeps;
    const importeIva = (sinImpuesto + importeIeps) * tasaIva;
    const importeUtilidad = sinImpuesto - costoActual();

    setTexto(row, ".pp-sin-impuesto", sinImpuesto);
    setTexto(row, ".pp-iva", importeIva);
    setTexto(row, ".pp-ieps", importeIeps);
    setTexto(row, ".pp-utilidad-importe", importeUtilidad);
  }

  function setTexto(row, selector, valor) {
    const el = row?.querySelector(selector);
    if (el) {
      el.textContent = isFinite(valor)
        ? valor.toLocaleString("es-MX", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
        : "—";
    }
  }

  function sincronizarVenta(row) {
    if (!campoVenta || campoVenta.disabled || !esPublicoGeneral(row)) return;
    const precio = row.querySelector(".pp-precio")?.value;
    if (precio !== undefined && precio !== "") campoVenta.value = parseFloat(precio).toFixed(2);
  }

  function recalcularDesdePrecio(precioInput, { desdeVenta = false } = {}) {
    const row = fila(precioInput);
    const precio = parseFloat(precioInput.value);
    if (!row || isNaN(precio)) return;

    const sinImpuesto = precio / factor;
    actualizarCeldas(row, sinImpuesto);

    const utilidadInput = row.querySelector(".pp-utilidad");
    const costo = costoActual();
    if (utilidadInput && costo > 0) {
      utilidadInput.value = (((sinImpuesto - costo) / costo) * 100).toFixed(4);
    }
    if (!desdeVenta) sincronizarVenta(row);
  }

  function recalcularDesdeUtilidad(utilidadInput) {
    const row = fila(utilidadInput);
    const utilidad = parseFloat(utilidadInput.value);
    if (!row || isNaN(utilidad)) return;

    const sinImpuestoCrudo = costoActual() * (1 + utilidad / 100);
    const precioRedondeado = redondearPrecioVenta(sinImpuestoCrudo * factor);
    // Las celdas se muestran a partir del precio YA redondeado (no del
    // crudo): así la vista previa coincide con lo que se ve al recargar,
    // que siempre se calcula desde precio_con_impuesto hacia atrás.
    actualizarCeldas(row, precioRedondeado / factor);

    const precioInput = row.querySelector(".pp-precio");
    if (precioInput) {
      precioInput.value = precioRedondeado.toFixed(2);
    }
    sincronizarVenta(row);
  }

  // Sin cambiar precios ni % de utilidad: solo el importe de utilidad, que
  // depende del costo.
  function refrescarCeldas() {
    filas().forEach((row) => {
      const precio = parseFloat(row.querySelector(".pp-precio")?.value);
      if (!isNaN(precio)) actualizarCeldas(row, precio / factor);
    });
  }

  function costoCambio() {
    const valor = parseFloat(campoCosto?.value);
    return !isNaN(valor) && Math.round(valor * 10000) !== Math.round(costoOriginal * 10000);
  }

  function aplicarRecalculo() {
    preciosAntesDeConfirmar.forEach((_, row) => recalcularDesdeUtilidad(row.querySelector(".pp-utilidad")));
  }

  function deshacerRecalculo() {
    preciosAntesDeConfirmar.forEach((precio, row) => {
      const precioInput = row.querySelector(".pp-precio");
      precioInput.value = precio;
      const utilidad = row.querySelector(".pp-utilidad").value;
      recalcularDesdePrecio(precioInput);
      // El % de utilidad guardado se respeta: es el que se usará la próxima vez.
      row.querySelector(".pp-utilidad").value = utilidad;
    });
    preciosAntesDeConfirmar = null;
  }

  function alCambiarCosto() {
    if (preciosAntesDeConfirmar) {
      if (costoCambio()) aplicarRecalculo();
      else deshacerRecalculo();
    }
    refrescarCeldas();
    pintarConfirmacion();
  }

  function alCambiarVenta() {
    const row = filas().find(esPublicoGeneral);
    const precioInput = row?.querySelector(".pp-precio");
    if (!precioInput || campoVenta.value === "") return;
    precioInput.value = campoVenta.value;
    recalcularDesdePrecio(precioInput, { desdeVenta: true });
  }

  function pintarConfirmacion() {
    if (!confirmarCaja) return;
    const hayQueRecalcular = preciosAntesDeConfirmar ? preciosAntesDeConfirmar.size > 0 : filasConUtilidad().length > 0;
    confirmarCaja.hidden = !(costoCambio() && hayQueRecalcular);
    if (preciosAntesDeConfirmar) {
      const total = preciosAntesDeConfirmar.size;
      confirmarBoton.textContent = "Deshacer";
      confirmarEstado.textContent = `Se recalcularon ${total} precio${total === 1 ? "" : "s"} de lista con su % de utilidad (revísalos abajo).`;
      confirmarEstado.classList.replace("text-gray-400", "text-emerald-600");
    } else {
      confirmarBoton.textContent = "Actualizar también precios de lista";
      confirmarEstado.textContent = "Si no lo confirmas, solo se guarda el costo.";
      confirmarEstado.classList.replace("text-emerald-600", "text-gray-400");
    }
  }

  pintarConfirmacion();
});
