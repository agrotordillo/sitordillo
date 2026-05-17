let overlay, panel, backdrop;
let isOpen = false;
let closeTimer;

function getAnimationMs() {
  if (!overlay) return 200;
  const duration = window.getComputedStyle(overlay).transitionDuration || "0s";
  const value = Number.parseFloat(duration);
  if (Number.isNaN(value)) return 200;
  return duration.includes("ms") ? value : value * 1000;
}

function open() {
  if (!overlay) return;
  isOpen = true;
  overlay.classList.remove("hidden");
  overlay.classList.remove("opacity-0");
  overlay.classList.add("opacity-100");
  requestAnimationFrame(() => {
    panel.classList.replace("-translate-x-full", "translate-x-0");
  });
}

function close() {
  if (!overlay) return;
  isOpen = false;
  panel.classList.replace("translate-x-0", "-translate-x-full");
  overlay.classList.remove("opacity-100");
  overlay.classList.add("opacity-0");

  if (closeTimer) {
    clearTimeout(closeTimer);
  }
  closeTimer = window.setTimeout(() => {
    if (!isOpen) overlay.classList.add("hidden");
  }, getAnimationMs());
}

document.addEventListener("DOMContentLoaded", () => {
  overlay = document.getElementById("sidebar");
  panel = document.getElementById("sidebar-panel");
  backdrop = document.getElementById("sidebar-backdrop");
  if (!overlay || !panel) return;

  document.getElementById("sidebar-toggle")?.addEventListener("click", open);
  document.getElementById("sidebar-close")?.addEventListener("click", close);
  backdrop?.addEventListener("click", close);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && isOpen) close();
  });
});

export { open, close };
