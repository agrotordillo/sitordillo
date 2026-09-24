document.addEventListener("DOMContentLoaded", () => {
  // Calculo dinamico en la edicion de precios por lista (apps.products:
  // /productos/<id>/precios/). Replica en JS la misma formula que usa
  // ProductoPrecio en el backend (precio_sin_impuesto, importe_iva,
  // importe_ieps, importe_utilidad), mas la relacion costo <-> % utilidad:
  //   utilidad% = (precio_sin_impuesto - costo) / costo * 100
  //   precio_sin_impuesto = costo * (1 + utilidad% / 100)
  const tabla = document.querySelector("[data-producto-costo]");
  if (!tabla) return;

  const costo = parseFloat(tabla.dataset.productoCosto) || 0;
  const tasaIva = tabla.dataset.tipoIva === "gravado" ? (parseFloat(tabla.dataset.tasaIva) || 0) / 100 : 0;
  const tasaIeps = tabla.dataset.aplicaIeps === "true" ? (parseFloat(tabla.dataset.tasaIeps) || 0) / 100 : 0;
  const factor = (1 + tasaIeps) * (1 + tasaIva);

  // Redondea hacia arriba (nunca hacia abajo) al múltiplo de $0.50 más
  // cercano -misma regla que apps.products.models.redondear_precio_venta-:
  // 7.32 y 7.51 suben a 7.50 y 8.00; 7.00 y 7.50 se quedan igual. Solo se
  // usa para el precio SUGERIDO al escribir el % de utilidad, nunca para
  // un precio con impuesto capturado directamente a mano.
  function redondearPrecioVenta(valor) {
    const pasos = Math.round((valor / 0.5) * 1e6) / 1e6; // corrige ruido de punto flotante
    return Math.ceil(pasos) * 0.5;
  }

  document.addEventListener("input", (event) => {
    if (event.target.matches(".pp-precio")) {
      recalcularDesdePrecio(event.target);
    } else if (event.target.matches(".pp-utilidad")) {
      recalcularDesdeUtilidad(event.target);
    }
  });

  function fila(input) {
    return input.closest(".formset-row");
  }

  function actualizarCeldas(row, sinImpuesto) {
    const importeIeps = sinImpuesto * tasaIeps;
    const importeIva = (sinImpuesto + importeIeps) * tasaIva;
    const importeUtilidad = sinImpuesto - costo;

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

  function recalcularDesdePrecio(precioInput) {
    const row = fila(precioInput);
    const precio = parseFloat(precioInput.value);
    if (!row || isNaN(precio)) return;

    const sinImpuesto = precio / factor;
    actualizarCeldas(row, sinImpuesto);

    const utilidadInput = row.querySelector(".pp-utilidad");
    if (utilidadInput && costo > 0) {
      utilidadInput.value = (((sinImpuesto - costo) / costo) * 100).toFixed(4);
    }
  }

  function recalcularDesdeUtilidad(utilidadInput) {
    const row = fila(utilidadInput);
    const utilidad = parseFloat(utilidadInput.value);
    if (!row || isNaN(utilidad)) return;

    const sinImpuestoCrudo = costo * (1 + utilidad / 100);
    const precioRedondeado = redondearPrecioVenta(sinImpuestoCrudo * factor);
    // Las celdas se muestran a partir del precio YA redondeado (no del
    // crudo): así la vista previa coincide con lo que se ve al recargar,
    // que siempre se calcula desde precio_con_impuesto hacia atrás.
    actualizarCeldas(row, precioRedondeado / factor);

    const precioInput = row.querySelector(".pp-precio");
    if (precioInput) {
      precioInput.value = precioRedondeado.toFixed(2);
    }
  }
});
