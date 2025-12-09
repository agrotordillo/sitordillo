import { $, $$, on, create } from "../../core/dom.js";

export class FormValidator {
  constructor(formSelector, options = {}) {
    this.form =
      typeof formSelector === "string" ? $(formSelector) : formSelector;

    if (!this.form) return;

    this.options = {
      validateOnSubmit: true,
      validateOnBlur: true,
      showErrors: true,
      ...options,
    };

    this.errors = new Map();
    this.init();
  }

  init() {
    if (this.options.validateOnSubmit) {
      on(this.form, "submit", (e) => this.handleSubmit(e));
    }

    if (this.options.validateOnBlur) {
      $$("[data-validate], [required]", this.form).forEach((field) => {
        on(field, "blur", () => this.validateField(field));
      });
    }
  }

  handleSubmit(e) {
    if (!this.validate()) {
      e.preventDefault();
    }
  }

  validate() {
    this.clearErrors();

    const fields = $$("[data-validate], [required]", this.form);
    let isValid = true;

    fields.forEach((field) => {
      if (!this.validateField(field)) {
        isValid = false;
      }
    });

    return isValid;
  }

  validateField(field) {
    const value = field.value.trim();
    this.clearFieldError(field);

    if (field.required && !value) {
      this.showFieldError(field, "Este campo es requerido");
      return false;
    }

    if (
      field.type === "email" &&
      value &&
      !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)
    ) {
      this.showFieldError(field, "Email no válido");
      return false;
    }

    if (field.type === "number" && value) {
      const numValue = parseFloat(value);
      const min = parseFloat(field.min);
      const max = parseFloat(field.max);

      if (!isNaN(min) && numValue < min) {
        this.showFieldError(field, `Mínimo ${min}`);
        return false;
      }

      if (!isNaN(max) && numValue > max) {
        this.showFieldError(field, `Máximo ${max}`);
        return false;
      }
    }

    return true;
  }

  showFieldError(field, message) {
    if (!this.options.showErrors) return;

    field.classList.add("border-red-500");

    const errorEl = create(
      "div",
      {
        className: "field-error text-red-500 text-sm mt-1",
      },
      [message]
    );

    field.parentNode.appendChild(errorEl);
  }

  clearFieldError(field) {
    field.classList.remove("border-red-500");

    const errorEl = field.nextElementSibling;
    if (errorEl && errorEl.classList.contains("field-error")) {
      errorEl.remove();
    }
  }

  clearErrors() {
    this.errors.clear();
    $$("[data-validate], [required]", this.form).forEach((field) => {
      this.clearFieldError(field);
    });
  }
}
