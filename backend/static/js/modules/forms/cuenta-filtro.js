document.addEventListener("DOMContentLoaded", () => {
  const select = document.getElementById("filtro-periodo");
  const rango = document.getElementById("filtro-rango-fechas");
  if (!select || !rango) return;

  select.addEventListener("change", () => {
    rango.classList.toggle("hidden", select.value !== "rango");
  });
});
