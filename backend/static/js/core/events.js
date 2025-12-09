class EventSystem {
  constructor() {
    if (EventSystem.instance) return EventSystem.instance;
    EventSystem.instance = this;

    this.events = new Map();
  }

  on(event, callback) {
    if (!this.events.has(event)) {
      this.events.set(event, new Set());
    }
    this.events.get(event).add(callback);

    return () => this.off(event, callback);
  }

  off(event, callback) {
    if (this.events.has(event)) {
      this.events.get(event).delete(callback);
    }
  }

  emit(event, data = null) {
    if (this.events.has(event)) {
      this.events.get(event).forEach((callback) => {
        try {
          callback(data);
        } catch (error) {
          console.error(`Error in event ${event}:`, error);
        }
      });
    }
  }
}

export const events = new EventSystem();
