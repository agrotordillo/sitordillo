// "Columnas" y "Agrupar por" de un listado (ver
// products/includes/_dialogos_listado.html):
// - [data-abrir-dialogo="<id>"] abre el <dialog> con ese id y
//   [data-cerrar-dialogo] lo cierra.
// - [data-lista-doble]: dos <select multiple>, [data-lista-origen] y
//   [data-lista-destino], con botones [data-mover] para pasar opciones de
//   uno a otro y reordenar el destino (doble clic también las pasa). Las
//   opciones [data-fija] no se pueden quitar. Al enviar el formulario se
//   seleccionan todas las del destino para que se envíen en su orden.
// - [data-pestana] / [data-panel-pestana]: pestañas Estático/Dinámico;
//   la activa queda en el input [data-modo-agrupar].
// - [data-colapsar-grupo="<id>"] oculta/muestra las filas cuyo
//   data-grupos incluye ese id (los productos y subgrupos del grupo).
document.addEventListener("DOMContentLoaded", () => {
  const mover = (lista, accion) => {
    const origen = lista.querySelector("[data-lista-origen]");
    const destino = lista.querySelector("[data-lista-destino]");
    const elegidas = (select) => Array.from(select.selectedOptions);

    if (accion === "agregar") {
      elegidas(origen).forEach((opcion) => destino.append(opcion));
    } else if (accion === "quitar") {
      elegidas(destino)
        .filter((opcion) => !opcion.hasAttribute("data-fija"))
        .forEach((opcion) => origen.append(opcion));
    } else if (accion === "subir") {
      elegidas(destino).forEach((opcion) => {
        const anterior = opcion.previousElementSibling;
        if (anterior && !anterior.selected) anterior.before(opcion);
      });
    } else if (accion === "bajar") {
      elegidas(destino).reverse().forEach((opcion) => {
        const siguiente = opcion.nextElementSibling;
        if (siguiente && !siguiente.selected) siguiente.after(opcion);
      });
    }
  };

  document.addEventListener("click", (event) => {
    const abrir = event.target.closest("[data-abrir-dialogo]");
    if (abrir) {
      document.getElementById(abrir.dataset.abrirDialogo)?.showModal();
      return;
    }

    const cerrar = event.target.closest("[data-cerrar-dialogo]");
    if (cerrar) {
      cerrar.closest("dialog")?.close();
      return;
    }

    const boton = event.target.closest("[data-mover]");
    if (boton) {
      mover(boton.closest("[data-lista-doble]"), boton.dataset.mover);
      return;
    }

    const pestana = event.target.closest("[data-pestana]");
    if (pestana) {
      const formulario = pestana.closest("form");
      formulario.querySelectorAll("[data-pestana]").forEach((otra) => {
        otra.setAttribute("aria-selected", String(otra === pestana));
      });
      formulario.querySelectorAll("[data-panel-pestana]").forEach((panel) => {
        panel.hidden = panel.dataset.panelPestana !== pestana.dataset.pestana;
      });
      formulario.querySelector("[data-modo-agrupar]").value = pestana.dataset.pestana;
      return;
    }

    const grupo = event.target.closest("[data-colapsar-grupo]");
    if (grupo) {
      const id = grupo.dataset.colapsarGrupo;
      const colapsar = grupo.getAttribute("aria-expanded") === "true";
      grupo.setAttribute("aria-expanded", String(!colapsar));
      grupo.querySelector("[data-icono-grupo]")?.classList.toggle("-rotate-90", colapsar);
      document.querySelectorAll(`[data-grupos~="${id}"]`).forEach((fila) => {
        fila.hidden = colapsar;
        // Al expandir, los subgrupos vuelven a mostrarse expandidos.
        const subgrupo = fila.querySelector("[data-colapsar-grupo]");
        if (subgrupo) {
          subgrupo.setAttribute("aria-expanded", "true");
          subgrupo.querySelector("[data-icono-grupo]")?.classList.remove("-rotate-90");
        }
      });
    }
  });

  document.addEventListener("dblclick", (event) => {
    const opcion = event.target.closest("[data-lista-doble] option");
    if (!opcion) return;
    const lista = opcion.closest("[data-lista-doble]");
    const select = opcion.closest("select");
    Array.from(select.options).forEach((otra) => { otra.selected = otra === opcion; });
    mover(lista, select.hasAttribute("data-lista-origen") ? "agregar" : "quitar");
  });

  document.addEventListener("submit", (event) => {
    const formulario = event.target.closest("[data-formulario-lista-doble]");
    if (!formulario) return;
    formulario.querySelectorAll("[data-lista-destino] option").forEach((opcion) => { opcion.selected = true; });
  });
});
