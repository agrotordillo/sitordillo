// Botón "Columnas" genérico para listados: abre un panel con checkboxes y
// muestra/oculta las celdas [data-col="<valor>"] correspondientes. El
// checkbox y las celdas se enlazan solo por el atributo data-col, así que
// una misma página puede tener varios grupos independientes si hace falta.
document.addEventListener("DOMContentLoaded", () => {
  document.addEventListener("click", (event) => {
    const boton = event.target.closest("[data-column-toggle-btn]");
    if (boton) {
      const panel = document.querySelector(boton.dataset.columnToggleBtn);
      if (panel) panel.classList.toggle("hidden");
      return;
    }
    if (!event.target.closest("[data-column-toggle-panel]")) {
      document.querySelectorAll("[data-column-toggle-panel]:not(.hidden)").forEach((panel) => panel.classList.add("hidden"));
    }
  });

  document.addEventListener("change", (event) => {
    const check = event.target.closest("[data-col-toggle]");
    if (!check) return;
    const col = check.dataset.colToggle;
    document.querySelectorAll(`[data-col="${col}"]`).forEach((el) => {
      el.classList.toggle("hidden", !check.checked);
    });
  });
});
