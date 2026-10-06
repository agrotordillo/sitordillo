// Impresión del ticket de venta (ventas/venta_ticket.html). Antes vivía en
// un <script> en línea; la CSP ya no lo permite (B32 en docs/AUDITORIA.md).
//
// Con impresora configurada en la sucursal, la vista manda el ticket ya
// armado en ESC/POS (json_script "ticket-data") y se imprime con QZ Tray;
// sin ella, o si QZ Tray no responde, se usa la impresión normal del
// navegador.
(function () {
  var boton = document.getElementById("btn-imprimir-ticket");
  var estado = document.getElementById("qz-estado");
  var nodoDatos = document.getElementById("ticket-data");

  if (!nodoDatos || typeof qz === "undefined") {
    if (boton) {
      boton.addEventListener("click", function () { window.print(); });
    }
    return;
  }

  var datos = JSON.parse(nodoDatos.textContent);

  // Firma cada solicitud con el certificado del servidor (ver
  // apps/ventas/views/qz_views.py) para que QZ Tray confíe en esta
  // conexión -sin esto, cada conexión es "anónima" y el diálogo de "Remember
  // this decision" de QZ Tray no persiste porque no hay ningún certificado
  // estable contra el cual recordarla-. Una vez que ese mismo certificado se
  // instale como override.crt en QZ Tray de esa PC, deja de preguntar.
  qz.security.setCertificatePromise(function (resolve, reject) {
    fetch(boton.dataset.urlCertificado, { cache: "no-store" })
      .then(function (data) { data.ok ? resolve(data.text()) : reject(data.text()); });
  });
  qz.security.setSignatureAlgorithm("SHA512");
  qz.security.setSignaturePromise(function (toSign) {
    return function (resolve, reject) {
      fetch(boton.dataset.urlFirmar + "?request=" + encodeURIComponent(toSign), { cache: "no-store" })
        .then(function (data) { data.ok ? resolve(data.text()) : reject(data.text()); });
    };
  });

  function mostrarEstado(texto) {
    if (estado) { estado.textContent = texto; }
  }

  function enviarAImpresora() {
    var conectar = qz.websocket.isActive() ? Promise.resolve() : qz.websocket.connect();
    return conectar.then(function () {
      var config = qz.configs.create(datos.printer);
      var payload = [{ type: "raw", format: "command", flavor: "base64", data: datos.data }];
      return qz.print(config, payload);
    });
  }

  if (boton) {
    boton.addEventListener("click", function () {
      mostrarEstado("Enviando a la impresora...");
      enviarAImpresora()
        .then(function () { mostrarEstado("Ticket enviado a la impresora."); })
        .catch(function (err) {
          console.error("QZ Tray:", err);
          mostrarEstado("No se pudo imprimir con QZ Tray (¿está abierto en esta PC?). Se abre la vista de impresión normal.");
          window.print();
        });
    });
  }

  if (datos.auto) {
    mostrarEstado("Imprimiendo automáticamente...");
    enviarAImpresora()
      .then(function () { mostrarEstado("Ticket enviado a la impresora."); })
      .catch(function (err) {
        console.error("QZ Tray:", err);
        mostrarEstado('No se pudo imprimir automáticamente (¿QZ Tray está abierto en esta PC?). Usa el botón "Imprimir ticket".');
      });
  }
})();
