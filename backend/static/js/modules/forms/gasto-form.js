document.addEventListener("alpine:init", () => {
  // Combina en un solo componente el toggle de "gasto compartido" y el
  // formset de distribución por sucursal, porque ambas cosas dependen una
  // de la otra: el formset solo se muestra y valida cuando el checkbox
  // está activo, y su suma se compara en vivo contra el importe capturado.
  Alpine.data("gastoForm", (config) => ({
    compartido: false,
    totalAsignado: 0,
    restante: 0,

    init() {
      this._rows = this.$refs.rows;
      this._emptyTemplate = this.$refs.emptyRow;
      this._totalFormsInput = document.querySelector(config.totalFormsSelector);
      this._importeInput = document.querySelector(config.importeSelector);
      this._compartidoInput = document.querySelector(config.compartidoSelector);

      this.compartido = this._compartidoInput ? this._compartidoInput.checked : false;
      this._compartidoInput?.addEventListener("change", (event) => {
        this.compartido = event.target.checked;
      });
      this._importeInput?.addEventListener("input", () => this._recalculate());

      this._rows.querySelectorAll(".formset-row").forEach((row) => this._bindRow(row));
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
      row.querySelectorAll(".fs-monto").forEach((el) => {
        el.addEventListener("input", () => this._recalculate());
      });
    },

    _recalculate() {
      let suma = 0;
      this._rows.querySelectorAll(".formset-row").forEach((row) => {
        if (row.dataset.removed === "true") return;
        suma += parseFloat(row.querySelector(".fs-monto")?.value) || 0;
      });
      this.totalAsignado = suma;
      this.restante = (parseFloat(this._importeInput?.value) || 0) - suma;
    },

    formatMoney(value) {
      return (value || 0).toLocaleString("es-MX", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    },
  }));
});
