import { $, $$, on } from "../../core/dom.js";
import { formatCurrency, calculateIVA } from "../../core/utils.js";

export class FormCalculator {
  constructor(containerSelector, options = {}) {
    this.container = $(containerSelector);
    if (!this.container) return;

    this.options = {
      taxRate: 0.16,
      currency: "MXN",
      autoCalculate: true,
      ...options,
    };

    this.init();
  }

  init() {
    if (this.options.autoCalculate) {
      $$('input[type="number"]', this.container).forEach((input) => {
        on(input, "input", () => this.calculate());
      });
    }

    this.calculate();
  }

  calculate() {
    const rows = $$(".calc-row", this.container);
    let subtotal = 0;

    rows.forEach((row) => {
      const price = this.parseNumber($(".calc-price", row)?.value);
      const quantity = this.parseNumber($(".calc-quantity", row)?.value);
      const rowTotal = price * quantity;

      subtotal += rowTotal;

      const totalEl = $(".calc-row-total", row);
      if (totalEl) {
        totalEl.textContent = formatCurrency(rowTotal, this.options.currency);
      }
    });

    const tax = calculateIVA(subtotal, this.options.taxRate);
    const total = subtotal + tax;

    this.updateDisplay(subtotal, tax, total);

    return { subtotal, tax, total };
  }

  updateDisplay(subtotal, tax, total) {
    const subtotalEl = $(".calc-subtotal", this.container);
    const taxEl = $(".calc-tax", this.container);
    const totalEl = $(".calc-total", this.container);

    if (subtotalEl) subtotalEl.textContent = formatCurrency(subtotal);
    if (taxEl) taxEl.textContent = formatCurrency(tax);
    if (totalEl) totalEl.textContent = formatCurrency(total);
  }

  parseNumber(value) {
    const num = parseFloat(value);
    return isNaN(num) ? 0 : num;
  }

  setTaxRate(rate) {
    this.options.taxRate = rate;
    this.calculate();
  }
}
