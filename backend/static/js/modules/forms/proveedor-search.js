document.addEventListener("DOMContentLoaded", () => {
  let debounceTimer;

  document.addEventListener("input", (event) => {
    if (!event.target.matches(".proveedor-search-input")) return;
    const wrapper = event.target.closest(".proveedor-search");
    if (!wrapper) return;
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => buscar(wrapper, event.target), 250);
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
      resultsEl.innerHTML = "";
      if (hiddenInput) hiddenInput.value = "";
      return;
    }

    try {
      const res = await fetch(`${url}?q=${encodeURIComponent(q)}`, { headers: { Accept: "application/json" } });
      if (!res.ok) return;
      const items = await res.json();
      mostrarResultados(items, input, hiddenInput, resultsEl);
    } catch (err) {
      if (window.App?.isDev) console.error("[proveedor-search]", err);
    }
  }

  function mostrarResultados(items, input, hiddenInput, resultsEl) {
    resultsEl.innerHTML = "";
    if (!items.length) {
      resultsEl.innerHTML = '<p class="px-3 py-2 text-xs text-gray-400">Sin resultados</p>';
      resultsEl.classList.remove("hidden");
      return;
    }
    items.forEach((item) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "block w-full text-left px-3 py-2 text-sm hover:bg-gray-50 border-b border-gray-50 last:border-0";
      btn.innerHTML = `<span class="font-mono text-xs text-gray-400">${item.rfc}</span> · ${item.nombre}`;
      btn.addEventListener("click", () => {
        hiddenInput.value = item.id;
        hiddenInput.dispatchEvent(new Event("change", { bubbles: true }));
        input.value = `${item.rfc} · ${item.nombre}`;
        resultsEl.classList.add("hidden");
      });
      resultsEl.appendChild(btn);
    });
    resultsEl.classList.remove("hidden");
  }
});
