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
      resultsEl.replaceChildren();
      if (hiddenInput) hiddenInput.value = "";
      return;
    }
    if (q.length < MIN_CHARS) {
      resultsEl.classList.add("hidden");
      resultsEl.replaceChildren();
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

  // La descripción viene del catálogo local, al que se le pueden agregar
  // claves: se pinta siempre con textContent, nunca con innerHTML (B07 en
  // docs/AUDITORIA.md).
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
      btn.append(crearOpcion(item.descripcion, item.clave));
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
