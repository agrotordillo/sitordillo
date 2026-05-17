// ejemplo-simple.js
import { $, on } from "../core/dom.js";
import { events, notifications } from "../app.js";

class EjemploSimplePage {
  constructor() {
    // Esperar a que el DOM esté listo
    events.on("app:ready", () => {
      this.init();
    });
  }

  init() {
    const boton = $("#mi-boton");
    if (boton) {
      on(boton, "click", () => {
        notifications.success("¡Notificación de éxito desde el botón!");
      });
    }
  }
}

// Auto-inicializar
new EjemploSimplePage();
