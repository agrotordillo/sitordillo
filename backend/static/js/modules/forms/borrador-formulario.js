// Borradores de formularios de captura.
//
// Decisión del usuario: si estás capturando y te cambias de pantalla sin
// guardar, lo capturado no se pierde. Todo <form data-borrador> va
// guardando en el navegador (localStorage, por usuario y por pantalla) lo
// que se escribe; al volver al mismo formulario se recupera tal cual
// -incluidos los renglones agregados- con el aviso "Se recuperó lo que no
// guardaste · Descartar". Nada llega al sistema hasta que se da Guardar.
//
// - Se guarda solo después de una captura real del usuario (eventos
//   isTrusted), con una pausa corta, y también al salir de la página.
// - Al enviar el formulario el borrador se aparta: si la siguiente página
//   es otra (se guardó bien), se borra; si es el mismo formulario (el
//   servidor lo regresó con errores), se conserva sin volver a aplicarlo,
//   porque el servidor ya lo trae lleno.
// - No se guardan contraseñas, archivos, tokens ni los ids/contadores
//   internos de los renglones (los pone el servidor).
// - Caducan a los 7 días.

const PREFIJO = "borrador:";
const PREFIJO_ENVIADO = "borrador-enviado:";
const CADUCIDAD_MS = 7 * 24 * 60 * 60 * 1000;
const NO_GUARDAR = /^(csrfmiddlewaretoken|token_envio|next)$|-(INITIAL_FORMS|MIN_NUM_FORMS|MAX_NUM_FORMS|id)$/;
const ESPERA_OPCIONES_MS = 8000;

function usuario() {
  return document.body?.dataset.usuario || "";
}

function claveDe(form) {
  const params = new URLSearchParams(window.location.search);
  params.delete("next");
  params.sort();
  const busqueda = params.toString();
  const nombre = form.dataset.borrador || "principal";
  return `${usuario()}:${window.location.pathname}${busqueda ? `?${busqueda}` : ""}#${nombre}`;
}

function leer(clave) {
  try {
    const crudo = window.localStorage.getItem(clave);
    return crudo ? JSON.parse(crudo) : null;
  } catch {
    return null;
  }
}

function escribir(clave, valor) {
  try {
    window.localStorage.setItem(clave, JSON.stringify(valor));
  } catch {
    // Sin espacio o sin acceso a localStorage: el formulario sigue funcionando igual.
  }
}

function borrar(clave) {
  try {
    window.localStorage.removeItem(clave);
  } catch {
    /* sin acceso */
  }
}

function clavesConPrefijo(prefijo) {
  const claves = [];
  try {
    for (let i = 0; i < window.localStorage.length; i += 1) {
      const clave = window.localStorage.key(i);
      if (clave && clave.startsWith(prefijo)) claves.push(clave);
    }
  } catch {
    /* sin acceso */
  }
  return claves;
}

function esTextoDeBuscador(el) {
  return el.tagName === "INPUT" && !el.name && /-search-input\b/.test(el.className);
}

// Campo oculto (con name) que acompaña al texto visible de un buscador.
function ocultoDelBuscador(el) {
  return el.parentElement?.querySelector('input[type="hidden"][name]') || null;
}

function guardable(el) {
  if (el.disabled) return false;
  if (["password", "file", "submit", "button", "reset", "image"].includes(el.type)) return false;
  if (el.tagName === "BUTTON" || el.tagName === "FIELDSET" || el.tagName === "OUTPUT") return false;
  if (esTextoDeBuscador(el)) return Boolean(ocultoDelBuscador(el));
  return Boolean(el.name) && !NO_GUARDAR.test(el.name);
}

function capturar(form) {
  const campos = [];
  const ocurrencias = {};
  for (const el of form.elements) {
    if (!guardable(el)) continue;
    if (esTextoDeBuscador(el)) {
      campos.push({ t: ocultoDelBuscador(el).name, v: el.value });
      continue;
    }
    const n = ocurrencias[el.name] || 0;
    ocurrencias[el.name] = n + 1;
    const campo = { n: el.name, i: n };
    if (el.type === "checkbox" || el.type === "radio") campo.c = el.checked;
    else if (el.tagName === "SELECT" && el.multiple) campo.m = [...el.selectedOptions].map((o) => o.value);
    else campo.v = el.value;
    campos.push(campo);
  }
  const totales = {};
  form.querySelectorAll('input[name$="-TOTAL_FORMS"]').forEach((el) => {
    totales[el.name] = parseInt(el.value, 10) || 0;
  });
  return { guardado: Date.now(), totales, campos };
}

function distinto(form, borrador) {
  const actual = JSON.stringify(capturar(form).campos);
  return actual !== JSON.stringify(borrador.campos);
}

// Un <select> cuyas opciones llegan después (p. ej. subcategorías que se
// cargan al elegir la categoría): se aplica el valor en cuanto aparezca la
// opción, durante unos segundos.
function asegurarValorDeSelect(select, valor) {
  const aplicar = () => {
    if (select.value === valor) return true;
    if (![...select.options].some((o) => o.value === valor)) return false;
    select.value = valor;
    select.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  };
  aplicar();
  const observador = new MutationObserver(aplicar);
  observador.observe(select, { childList: true });
  setTimeout(() => observador.disconnect(), ESPERA_OPCIONES_MS);
}

function restaurar(form, borrador) {
  // 1. Renglones: agregar los que faltan antes de llenar sus campos.
  for (const [nombre, total] of Object.entries(borrador.totales || {})) {
    const input = form.querySelector(`input[name="${CSS.escape(nombre)}"]`);
    if (!input || typeof input.agregarRenglon !== "function") continue;
    let intentos = 0;
    while ((parseInt(input.value, 10) || 0) < total && intentos < 500) {
      input.agregarRenglon();
      intentos += 1;
    }
  }

  // 2. Valores.
  const porNombre = {};
  for (const el of form.elements) {
    if (!el.name) continue;
    (porNombre[el.name] ||= []).push(el);
  }
  const tocados = [];
  for (const campo of borrador.campos) {
    if (campo.t !== undefined) {
      const oculto = porNombre[campo.t]?.[0];
      const texto = oculto?.parentElement?.querySelector("input:not([name])[class*='-search-input']");
      if (texto) texto.value = campo.v;
      continue;
    }
    // Los de solo lectura también (p. ej. el precio en ventas, que pone un
    // script): el servidor los vuelve a calcular al guardar.
    const el = porNombre[campo.n]?.[campo.i];
    if (!el || el.disabled) continue;
    if (campo.c !== undefined) {
      el.checked = campo.c;
    } else if (campo.m !== undefined) {
      [...el.options].forEach((o) => { o.selected = campo.m.includes(o.value); });
    } else if (el.tagName === "SELECT") {
      asegurarValorDeSelect(el, campo.v);
      continue;
    } else {
      el.value = campo.v;
    }
    tocados.push(el);
  }

  // 3. Avisar a los demás scripts (totales, renglones borrados, etc.).
  tocados.forEach((el) => {
    if (el.type !== "hidden" && el.type !== "checkbox" && el.type !== "radio") {
      el.dispatchEvent(new Event("input", { bubbles: true }));
    }
    el.dispatchEvent(new Event("change", { bubbles: true }));
  });

  // 4. Renglones que estaban quitados.
  form.querySelectorAll('input[name$="-DELETE"]').forEach((el) => {
    const row = el.closest(".formset-row");
    if (el.checked && row) {
      row.style.display = "none";
      row.dataset.removed = "true";
    }
  });
}

function mostrarAviso(form, clave, borrador) {
  const aviso = document.createElement("div");
  aviso.className =
    "mb-4 flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border border-primary-100 bg-primary-50 px-4 py-2.5 text-sm text-primary-800";
  const fecha = new Date(borrador.guardado).toLocaleString("es-MX", { dateStyle: "short", timeStyle: "short" });
  const texto = document.createElement("span");
  texto.textContent = `Se recuperó lo que no guardaste (${fecha}). Aún no está guardado en el sistema.`;
  const descartar = document.createElement("button");
  descartar.type = "button";
  descartar.className = "font-medium underline hover:text-primary-900";
  descartar.textContent = "Descartar";
  descartar.addEventListener("click", () => {
    borrar(clave);
    window.location.reload();
  });
  aviso.append(texto, descartar);
  form.prepend(aviso);
}

function limpiarCaducados() {
  const ahora = Date.now();
  for (const clave of [...clavesConPrefijo(PREFIJO), ...clavesConPrefijo(PREFIJO_ENVIADO)]) {
    const borrador = leer(clave);
    if (!borrador || ahora - (borrador.guardado || 0) > CADUCIDAD_MS) borrar(clave);
  }
}

// Borradores apartados al enviar: si esta página es la del mismo
// formulario, el servidor lo regresó con errores -se conserva como
// borrador-; si es cualquier otra, se guardó bien y se borra.
function resolverEnviados(clavesDeEstaPagina) {
  const prefijo = `${PREFIJO_ENVIADO}${usuario()}:`;
  for (const clave of clavesConPrefijo(prefijo)) {
    const propia = clave.slice(PREFIJO_ENVIADO.length);
    const borrador = leer(clave);
    if (clavesDeEstaPagina.has(propia) && borrador) escribir(`${PREFIJO}${propia}`, borrador);
    borrar(clave);
  }
}

function iniciar(form, recienEnviado) {
  const clave = claveDe(form);
  const claveCompleta = `${PREFIJO}${clave}`;
  let pendiente = false;
  let temporizador = null;

  const guardar = () => {
    clearTimeout(temporizador);
    if (!pendiente) return;
    pendiente = false;
    escribir(claveCompleta, capturar(form));
  };
  const programar = (event) => {
    if (!event.isTrusted) return;
    pendiente = true;
    clearTimeout(temporizador);
    temporizador = setTimeout(guardar, 500);
  };

  const borrador = leer(claveCompleta);
  if (borrador && !recienEnviado.has(clave) && distinto(form, borrador)) {
    restaurar(form, borrador);
    mostrarAviso(form, claveCompleta, borrador);
  }

  form.addEventListener("input", programar, true);
  form.addEventListener("change", programar, true);
  // Clics en botones de "agregar/quitar renglón" también cambian el borrador.
  form.addEventListener("click", (event) => {
    if (event.target.closest('button[type="button"]')) programar(event);
  }, true);
  window.addEventListener("pagehide", guardar);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") guardar();
  });

  form.addEventListener("submit", (event) => {
    // Si otro manejador canceló el envío (una confirmación rechazada), se
    // deja el borrador como está.
    setTimeout(() => {
      if (event.defaultPrevented) return;
      clearTimeout(temporizador);
      pendiente = false;
      escribir(`${PREFIJO_ENVIADO}${clave}`, capturar(form));
      borrar(claveCompleta);
    }, 0);
  });
}

function arrancar() {
  if (!usuario()) return;
  limpiarCaducados();
  const formularios = [...document.querySelectorAll("form[data-borrador]")];
  const clavesDeEstaPagina = new Set(formularios.map(claveDe));
  // Los que el servidor acaba de regresar con errores ya vienen llenos:
  // se conservan como borrador pero no se vuelven a aplicar.
  const recienEnviado = new Set(
    [...clavesDeEstaPagina].filter((clave) => leer(`${PREFIJO_ENVIADO}${clave}`)),
  );
  resolverEnviados(clavesDeEstaPagina);
  // Se espera un ciclo para que Alpine y los demás scripts del formulario
  // ya estén listos (renglones, selects dependientes, buscadores).
  setTimeout(() => formularios.forEach((form) => iniciar(form, recienEnviado)), 0);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", arrancar);
} else {
  arrancar();
}
