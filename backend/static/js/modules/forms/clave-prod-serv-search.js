document.addEventListener("DOMContentLoaded", () => {
  const MIN_CHARS = 3;
  const debounceTimers = new WeakMap();

  document.addEventListener("input", (event) => {
    if (!event.target.matches(".clave-prod-serv-search-input")) return;
    const input = event.target;
    const wrapper = input.closest(".clave-prod-serv-search");
    if (!wrapper) return;
    clearTimeout(debounceTimers.get(input));
    debounceTimers.set(input, setTimeout(() => buscar(wrapper, input), 250));
  });

  document.addEventListener("click", (event) => {
    document.querySelectorAll(".clave-prod-serv-search-results:not(.hidden)").forEach((el) => {
      const wrapper = el.closest(".clave-prod-serv-search");
      if (wrapper && !wrapper.contains(event.target)) el.classList.add("hidden");
    });
  });

  async function buscar(wrapper, input) {
    const url = wrapper.dataset.claveProdServSearchUrl;
    const resultsEl = wrapper.querySelector(".clave-prod-serv-search-results");
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
      if (window.App?.isDev) console.error("[clave-prod-serv-search]", err);
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
          <span class="block truncate text-gray-800">${item.descripcion}</span>
          <span class="block text-xs text-gray-400 font-mono">${item.clave}</span>
        </span>`;
      btn.addEventListener("click", () => {
        hiddenInput.value = item.id;
        hiddenInput.dispatchEvent(new Event("change", { bubbles: true }));
        input.value = `${item.clave} · ${item.descripcion}`;
        resultsEl.classList.add("hidden");
      });
      resultsEl.appendChild(btn);
    });
    resultsEl.classList.remove("hidden");
  }
});
