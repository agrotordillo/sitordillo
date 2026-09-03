document.addEventListener("DOMContentLoaded", () => {
  // Marca en rojo el precio unitario de una línea de compra cuando el
  // precio de referencia (precio_unitario menos SOLO el % base del
  // proveedor, ver Proveedor.descuento) supera el costo anterior
  // registrado del producto, y ofrece un botón para actualizar
  // Producto.precio_costo a ese valor — nunca al precio bruto de la
  // factura, y nunca al % combinado de la orden (que puede traer un
  // adicional variable por consumo/negociación que no debe mover el
  // costo de referencia ni el listado de precios).
  document.addEventListener("input", (event) => {
    if (!event.target.matches(".fs-precio")) return;
    evaluar(event.target);
  });

  document.addEventListener("change", (event) => {
    if (event.target.matches('input[name$="-producto"]')) {
      const row = event.target.closest(".formset-row");
      const precioInput = row?.querySelector(".fs-precio");
      if (precioInput) evaluar(precioInput);
    } else if (event.target.name === "proveedor") {
      // Cambió el proveedor (y con él, su % base) -> reevaluar todas las líneas.
      document.querySelectorAll(".fs-precio").forEach(evaluar);
    }
  });

  document.addEventListener("click", (event) => {
    if (!event.target.matches(".actualizar-costo-btn")) return;
    pedirConfirmacion(event.target);
  });

  document.querySelectorAll(".fs-precio").forEach(evaluar);

  function descuentoBaseProveedor() {
    const campo = document.querySelector('input[name="proveedor"]');
    const valor = campo ? parseFloat(campo.dataset.descuento) : 0;
    return isNaN(valor) ? 0 : valor;
  }

  function precioReferencia(precioBruto) {
    return precioBruto * (1 - descuentoBaseProveedor() / 100);
  }

  // Solo para texto visible al usuario (separador de miles); los valores
  // que se guardan en dataset.precioNeto y se mandan al backend siguen en
  // .toFixed(2) plano, sin comas, para que se puedan volver a parsear.
  function formatMoney(valor) {
    return valor.toLocaleString("es-MX", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function evaluar(precioInput) {
    const row = precioInput.closest(".formset-row");
    const productoInput = row?.querySelector('input[name$="-producto"]');
    const boton = row?.querySelector(".actualizar-costo-btn");
    const netoEl = row?.querySelector(".fs-precio-neto");
    const costoAnterior = parseFloat(productoInput?.dataset.precioCosto);
    const bruto = parseFloat(precioInput.value);
    const pct = descuentoBaseProveedor();
    const referencia = precioReferencia(bruto);

    if (netoEl) {
      netoEl.textContent = pct > 0 && !isNaN(referencia)
        ? `Costo ref. (−${pct}% proveedor): $${formatMoney(referencia)}`
        : "";
    }

    // Se compara redondeado a centavos: con floats crudos, un residuo de
    // punto flotante (p. ej. 207.42000000000002) puede marcar "excede"
    // aunque ambos valores se muestren idénticos en pantalla.
    const excede = !isNaN(costoAnterior) && !isNaN(referencia)
      && Math.round(referencia * 100) > Math.round(costoAnterior * 100);
    precioInput.classList.toggle("border-red-500", excede);
    precioInput.classList.toggle("text-red-600", excede);
    if (boton) {
      boton.classList.toggle("hidden", !excede);
      boton.textContent = "Actualizar precio de costo";
      boton.disabled = false;
      boton.dataset.precioNeto = isNaN(referencia) ? "" : referencia.toFixed(2);
    }
  }

  function pedirConfirmacion(boton) {
    const row = boton.closest(".formset-row");
    const productoInput = row?.querySelector('input[name$="-producto"]');
    const nombreInput = row?.querySelector(".producto-search-input");
    const costoNuevo = parseFloat(boton.dataset.precioNeto);
    if (!productoInput?.value || isNaN(costoNuevo)) return;

    const costoAnterior = parseFloat(productoInput.dataset.precioCosto || 0);
    window.dispatchEvent(new CustomEvent("confirmar-costo:abrir", {
      detail: {
        nombre: nombreInput?.value || "este producto",
        anterior: formatMoney(costoAnterior),
        nuevo: formatMoney(costoNuevo),
        onConfirmar: () => actualizarCosto(boton),
      },
    }));
  }

  async function actualizarCosto(boton) {
    const row = boton.closest(".formset-row");
    const productoInput = row?.querySelector('input[name$="-producto"]');
    const precioInput = row?.querySelector(".fs-precio");
    const costoNuevo = boton.dataset.precioNeto;
    if (!productoInput?.value || !costoNuevo) return;

    boton.disabled = true;
    boton.textContent = "Actualizando…";

    try {
      const res = await fetch(boton.dataset.url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": document.querySelector('input[name="csrfmiddlewaretoken"]')?.value || "",
        },
        body: JSON.stringify({ producto: productoInput.value, precio_costo: costoNuevo }),
      });
      if (!res.ok) throw new Error("respuesta no OK");
      const data = await res.json();
      productoInput.dataset.precioCosto = data.precio_costo;
      if (precioInput) evaluar(precioInput);
      boton.textContent = "Precio de costo actualizado ✓";
      boton.classList.remove("hidden");
      setTimeout(() => boton.classList.add("hidden"), 2000);
    } catch (err) {
      boton.disabled = false;
      boton.textContent = "No se pudo actualizar, intenta de nuevo";
      if (window.App?.isDev) console.error("[precio-alerta]", err);
    }
  }
});
