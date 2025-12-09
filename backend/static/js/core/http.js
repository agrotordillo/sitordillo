class HTTPClient {
  constructor() {
    if (HTTPClient.instance) return HTTPClient.instance;
    HTTPClient.instance = this;

    this.baseURL = "/api";
    this.csrfToken = this.getCSRFToken();
    this.defaultHeaders = {
      "Content-Type": "application/json",
      "X-Requested-With": "XMLHttpRequest",
    };
  }

  getCSRFToken() {
    return (
      document.querySelector("[name=csrfmiddlewaretoken]")?.value ||
      document.cookie.match(/csrftoken=([^;]+)/)?.[1]
    );
  }

  async request(endpoint, options = {}) {
    const url = endpoint.startsWith("http")
      ? endpoint
      : `${this.baseURL}${endpoint}`;

    const headers = {
      ...this.defaultHeaders,
      ...options.headers,
    };

    if (this.csrfToken) {
      headers["X-CSRFToken"] = this.csrfToken;
    }

    const config = {
      method: options.method || "GET",
      headers,
      credentials: "same-origin",
      ...options,
    };

    if (config.body && typeof config.body === "object") {
      config.body = JSON.stringify(config.body);
    }

    try {
      const response = await fetch(url, config);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      console.error("HTTP Error:", error);
      throw error;
    }
  }

  get(endpoint, options = {}) {
    return this.request(endpoint, { ...options, method: "GET" });
  }

  post(endpoint, data, options = {}) {
    return this.request(endpoint, { ...options, method: "POST", body: data });
  }

  put(endpoint, data, options = {}) {
    return this.request(endpoint, { ...options, method: "PUT", body: data });
  }

  delete(endpoint, options = {}) {
    return this.request(endpoint, { ...options, method: "DELETE" });
  }
}

export const http = new HTTPClient();
