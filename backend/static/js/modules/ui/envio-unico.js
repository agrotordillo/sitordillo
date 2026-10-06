// Deshabilita el botón de enviar de los formularios protegidos contra doble
// envío -los que traen el token de un solo uso, ver {% token_envio %} y
// apps/core/envio_unico.py-: evita el doble clic común. El servidor sigue
// siendo la garantía real (recargar, dos pestañas, una red que reintenta).
//
// Se deshabilita en el siguiente ciclo (setTimeout 0), no dentro del evento
// "submit": a esas alturas el navegador ya armó los datos del formulario, así
// que no se pierde el valor del botón que se presionó. Si otro manejador
// canceló el envío (un confirm() rechazado), no se toca nada.
const SELECTOR_TOKEN = 'input[name="token_envio"]';
const SELECTOR_BOTONES = 'button[type="submit"], button:not([type]), input[type="submit"]';
const MARCA = "envioUnicoDeshabilitado";

document.addEventListener("submit", (event) => {
  const form = event.target;
  if (event.defaultPrevented || !(form instanceof HTMLFormElement) || !form.querySelector(SELECTOR_TOKEN)) return;

  setTimeout(() => {
    form.querySelectorAll(SELECTOR_BOTONES).forEach((boton) => {
      if (boton.disabled) return;
      boton.disabled = true;
      boton.dataset[MARCA] = "true";
      boton.classList.add("opacity-50", "cursor-wait");
    });
  }, 0);
});

// Al volver con el botón "Atrás", el navegador puede restaurar la página
// desde su caché con los botones todavía deshabilitados: solo se rehabilitan
// los que deshabilitó este script.
window.addEventListener("pageshow", (event) => {
  if (!event.persisted) return;
  document.querySelectorAll(`[data-envio-unico-deshabilitado="true"]`).forEach((boton) => {
    boton.disabled = false;
    delete boton.dataset[MARCA];
    boton.classList.remove("opacity-50", "cursor-wait");
  });
});
