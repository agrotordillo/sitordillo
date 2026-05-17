document.addEventListener("alpine:init", () => {
  Alpine.data("dependentSelect", (config) => ({
    loading: false,
    _parent: null,
    _child: null,

    init() {
      this._parent = document.querySelector(config.parent);
      this._child = document.querySelector(config.child);
      if (!this._parent || !this._child) return;

      this._parent.addEventListener("change", () => {
        this._load(this._parent.value);
      });

      if (this._parent.value) {
        this._load(this._parent.value);
      } else {
        this._reset();
      }
    },

    async _load(parentValue) {
      if (!parentValue) {
        this._reset();
        return;
      }

      this.loading = true;
      this._child.disabled = true;

      try {
        const sep = config.url.includes("?") ? "&" : "?";
        const res = await fetch(
          `${config.url}${sep}${config.param}=${parentValue}`,
          { headers: { Accept: "application/json" } }
        );
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        this._populate(data);
      } catch (err) {
        if (window.App?.isDev) console.error("[dependent-select]", err);
        this._reset();
      } finally {
        this.loading = false;
      }
    },

    _populate(options) {
      const initial = config.initial || "";
      const emptyLabel = config.emptyLabel || "---------";

      this._child.innerHTML = "";

      const blank = document.createElement("option");
      blank.value = "";
      blank.textContent = emptyLabel;
      this._child.appendChild(blank);

      for (const opt of options) {
        const el = document.createElement("option");
        el.value = opt.value;
        el.textContent = opt.label;
        if (String(opt.value) === String(initial)) el.selected = true;
        this._child.appendChild(el);
      }

      this._child.disabled = false;
    },

    _reset() {
      const msg = config.placeholder || "Selecciona primero el campo anterior";
      this._child.innerHTML = "";
      const opt = document.createElement("option");
      opt.value = "";
      opt.textContent = msg;
      this._child.appendChild(opt);
      this._child.disabled = true;
    },
  }));
});
