// Comportamientos que antes iban como atributos on* en el HTML. La CSP ya no
// permite JavaScript en línea (B32 en docs/AUDITORIA.md): las plantillas los
// declaran con data-* y este módulo los conecta.
//
//   <form data-confirmar="¿Seguro?">   pide confirmación antes de enviar.
//   <select data-enviar-al-cambiar>    envía su formulario al cambiar.
//   <button data-imprimir>             abre el diálogo de impresión.

// En fase de captura: corre antes que cualquier otro manejador de "submit"
// (p. ej. envio-unico.js, que deshabilita los botones), así un envío que no
// se confirma ni siquiera les llega.
document.addEventListener(
  "submit",
  (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || !form.dataset.confirmar) return;
    if (!window.confirm(form.dataset.confirmar)) {
      event.preventDefault();
      event.stopImmediatePropagation();
    }
  },
  true,
);

document.addEventListener("change", (event) => {
  const campo = event.target;
  if (!(campo instanceof Element) || !campo.matches("[data-enviar-al-cambiar]") || !campo.form) return;
  campo.form.requestSubmit();
});

document.addEventListener("click", (event) => {
  if (event.target instanceof Element && event.target.closest("[data-imprimir]")) {
    window.print();
  }
});
