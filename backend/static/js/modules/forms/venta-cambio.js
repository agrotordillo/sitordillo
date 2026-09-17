document.addEventListener("DOMContentLoaded", () => {
  // Igual patrón que pago-form.js (mostrar/ocultar campos según la clave
  // SAT de la forma de pago elegida, sin ir al servidor), pero aquí solo
  // aplica a Efectivo: muestra "cuánto se recibe" y calcula el cambio en
  // vivo contra el total de la venta (que ya calcula formsetRows() en
  // venta_form.html). Cuando el cobro se dividió en varias formas de pago,
  // este bloque completo queda oculto por Alpine (ver x-show="!dividido")
  // y el recibido/cambio de cada forma de pago se maneja por fila en
  // venta-pago-dividido.js.
  const CLAVE_EFECTIVO = "01";

  const select = document.getElementById("id_forma_pago");
  const campoEfectivo = document.getElementById("venta-campo-efectivo");
  const inputRecibido = document.getElementById("id_efectivo_recibido");
  const spanCambio = document.getElementById("venta-cambio-simple");
  const totalEl = document.getElementById("venta-total-display");
  if (!select || !campoEfectivo || !inputRecibido || !spanCambio || !totalEl) return;

  select.addEventListener("change", actualizar);
  inputRecibido.addEventListener("input", actualizarCambio);
  document.addEventListener("input", (event) => {
    if (event.target.matches(".fs-cantidad, .fs-precio")) actualizarCambio();
  });

  actualizar();

  function actualizar() {
    const esEfectivo = select.selectedOptions[0]?.dataset.clave === CLAVE_EFECTIVO;
    campoEfectivo.classList.toggle("hidden", !esEfectivo);
    if (!esEfectivo) inputRecibido.value = "";
    actualizarCambio();
  }

  function totalVenta() {
    const texto = totalEl.textContent || "0";
    return parseFloat(texto.replace(/[^0-9.-]/g, "")) || 0;
  }

  function actualizarCambio() {
    const cambio = (parseFloat(inputRecibido.value) || 0) - totalVenta();
    spanCambio.textContent =
      "$" + cambio.toLocaleString("es-MX", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
});
