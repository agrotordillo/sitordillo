// Decisión del usuario: precios, costos, IVA, IEPS, % de utilidad y
// cantidades (también en ventas) solo se cambian tecleando. En los
// navegadores, girar la rueda del mouse sobre un <input type="number">
// enfocado sube o baja su valor sin que nadie lo note -un precio o una
// cantidad pueden cambiar mientras uno solo quería desplazar la página-.
// Al girar la rueda sobre un campo numérico enfocado se le quita el foco:
// el valor no cambia y la página se desplaza como siempre. Aplica a todos
// los campos numéricos del sistema, incluidos los renglones que se agregan
// después (el evento se escucha en el documento).
document.addEventListener(
  "wheel",
  (event) => {
    const campo = event.target;
    if (campo instanceof HTMLInputElement && campo.type === "number" && campo === document.activeElement) {
      campo.blur();
    }
  },
  { capture: true, passive: true },
);
