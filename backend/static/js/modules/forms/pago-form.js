document.addEventListener("DOMContentLoaded", () => {
  const CLAVE_TRANSFERENCIA = "03";
  const CLAVE_CHEQUE = "02";
  const CLAVE_COMPENSACION = "17"; // "Nota de crédito" del proveedor.
  const CLAVE_TARJETA_CREDITO = "04";
  const CLAVE_TARJETA_DEBITO = "28";
  // Banco obligatorio en transferencia; opcional (para reconciliar el
  // estado de cuenta) en pago con tarjeta — ver Pago.CLAVES_CON_BANCO.
  const CLAVES_CON_BANCO = [CLAVE_TRANSFERENCIA, CLAVE_TARJETA_CREDITO, CLAVE_TARJETA_DEBITO];

  const select = document.getElementById("id_forma_pago");
  const campoBanco = document.getElementById("campo-banco");
  const campoReferencia = document.getElementById("campo-referencia");
  const labelReferencia = document.getElementById("label-referencia");
  if (!select || !campoBanco || !campoReferencia) return;

  select.addEventListener("change", actualizar);
  actualizar();

  function actualizar() {
    const clave = select.selectedOptions[0]?.dataset.clave;

    campoBanco.classList.toggle("hidden", !CLAVES_CON_BANCO.includes(clave));

    const esReferencia = clave === CLAVE_CHEQUE || clave === CLAVE_COMPENSACION;
    campoReferencia.classList.toggle("hidden", !esReferencia);
    if (labelReferencia) {
      labelReferencia.textContent =
        clave === CLAVE_COMPENSACION ? "Número de nota de crédito" : "Número de cheque";
    }
  }
});
