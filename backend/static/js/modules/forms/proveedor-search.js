document.addEventListener("DOMContentLoaded", () => {
  // Debounce independiente por campo: ver nota en producto-search.js.
  const debounceTimers = new WeakMap();

  document.addEventListener("input", (event) => {
    if (!event.target.matches(".proveedor-search-input")) return;
    const input = event.target;
    const wrapper = input.closest(".proveedor-search");
    if (!wrapper) return;
    clearTimeout(debounceTimers.get(input));
    debounceTimers.set(input, setTimeout(() => buscar(wrapper, input), 250));
  });

  document.addEventListener("click", (event) => {
    document.querySelectorAll(".proveedor-search-results:not(.hidden)").forEach((el) => {
      const wrapper = el.closest(".proveedor-search");
      if (wrapper && !wrapper.contains(event.target)) el.classList.add("hidden");
    });
  });

  async function buscar(wrapper, input) {
    const url = wrapper.dataset.proveedorSearchUrl;
    const resultsEl = wrapper.querySelector(".proveedor-search-results");
    const hiddenInput = wrapper.querySelector('input[type="hidden"]');
    const q = input.value.trim();

    if (!q) {
      resultsEl.classList.add("hidden");
      resultsEl.replaceChildren();
      if (hiddenInput) hiddenInput.value = "";
      return;
    }

    mostrarCargando(resultsEl);

    try {
      const res = await fetch(`${url}?q=${encodeURIComponent(q)}`, { headers: { Accept: "application/json" } });
      if (!res.ok) return;
      const items = await res.json();
      mostrarResultados(items, input, hiddenInput, resultsEl);
    } catch (err) {
      if (window.App?.isDev) console.error("[proveedor-search]", err);
    }
  }

  // Los datos del proveedor los captura un usuario: se pintan siempre con
  // textContent, nunca con innerHTML, para que un nombre con HTML no se
  // ejecute en el navegador de quien busca (B07 en docs/AUDITORIA.md).
  function crearMensaje(texto) {
    const p = document.createElement("p");
    p.className = "px-3 py-2.5 text-xs text-gray-400";
    p.textContent = texto;
    return p;
  }

  function crearOpcion(principal, secundario) {
    const contenedor = document.createElement("span");
    contenedor.className = "min-w-0 flex-1";
    const linea1 = document.createElement("span");
    linea1.className = "block truncate text-gray-800";
    linea1.textContent = principal;
    const linea2 = document.createElement("span");
    linea2.className = "block text-xs text-gray-400 font-mono";
    linea2.textContent = secundario;
    contenedor.append(linea1, linea2);
    return contenedor;
  }

  function mostrarCargando(resultsEl) {
    resultsEl.replaceChildren(crearMensaje("Buscando…"));
    resultsEl.classList.remove("hidden");
  }

  function mostrarResultados(items, input, hiddenInput, resultsEl) {
    resultsEl.replaceChildren();
    if (!items.length) {
      resultsEl.replaceChildren(crearMensaje("Sin resultados"));
      resultsEl.classList.remove("hidden");
      return;
    }
    items.forEach((item) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "flex w-full items-center gap-2 text-left px-3 py-2.5 text-sm hover:bg-primary-50 transition-colors";
      btn.append(crearOpcion(item.nombre, item.rfc || "Sin RFC"));
      btn.addEventListener("click", () => {
        hiddenInput.value = item.id;
        // % base del proveedor: lo usan formset-rows.js (total) y
        // precio-alerta.js (costo de referencia). Se suma solo, igual que en
        // OrdenCompra.descuento_pct_total: NO se copia al campo "Descuento
        // proveedor (%)", que es solo el adicional de esta orden -copiarlo
        // ahí descontaba el base dos veces-. Una orden cargada desde CFDI
        // nunca lleva base (su precio ya viene neto).
        if (hiddenInput.dataset.sinDescuentoBase === "true") {
          hiddenInput.dataset.descuento = "0";
        } else if (item.descuento !== undefined) {
          hiddenInput.dataset.descuento = item.descuento;
        }
        hiddenInput.dispatchEvent(new Event("change", { bubbles: true }));
        input.value = `${item.rfc} · ${item.nombre}`;
        resultsEl.classList.add("hidden");
        // formset-rows.js solo recalcula con "input" de los campos de la
        // orden: se avisa para que el total refleje el % base del nuevo
        // proveedor de inmediato.
        document.querySelector(".fs-descuento-general")?.dispatchEvent(new Event("input", { bubbles: true }));
      });
      resultsEl.appendChild(btn);
    });
    resultsEl.classList.remove("hidden");
  }
});
