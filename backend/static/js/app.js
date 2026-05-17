import { events } from "./core/events.js";
import { http } from "./core/http.js";
import { notifications } from "./modules/ui/notifications.js";
import * as sidebar from "./modules/ui/sidebar.js";

const isDev = window.location.hostname === "localhost";

window.App = { events, http, notifications, sidebar, isDev };

window.addEventListener("error", (event) => {
  if (isDev) console.error("Error global:", event.error);
  if (event.error instanceof Error) {
    notifications.error("Ocurrió un error inesperado");
  }
});

window.addEventListener("unhandledrejection", (event) => {
  if (isDev) console.error("Promise rechazada:", event.reason);
});

export { events, http, notifications, sidebar };
