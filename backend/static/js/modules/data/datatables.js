import { $, on } from "../../core/dom.js";

export class DataTableManager {
  constructor(tableSelector, options = {}) {
    this.table = $(tableSelector);
    if (!this.table || !window.DataTable) return;

    this.options = {
      pageLength: 25,
      language: {
        url: "//cdn.datatables.net/plug-ins/1.10.25/i18n/Spanish.json",
      },
      ...options,
    };

    this.dataTable = null;
    this.init();
  }

  init() {
    this.dataTable = new window.DataTable(this.table, this.options);
    this.setupEvents();
  }

  setupEvents() {
    on(this.table, "draw.dt", () => {
      this.table.dispatchEvent(new CustomEvent("datatable:draw"));
    });
  }

  reload() {
    if (this.dataTable && this.dataTable.ajax) {
      this.dataTable.ajax.reload();
    }
  }

  addRow(data) {
    if (this.dataTable) {
      this.dataTable.row.add(data).draw();
    }
  }

  destroy() {
    if (this.dataTable) {
      this.dataTable.destroy();
    }
  }
}
