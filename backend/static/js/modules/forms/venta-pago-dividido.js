document.addEventListener("alpine:init", () => {
  // Toggle de "dividir el cobro" + el formset de forma de pago/monto,
  // igual patrón que gastoForm (gasto-form.js) para el reparto de un
  // gasto compartido: el formset solo se muestra y valida cuando el
  // checkbox está activo, y su suma se compara en vivo contra el total.
  // A diferencia de gastoForm, el total contra el que se compara no es un
  // <input> propio -es el total de la venta, que ya calcula formsetRows()
  // en el <form> de arriba (ver venta_form.html)-, así que se lee del
  // texto del elemento que lo muestra en vez de duplicar el cálculo.
  Alpine.data("pagoDivididoForm", (config) => ({
    dividido: false,
    totalAsignado: 0,
    restante: 0,

    init() {
      // Prefijo "_pago" en todas las propiedades internas (no reactivas
      // para la vista) a propósito: este x-data queda ANIDADO dentro del
      // x-data="formsetRows(...)" del <form> (ver venta_form.html), y
      // Alpine comparte/hereda propiedades entre x-data anidados -si un
      // hijo asigna this.algo = x con un nombre que el padre YA tiene,
      // Alpine lo escribe en el padre, no en el hijo-. formsetRows usa
      // _rows/_emptyTemplate/_totalFormsInput para SU PROPIA tabla de
      // productos; usar esos mismos nombres aquí los pisaba en cuanto
      // este init() corría, dejando _rows de formsetRows apuntando a la
      // tabla de pago dividido y el subtotal/total de la venta en 0.00
      // sin importar el precio o cantidad capturados.
      this._pagoRows = this.$refs.rows;
      this._pagoEmptyTemplate = this.$refs.emptyRow;
      this._pagoTotalFormsInput = document.querySelector(config.totalFormsSelector);
      this._pagoTotalVentaEl = document.querySelector(config.totalVentaSelector);
      this._pagoDivididoInput = document.querySelector(config.divididoSelector);

      this.dividido = this._pagoDivididoInput ? this._pagoDivididoInput.checked : false;
      this._pagoDivididoInput?.addEventListener("change", (event) => {
        this.dividido = event.target.checked;
        this._recalculate();
      });

      // El total de la venta cambia con cualquier cantidad/precio de
      // producto (formsetRows lo recalcula primero, ya que su script se
      // carga antes que este); aquí solo se vuelve a leer.
      document.addEventListener("input", (event) => {
        if (event.target.matches(".fs-cantidad, .fs-precio, .fs-monto-pago")) this._recalculate();
      });

      this._pagoRows.querySelectorAll(".formset-row").forEach((row) => this._bindRow(row));
      this._recalculate();
    },

    addRow() {
      const index = parseInt(this._pagoTotalFormsInput.value, 10);
      const html = this._pagoEmptyTemplate.innerHTML.replaceAll("__prefix__", index);
      const wrapper = document.createElement("tbody");
      wrapper.innerHTML = html.trim();
      const row = wrapper.firstElementChild;
      if (!row) return;

      this._pagoRows.appendChild(row);
      this._pagoTotalFormsInput.value = index + 1;
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
      row.querySelectorAll(".fs-monto-pago").forEach((el) => {
        el.addEventListener("input", () => this._recalculate());
      });

      // Cada fila del pago dividido puede tener su propia forma de pago
      // (una en efectivo, otra en tarjeta, etc.), así que a diferencia de
      // venta-cambio.js (que solo mira el <select> único del cobro sin
      // dividir) aquí el "recibido"/"cambio" se resuelve por fila.
      const select = row.querySelector(".fs-forma-pago-dividido");
      const campoRecibido = row.querySelector(".campo-recibido-dividido");
      const inputRecibido = row.querySelector(".fs-recibido-pago");
      if (!select || !campoRecibido || !inputRecibido) return;

      const actualizarFila = () => {
        const esEfectivo = select.selectedOptions[0]?.dataset.clave === "01";
        campoRecibido.classList.toggle("hidden", !esEfectivo);
        if (!esEfectivo) inputRecibido.value = "";
        this._actualizarCambioFila(row);
      };
      select.addEventListener("change", actualizarFila);
      inputRecibido.addEventListener("input", () => this._actualizarCambioFila(row));
      row.querySelectorAll(".fs-monto-pago").forEach((el) => {
        el.addEventListener("input", () => this._actualizarCambioFila(row));
      });
      actualizarFila();
    },

    _actualizarCambioFila(row) {
      const span = row.querySelector(".cambio-dividido");
      if (!span) return;
      const monto = parseFloat(row.querySelector(".fs-monto-pago")?.value) || 0;
      const recibido = parseFloat(row.querySelector(".fs-recibido-pago")?.value) || 0;
      span.textContent = "$" + this.formatMoney(recibido - monto);
    },

    _totalVenta() {
      const texto = this._pagoTotalVentaEl?.textContent || "0";
      return parseFloat(texto.replace(/[^0-9.-]/g, "")) || 0;
    },

    _recalculate() {
      let suma = 0;
      this._pagoRows.querySelectorAll(".formset-row").forEach((row) => {
        if (row.dataset.removed === "true") return;
        suma += parseFloat(row.querySelector(".fs-monto-pago")?.value) || 0;
      });
      this.totalAsignado = suma;
      this.restante = this._totalVenta() - suma;
    },

    formatMoney(value) {
      return (value || 0).toLocaleString("es-MX", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    },
  }));
});
