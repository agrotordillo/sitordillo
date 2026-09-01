document.addEventListener("DOMContentLoaded", () => {
  // Marca en rojo el precio unitario de una línea de compra cuando el
  // precio NETO (ya con el % de descuento general del proveedor aplicado,
  // ver OrdenCompra.descuento_pct) supera el costo anterior registrado del
  // producto, y ofrece un botón para actualizar Producto.precio_costo a ese
  // neto — nunca al precio bruto que se captura tal cual viene en la factura.
  document.addEventListener("input", (event) => {
    if (event.target.matches(".fs-precio")) {
      evaluar(event.target);
    } else if (event.target.id === "id_descuento_pct") {
      document.querySelectorAll(".fs-precio").forEach(evaluar);
    }
  });

  document.addEventListener("change", (event) => {
    if (!event.target.matches('input[name$="-producto"]')) return;
    const row = event.target.closest(".formset-row");
    const precioInput = row?.querySelector(".fs-precio");
    if (precioInput) evaluar(precioInput);
  });

  document.addEventListener("click", (event) => {
    if (!event.target.matches(".actualizar-costo-btn")) return;
    pedirConfirmacion(event.target);
  });

  document.querySelectorAll(".fs-precio").forEach(evaluar);

  function descuentoPct() {
    const campo = document.getElementById("id_descuento_pct");
    const valor = campo ? parseFloat(campo.value) : 0;
    return isNaN(valor) ? 0 : valor;
  }

  function precioNeto(precioBruto) {
    return precioBruto * (1 - descuentoPct() / 100);
  }

  function evaluar(precioInput) {
    const row = precioInput.closest(".formset-row");
    const productoInput = row?.querySelector('input[name$="-producto"]');
    const boton = row?.querySelector(".actualizar-costo-btn");
    const netoEl = row?.querySelector(".fs-precio-neto");
    const costoAnterior = parseFloat(productoInput?.dataset.precioCosto);
    const bruto = parseFloat(precioInput.value);
    const pct = descuentoPct();
    const neto = precioNeto(bruto);

    if (netoEl) {
      netoEl.textContent = pct > 0 && !isNaN(neto) ? `Neto (−${pct}%): $${neto.toFixed(2)}` : "";
    }

    const excede = !isNaN(costoAnterior) && !isNaN(neto) && neto > costoAnterior;
    precioInput.classList.toggle("border-red-500", excede);
    precioInput.classList.toggle("text-red-600", excede);
    if (boton) {
      boton.classList.toggle("hidden", !excede);
      boton.textContent = "Actualizar precio de costo";
      boton.disabled = false;
      boton.dataset.precioNeto = isNaN(neto) ? "" : neto.toFixed(2);
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
        anterior: costoAnterior.toFixed(2),
        nuevo: costoNuevo.toFixed(2),
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
