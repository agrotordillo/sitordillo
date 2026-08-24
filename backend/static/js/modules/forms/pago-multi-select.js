document.addEventListener("DOMContentLoaded", () => {
  const checkboxes = document.querySelectorAll(".chk-cuenta");
  checkboxes.forEach((chk) => chk.addEventListener("change", () => actualizarBoton(chk.dataset.group)));

  function actualizarBoton(groupId) {
    const marcadas = document.querySelectorAll(`.chk-cuenta[data-group="${groupId}"]:checked`).length;
    const boton = document.getElementById(`btn-pagar-${groupId}`);
    if (boton) boton.disabled = marcadas < 2;
  }
});
