import { events } from "./core/events.js";
import { http } from "./core/http.js";
import { notifications } from "./modules/ui/notifications.js";

// ========== ESTADO GLOBAL MÍNIMO ==========
window.App = {
  env: window.location.hostname.includes("localhost")
    ? "development"
    : "production",
  user: window.initialData?.user || null,
  csrfToken: document.querySelector("[name=csrfmiddlewaretoken]")?.value,

  // Singleton esenciales
  http,
  events,
  notifications,

  // Utilidades básicas
  utils: {
    debug: function (...args) {
      if (this.env === "development") {
        console.log("[DEBUG]", ...args);
      }
    },
  },
};

// ========== MANEJO DE ERRORES ==========
function setupErrorHandling() {
  window.addEventListener("error", (event) => {
    console.error("Error global:", event.error);

    if (event.error instanceof Error) {
      setTimeout(() => {
        notifications.error("Ocurrió un error inesperado");
      }, 100);
    }
  });

  window.addEventListener("unhandledrejection", (event) => {
    console.error("Promise rechazada:", event.reason);
  });
}

// ========== INICIALIZACIÓN ==========
function initializeApp() {
  console.log("🚀 Aplicación inicializada");

  events.emit("app:ready", {
    timestamp: new Date(),
    page: document.title,
  });

  // Notificación de bienvenida (opcional)
  if (!sessionStorage.getItem("app-welcomed")) {
    setTimeout(() => {
      notifications.info("Sistema listo", 1500);
      sessionStorage.setItem("app-welcomed", "true");
    }, 500);
  }
}

// ========== EJECUCIÓN ==========
document.addEventListener("DOMContentLoaded", () => {
  setupErrorHandling();
  initializeApp();
});

// Exportar para uso en páginas específicas
export { events, http, notifications };
