function getCsrfToken() {
  return (
    document.querySelector("[name=csrfmiddlewaretoken]")?.value ||
    document.cookie.match(/csrftoken=([^;]+)/)?.[1] ||
    ""
  );
}

document.addEventListener("alpine:init", () => {
  Alpine.data("quickCreate", (config) => ({
    open: false,
    loading: false,
    errors: {},
    values: {},
    fields: config.fields || [],
    title: config.title || "Nuevo registro",

    init() {
      this._target = document.querySelector(config.target);
      this._reset();
    },

    show() {
      this._reset();
      this.open = true;
      this.$nextTick(() => {
        this.$root.querySelector("[data-qc-autofocus]")?.focus();
      });
    },

    close() {
      if (this.loading) return;
      this.open = false;
    },

    async submit() {
      if (this.loading) return;
      this.loading = true;
      this.errors = {};
      try {
        const res = await fetch(config.url, {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "X-CSRFToken": getCsrfToken(),
          },
          body: JSON.stringify(this.values),
        });

        if (res.status === 400) {
          const data = await res.json().catch(() => ({}));
          this.errors = data.errors || {};
          return;
        }
        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        const data = await res.json();
        this._addToTarget(data);
        this.open = false;
        window.App?.notifications?.success?.(`${this.title} guardado`);
      } catch (err) {
        if (window.App?.isDev) console.error("[quickCreate]", err);
        this.errors = { __all__: ["No se pudo guardar el registro."] };
      } finally {
        this.loading = false;
      }
    },

    _reset() {
      this.errors = {};
      const next = {};
      for (const f of this.fields) next[f.name] = "";
      this.values = next;
    },

    _addToTarget({ value, label }) {
      if (!this._target) return;
      const opt = document.createElement("option");
      opt.value = value;
      opt.textContent = label;
      opt.selected = true;
      this._target.appendChild(opt);
      this._target.dispatchEvent(new Event("change", { bubbles: true }));
    },
  }));
});
