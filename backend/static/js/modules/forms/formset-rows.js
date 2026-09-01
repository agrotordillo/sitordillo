document.addEventListener("alpine:init", () => {
  Alpine.data("formsetRows", (config) => ({
    total: 0,

    init() {
      this._rows = this.$refs.rows;
      this._emptyTemplate = this.$refs.emptyRow;
      this._totalFormsInput = document.querySelector(config.totalFormsSelector);

      this._rows.querySelectorAll(".formset-row").forEach((row) => this._bindRow(row));
      document.querySelectorAll(".fs-impuesto-suma, .fs-impuesto-resta, .fs-descuento-general").forEach((el) => {
        el.addEventListener("input", () => this._recalculate());
      });
      this._recalculate();
    },

    addRow() {
      const index = parseInt(this._totalFormsInput.value, 10);
      const html = this._emptyTemplate.innerHTML.replaceAll("__prefix__", index);
      const wrapper = document.createElement("tbody");
      wrapper.innerHTML = html.trim();
      const row = wrapper.firstElementChild;
      if (!row) return;

      this._rows.appendChild(row);
      this._totalFormsInput.value = index + 1;
      this._bindRow(row);
      this._recalculate();
    },

    removeRow(button) {
      const row = button.closest(".formset-row");
      if (!row) return;

      const deleteInput = row.querySelector('input[name$="-DELETE"]');
      if (deleteInput) deleteInput.checked = true;

      row.style.display = "none";
      row.dataset.removed = "true";
      this._recalculate();
    },

    _bindRow(row) {
      row.querySelectorAll(".fs-cantidad, .fs-precio, .fs-descuento").forEach((el) => {
        el.addEventListener("input", () => this._recalculate());
      });
    },

    _recalculate() {
      let subtotal = 0;
      this._rows.querySelectorAll(".formset-row").forEach((row) => {
        if (row.dataset.removed === "true") return;
        const qty = parseFloat(row.querySelector(".fs-cantidad")?.value) || 0;
        const price = parseFloat(row.querySelector(".fs-precio")?.value) || 0;
        // .fs-descuento es opcional (% 0-100); si la fila no lo trae, no afecta el total.
        const descuentoEl = row.querySelector(".fs-descuento");
        const descuento = descuentoEl ? parseFloat(descuentoEl.value) || 0 : 0;
        const rowTotal = qty * price * (1 - descuento / 100);

        const totalEl = row.querySelector(".fs-row-total");
        if (totalEl) totalEl.textContent = rowTotal.toLocaleString("es-MX", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

        subtotal += rowTotal;
      });

      // Descuento general del proveedor: un solo % sobre el subtotal (no por
      // línea), igual que Proveedor.descuento y OrdenCompra.descuento_pct.
      let descuentoGeneralPct = 0;
      document.querySelectorAll(".fs-descuento-general").forEach((el) => {
        descuentoGeneralPct += parseFloat(el.value) || 0;
      });
      const montoDescuentoGeneral = subtotal * (descuentoGeneralPct / 100);
      document.querySelectorAll(".fs-descuento-general-monto").forEach((el) => {
        el.textContent = montoDescuentoGeneral.toLocaleString("es-MX", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
      });

      let ajusteImpuestos = 0;
      document.querySelectorAll(".fs-impuesto-suma").forEach((el) => {
        ajusteImpuestos += parseFloat(el.value) || 0;
      });
      document.querySelectorAll(".fs-impuesto-resta").forEach((el) => {
        ajusteImpuestos -= parseFloat(el.value) || 0;
      });

      this.total = (subtotal - montoDescuentoGeneral + ajusteImpuestos).toLocaleString("es-MX", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    },
  }));
});
