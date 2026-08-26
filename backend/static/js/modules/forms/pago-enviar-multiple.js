document.addEventListener("DOMContentLoaded", () => {
  const checkboxes = document.querySelectorAll(".chk-pago-correo");
  if (!checkboxes.length) return;

  const boton = document.getElementById("btn-enviar-multiple");
  if (!boton) return;

  checkboxes.forEach((chk) => chk.addEventListener("change", actualizar));
  actualizar();

  function actualizar() {
    const marcados = document.querySelectorAll(".chk-pago-correo:checked").length;
    boton.disabled = marcados < 1;
  }
});
