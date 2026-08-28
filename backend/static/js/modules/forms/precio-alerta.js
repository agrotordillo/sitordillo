document.addEventListener("DOMContentLoaded", () => {
  // Marca en rojo el precio unitario de una línea de compra cuando supera
  // el costo anterior registrado del producto (apps.compras: orden de compra),
  // y ofrece un botón para actualizar Producto.precio_costo al nuevo valor.
  document.addEventListener("input", (event) => {
    if (!event.target.matches(".fs-precio")) return;
    evaluar(event.target);
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

  function evaluar(precioInput) {
    const row = precioInput.closest(".formset-row");
    const productoInput = row?.querySelector('input[name$="-producto"]');
    const boton = row?.querySelector(".actualizar-costo-btn");
    const costoAnterior = parseFloat(productoInput?.dataset.precioCosto);
    const precio = parseFloat(precioInput.value);
    const excede = !isNaN(costoAnterior) && !isNaN(precio) && precio > costoAnterior;
    precioInput.classList.toggle("border-red-500", excede);
    precioInput.classList.toggle("text-red-600", excede);
    if (boton) {
      boton.classList.toggle("hidden", !excede);
      boton.textContent = "Actualizar precio de costo";
      boton.disabled = false;
    }
  }

  function pedirConfirmacion(boton) {
    const row = boton.closest(".formset-row");
    const productoInput = row?.querySelector('input[name$="-producto"]');
    const precioInput = row?.querySelector(".fs-precio");
    const nombreInput = row?.querySelector(".producto-search-input");
    if (!productoInput?.value || !precioInput?.value) return;

    const costoAnterior = parseFloat(productoInput.dataset.precioCosto || 0);
    const costoNuevo = parseFloat(precioInput.value);
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
    if (!productoInput?.value || !precioInput?.value) return;

    boton.disabled = true;
    boton.textContent = "Actualizando…";

    try {
      const res = await fetch(boton.dataset.url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": document.querySelector('input[name="csrfmiddlewaretoken"]')?.value || "",
        },
        body: JSON.stringify({ producto: productoInput.value, precio_costo: precioInput.value }),
      });
      if (!res.ok) throw new Error("respuesta no OK");
      const data = await res.json();
      productoInput.dataset.precioCosto = data.precio_costo;
      evaluar(precioInput);
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
