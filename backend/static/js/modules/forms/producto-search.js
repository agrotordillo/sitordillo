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
    document.querySelectorAll(".producto-search-results:not(.hidden)").forEach((el) => {
      const wrapper = el.closest(".producto-search");
      if (wrapper && !wrapper.contains(event.target)) el.classList.add("hidden");
    });
  });

  async function buscar(wrapper, input) {
    const url = wrapper.dataset.productoSearchUrl;
    const resultsEl = wrapper.querySelector(".producto-search-results");
    const hiddenInput = wrapper.querySelector('input[type="hidden"]');
    const q = input.value.trim();

    if (!q) {
      resultsEl.classList.add("hidden");
      resultsEl.innerHTML = "";
      if (hiddenInput) hiddenInput.value = "";
      return;
    }

    if (q.length < MIN_CHARS) {
      resultsEl.classList.add("hidden");
      resultsEl.innerHTML = "";
      return;
    }

    mostrarCargando(resultsEl);

    try {
      const res = await fetch(`${url}?q=${encodeURIComponent(q)}`, { headers: { Accept: "application/json" } });
      if (!res.ok) return;
      const items = await res.json();
      mostrarResultados(items, input, hiddenInput, resultsEl);
    } catch (err) {
      if (window.App?.isDev) console.error("[producto-search]", err);
    }
  }

  function mostrarCargando(resultsEl) {
    resultsEl.innerHTML = '<p class="px-3 py-2.5 text-xs text-gray-400">Buscando…</p>';
    resultsEl.classList.remove("hidden");
  }

  function mostrarResultados(items, input, hiddenInput, resultsEl) {
    resultsEl.innerHTML = "";
    if (!items.length) {
      resultsEl.innerHTML = '<p class="px-3 py-2.5 text-xs text-gray-400">Sin resultados</p>';
      resultsEl.classList.remove("hidden");
      return;
    }
    items.forEach((item) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "flex w-full items-center gap-2 text-left px-3 py-2.5 text-sm hover:bg-primary-50 transition-colors";
      btn.innerHTML = `
        <span class="min-w-0 flex-1">
          <span class="block truncate text-gray-800">${item.nombre}</span>
          <span class="block text-xs text-gray-400 font-mono">${item.folio} · ${item.sku}</span>
        </span>`;
      btn.addEventListener("click", () => {
        hiddenInput.value = item.id;
        hiddenInput.dataset.precioCosto = item.precio_costo;
        hiddenInput.dispatchEvent(new Event("change", { bubbles: true }));
        input.value = `${item.folio} · ${item.nombre}`;
        resultsEl.classList.add("hidden");
      });
      resultsEl.appendChild(btn);
    });
    resultsEl.classList.remove("hidden");
  }
});
