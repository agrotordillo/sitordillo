document.addEventListener("DOMContentLoaded", () => {
  const CLAVE_TRANSFERENCIA = "03";
  const CLAVE_CHEQUE = "02";
  const CLAVE_COMPENSACION = "17"; // "Nota de crédito" del proveedor.
  const CLAVE_TARJETA_CREDITO = "04";
  const CLAVE_TARJETA_DEBITO = "28";
  // Banco obligatorio en transferencia; opcional (para reconciliar el
  // estado de cuenta) en cheque o pago con tarjeta — ver Pago.CLAVES_CON_BANCO.
  const CLAVES_CON_BANCO = [CLAVE_TRANSFERENCIA, CLAVE_CHEQUE, CLAVE_TARJETA_CREDITO, CLAVE_TARJETA_DEBITO];

  const select = document.getElementById("id_forma_pago");
  const campoBanco = document.getElementById("campo-banco");
  const campoReferencia = document.getElementById("campo-referencia");
  const labelReferencia = document.getElementById("label-referencia");
  const inputBanco = document.getElementById("id_banco");
  const inputReferencia = document.getElementById("id_numero_referencia");
  if (!select || !campoBanco || !campoReferencia) return;

  select.addEventListener("change", actualizar);
  actualizar();

  function actualizar() {
    const clave = select.selectedOptions[0]?.dataset.clave;

    const aplicaBanco = CLAVES_CON_BANCO.includes(clave);
    campoBanco.classList.toggle("hidden", !aplicaBanco);
    // Si se oculta el campo, se limpia también su valor -de lo contrario
    // queda seleccionado un banco de una forma de pago anterior (ej.
    // transferencia) y el guardado se rechaza al cambiar a una forma de
    // pago que ya no lo admite (ej. cheque).
    if (!aplicaBanco && inputBanco) inputBanco.value = "";

    const esReferencia = clave === CLAVE_CHEQUE || clave === CLAVE_COMPENSACION;
    campoReferencia.classList.toggle("hidden", !esReferencia);
    if (!esReferencia && inputReferencia) inputReferencia.value = "";
    if (labelReferencia) {
      labelReferencia.textContent =
        clave === CLAVE_COMPENSACION ? "Número de nota de crédito" : "Número de cheque";
    }
  }
});
