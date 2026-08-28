document.addEventListener("DOMContentLoaded", () => {
  const MIN_CHARS = 3;

  // Debounce independiente por campo: con varias líneas de producto en la
  // misma página (ej. formulario de orden de compra), un timer compartido
  // hace que escribir en una fila cancele la búsqueda pendiente de otra.
  const debounceTimers = new WeakMap();

  document.addEventListener("input", (event) => {
    if (!event.target.matches(".producto-search-input")) return;
    const input = event.target;
    const wrapper = input.closest(".producto-search");
    if (!wrapper) return;
    clearTimeout(debounceTimers.get(input));
    debounceTimers.set(input, setTimeout(() => buscar(wrapper, input), 250));
  });

  document.addEventListener("click", (event) => {
    ocultarTodos((wrapper) => !wrapper.contains(event.target));
  });

  // El panel de resultados se posiciona con position:fixed (ver
  // posicionarPanel) para no quedar recortado por el overflow-x-auto de la
  // tabla que lo contiene; al no seguir el flujo normal, hay que ocultarlo
  // si la página se desplaza o cambia de tamaño, para que no quede
  // flotando en un lugar que ya no corresponde al campo.
  window.addEventListener("scroll", () => ocultarTodos(), true);
  window.addEventListener("resize", () => ocultarTodos());

  function ocultarTodos(exceptoSi) {
    document.querySelectorAll(".producto-search-results:not(.hidden)").forEach((el) => {
      const wrapper = el.closest(".producto-search");
      if (!exceptoSi || (wrapper && exceptoSi(wrapper))) el.classList.add("hidden");
    });
  }

  function posicionarPanel(input, resultsEl) {
    const rect = input.getBoundingClientRect();
    resultsEl.style.position = "fixed";
    resultsEl.style.top = `${rect.bottom + 4}px`;
    resultsEl.style.left = `${rect.left}px`;
    resultsEl.style.width = `${rect.width}px`;
  }

  function mostrarMensaje(resultsEl, input, html) {
    resultsEl.innerHTML = html;
    posicionarPanel(input, resultsEl);
    resultsEl.classList.remove("hidden");
  }

  async function buscar(wrapper, input) {
    const url = wrapper.dataset.productoSearchUrl;
    const almacenFieldId = wrapper.dataset.productoSearchAlmacenField;
    const resultsEl = wrapper.querySelector(".producto-search-results");
    const hiddenInput = wrapper.querySelector('input[type="hidden"]');
    const q = input.value.trim();

    if (!q) {
      resultsEl.classList.add("hidden");
      resultsEl.innerHTML = "";
      if (hiddenInput) hiddenInput.value = "";
      return;
    }

    // Cuando el buscador está ligado a un almacén (ej. traspasos), solo
    // tiene sentido ofrecer productos con existencia ahí: se exige elegir
    // el almacén primero, y se manda como filtro en cada búsqueda.
    let almacenValue = "";
    if (almacenFieldId) {
      const almacenField = document.getElementById(almacenFieldId);
      almacenValue = almacenField ? almacenField.value : "";
      if (!almacenValue) {
        mostrarMensaje(resultsEl, input, '<p class="px-3 py-2.5 text-xs text-amber-600">Selecciona primero el almacén origen.</p>');
        return;
      }
    }

    if (q.length < MIN_CHARS) {
      resultsEl.classList.add("hidden");
      resultsEl.innerHTML = "";
      return;
    }

    mostrarMensaje(resultsEl, input, '<p class="px-3 py-2.5 text-xs text-gray-400">Buscando…</p>');

    try {
      const params = new URLSearchParams({ q });
      if (almacenValue) params.set("almacen", almacenValue);
      const res = await fetch(`${url}?${params.toString()}`, { headers: { Accept: "application/json" } });
      if (!res.ok) return;
      const items = await res.json();
      mostrarResultados(items, input, hiddenInput, resultsEl, Boolean(almacenValue));
    } catch (err) {
      if (window.App?.isDev) console.error("[producto-search]", err);
    }
  }

  function mostrarResultados(items, input, hiddenInput, resultsEl, filtradoPorAlmacen) {
    if (!items.length) {
      const mensaje = filtradoPorAlmacen
        ? "Sin existencia de este producto en el almacén origen"
        : "Sin resultados";
      mostrarMensaje(resultsEl, input, `<p class="px-3 py-2.5 text-xs text-gray-400">${mensaje}</p>`);
      return;
    }

    resultsEl.innerHTML = "";
    items.forEach((item) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "flex w-full items-center gap-2 text-left px-3 py-2.5 text-sm hover:bg-primary-50 transition-colors";
      const disponible = item.disponible !== undefined ? ` · disponible: ${item.disponible}` : "";
      btn.innerHTML = `
        <span class="min-w-0 flex-1">
          <span class="block truncate text-gray-800">${item.nombre}</span>
          <span class="block text-xs text-gray-400 font-mono">${item.folio} · ${item.sku}${disponible}</span>
        </span>`;
      btn.addEventListener("click", () => {
        hiddenInput.value = item.id;
        hiddenInput.dataset.precioCosto = item.precio_costo;

        // Sugiere el precio unitario de la línea de compra con el costo del
        // producto (solo si el campo está vacío, para no pisar un precio ya
        // capturado a mano).
        const row = hiddenInput.closest(".formset-row");
        const precioInput = row?.querySelector(".fs-precio");
        if (precioInput && !precioInput.value && item.precio_costo) {
          precioInput.value = item.precio_costo;
          precioInput.dispatchEvent(new Event("input", { bubbles: true }));
        }

        hiddenInput.dispatchEvent(new Event("change", { bubbles: true }));
        input.value = `${item.sku || item.folio} · ${item.nombre}`;
        resultsEl.classList.add("hidden");
      });
      resultsEl.appendChild(btn);
    });

    posicionarPanel(input, resultsEl);
    resultsEl.classList.remove("hidden");
  }
});
