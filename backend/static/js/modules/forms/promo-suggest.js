document.addEventListener("DOMContentLoaded", () => {
  const rows = document.querySelector("[data-promo-url]");
  if (!rows) return;

  const url = rows.dataset.promoUrl;
  const proveedorSelect = document.getElementById("id_proveedor");
  const fechaInput = document.getElementById("id_fecha_orden");

  rows.addEventListener("change", (event) => {
    if (!event.target.matches('select[name$="-producto"]')) return;
    checkPromo(event.target);
  });

  async function checkPromo(productoSelect) {
    const row = productoSelect.closest(".formset-row");
    const hint = row?.querySelector(".promo-hint");
    if (hint) {
      hint.textContent = "";
      hint.classList.add("hidden");
    }

    const proveedorId = proveedorSelect?.value;
    const fecha = fechaInput?.value;
    const productoId = productoSelect.value;
    if (!proveedorId || !fecha || !productoId) return;

    try {
      const params = new URLSearchParams({ producto: productoId, proveedor: proveedorId, fecha });
      const res = await fetch(`${url}?${params}`, { headers: { Accept: "application/json" } });
      if (!res.ok) return;
      const data = await res.json();
      if (!data.vigente) return;

      const precioInput = row?.querySelector(".fs-precio");
      if (precioInput && !precioInput.value) {
        precioInput.value = data.precio_sugerido;
        precioInput.dispatchEvent(new Event("input", { bubbles: true }));
      }
      if (hint) {
        hint.textContent = `Promoción vigente: $${data.precio_sugerido}`;
        hint.classList.remove("hidden");
      }
    } catch (err) {
      if (window.App?.isDev) console.error("[promo-suggest]", err);
    }
  }
});
