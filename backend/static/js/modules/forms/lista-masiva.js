document.addEventListener("DOMContentLoaded", () => {
  const boton = document.getElementById("lista-masiva-btn");
  const textarea = document.getElementById("lista-masiva-texto");
  const resumenEl = document.getElementById("lista-masiva-resumen");
  if (!boton || !textarea || !resumenEl) return;

  boton.addEventListener("click", () => agregarLista(boton, textarea, resumenEl));

  function parsearLineas(texto) {
    const filas = [];
    texto.split("\n").forEach((linea) => {
      const partes = linea.trim().split(/\s+/).filter(Boolean);
      if (partes.length < 2) return;
      const sku = partes[0];
      const cantidad = parseFloat(partes[1].replace(",", "."));
      if (!sku || isNaN(cantidad) || cantidad <= 0) return;
      filas.push({ sku, cantidad });
    });
    return filas;
  }

  function csrfToken() {
    return document.querySelector('input[name="csrfmiddlewaretoken"]')?.value || "";
  }

  function mostrarResumen(mensaje, esError) {
    resumenEl.textContent = mensaje;
    resumenEl.classList.toggle("text-red-600", Boolean(esError));
    resumenEl.classList.toggle("text-gray-500", !esError);
  }

  function llenarFila(fila, producto, cantidad) {
    const hiddenInput = fila.querySelector('input[name$="-producto"]');
    const searchInput = fila.querySelector(".producto-search-input");
    const cantidadInput = fila.querySelector(".fs-cantidad");
    const precioInput = fila.querySelector(".fs-precio");
    if (!hiddenInput) return;

    hiddenInput.value = producto.id;
    hiddenInput.dataset.precioCosto = producto.precio_costo;
    hiddenInput.dispatchEvent(new Event("change", { bubbles: true }));
    if (searchInput) searchInput.value = `${producto.sku} · ${producto.nombre}`;

    if (cantidadInput) {
      cantidadInput.value = cantidad;
      cantidadInput.dispatchEvent(new Event("input", { bubbles: true }));
    }
    if (precioInput && !precioInput.value && producto.precio_costo) {
      precioInput.value = producto.precio_costo;
      precioInput.dispatchEvent(new Event("input", { bubbles: true }));
    }
  }

  async function agregarLista(boton, textarea, resumenEl) {
    const filas = parsearLineas(textarea.value);
    if (!filas.length) {
      mostrarResumen("No se reconoció ninguna línea válida (esperado: SKU y cantidad separados por espacio o tabulador).", true);
      return;
    }

    boton.disabled = true;
    boton.textContent = "Agregando…";
    mostrarResumen("Buscando productos…", false);

    try {
      const res = await fetch(boton.dataset.url, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
        body: JSON.stringify({ skus: filas.map((f) => f.sku) }),
      });
      if (!res.ok) throw new Error("respuesta no OK");
      const data = await res.json();

      const porSku = {};
      (data.productos || []).forEach((p) => {
        porSku[p.sku.toUpperCase()] = p;
      });

      const formEl = document.querySelector('[x-data^="formsetRows"]');
      const alpineData = formEl && window.Alpine ? window.Alpine.$data(formEl) : null;
      if (!alpineData) throw new Error("no se encontró el formset de productos");

      let agregados = 0;
      const noEncontrados = [];
      filas.forEach(({ sku, cantidad }) => {
        const producto = porSku[sku.toUpperCase()];
        if (!producto) {
          noEncontrados.push(sku);
          return;
        }
        alpineData.addRow();
        const filasDom = formEl.querySelectorAll(".formset-row");
        const nuevaFila = filasDom[filasDom.length - 1];
        if (nuevaFila) llenarFila(nuevaFila, producto, cantidad);
        agregados += 1;
      });

      let mensaje = `Se agreg${agregados === 1 ? "ó" : "aron"} ${agregados} producto${agregados === 1 ? "" : "s"}.`;
      if (noEncontrados.length) mensaje += ` No encontrados: ${noEncontrados.join(", ")}.`;
      mostrarResumen(mensaje, agregados === 0);
      if (agregados) textarea.value = "";
    } catch (err) {
      mostrarResumen("No se pudo procesar la lista, intenta de nuevo.", true);
      if (window.App?.isDev) console.error("[lista-masiva]", err);
    } finally {
      boton.disabled = false;
      boton.textContent = "Agregar a la orden";
    }
  }
});
