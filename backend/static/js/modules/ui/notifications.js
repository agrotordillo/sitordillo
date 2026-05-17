import { create } from "../../core/dom.js";

class NotificationSystem {
  constructor() {
    if (NotificationSystem.instance) return NotificationSystem.instance;
    NotificationSystem.instance = this;

    this.container = null;
    this.initContainer();
  }

  initContainer() {
    this.container = create("div", {
      id: "notifications-container",
      className: "fixed top-4 right-4 z-50 space-y-2",
    });
    document.body.appendChild(this.container);
  }

  show(options) {
    const {
      title = "",
      message,
      type = "info",
      duration = 5000,
    } = typeof options === "string" ? { message: options } : options;

    const notification = this.createNotification(title, message, type);
    this.container.appendChild(notification);

    setTimeout(() => {
      notification.classList.remove("opacity-0", "translate-x-full");
      notification.classList.add("opacity-100", "translate-x-0");
    }, 10);

    if (duration > 0) {
      setTimeout(() => this.remove(notification), duration);
    }

    return notification;
  }

  createNotification(title, message, type) {
    const types = {
      success: {
        bg: "bg-green-50",
        border: "border-green-200",
        text: "text-green-800",
        icon: "✅",
      },
      error: {
        bg: "bg-red-50",
        border: "border-red-200",
        text: "text-red-800",
        icon: "❌",
      },
      warning: {
        bg: "bg-yellow-50",
        border: "border-yellow-200",
        text: "text-yellow-800",
        icon: "⚠️",
      },
      info: {
        bg: "bg-blue-50",
        border: "border-blue-200",
        text: "text-blue-800",
        icon: "ℹ️",
      },
    };

    const config = types[type] || types.info;

    return create(
      "div",
      {
        className: `notification p-4 rounded-xl shadow-lg border transform transition-all duration-300 
                       ${config.bg} ${config.border} ${config.text}
                       opacity-0 translate-x-full`,
      },
      [
        create("div", { className: "flex items-start" }, [
          create("span", { className: "text-xl mr-3" }, [config.icon]),
          create("div", { className: "flex-1" }, [
            title && create("h4", { className: "font-semibold mb-1" }, [title]),
            create("p", { className: "text-sm" }, [message]),
          ]),
          create(
            "button",
            {
              className: "ml-4 text-gray-500 hover:text-gray-700",
              onclick: (e) => this.remove(e.target.closest(".notification")),
            },
            ["×"]
          ),
        ]),
      ]
    );
  }

  remove(notification) {
    if (notification && notification.parentNode === this.container) {
      notification.classList.remove("opacity-100", "translate-x-0");
      notification.classList.add("opacity-0", "translate-x-full");

      setTimeout(() => notification.remove(), 300);
    }
  }

  success(message, title = "Éxito") {
    return this.show({ title, message, type: "success" });
  }

  error(message, title = "Error") {
    return this.show({ title, message, type: "error", duration: 7000 });
  }

  info(message, title = "Información") {
    return this.show({ title, message, type: "info" });
  }
}

export const notifications = new NotificationSystem();
