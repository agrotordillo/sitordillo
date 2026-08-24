document.addEventListener("DOMContentLoaded", () => {
  const inputs = document.querySelectorAll(".monto-aplicar");
  const total = document.getElementById("total-a-pagar");
  if (!inputs.length || !total) return;

  inputs.forEach((input) => input.addEventListener("input", actualizarTotal));
  actualizarTotal();

  function actualizarTotal() {
    let suma = 0;
    inputs.forEach((input) => {
      const valor = parseFloat(input.value);
      if (!Number.isNaN(valor)) suma += valor;
    });
    total.textContent = `$${suma.toFixed(2)}`;
  }
});
