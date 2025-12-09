// Selectores con cache
const selectorCache = new Map();

export const $ = (selector, context = document) => {
  const key = `${selector}-${context.id || "root"}`;
  if (!selectorCache.has(key)) {
    selectorCache.set(key, context.querySelector(selector));
  }
  return selectorCache.get(key);
};

export const $$ = (selector, context = document) =>
  Array.from(context.querySelectorAll(selector));

export const on = (element, event, handler, options = {}) => {
  element.addEventListener(event, handler, options);
  return () => element.removeEventListener(event, handler, options);
};

export const delegate = (parent, selector, event, handler) => {
  return on(parent, event, (e) => {
    const target = e.target.closest(selector);
    if (target && parent.contains(target)) {
      handler.call(target, e);
    }
  });
};

export const create = (tag, attrs = {}, children = []) => {
  const el = document.createElement(tag);

  if (attrs.className) el.className = attrs.className;
  if (attrs.dataset) Object.assign(el.dataset, attrs.dataset);

  Object.entries(attrs).forEach(([key, value]) => {
    if (["className", "dataset"].includes(key)) return;

    if (key.startsWith("on") && typeof value === "function") {
      const eventName = key.substring(2).toLowerCase();
      el.addEventListener(eventName, value);
    } else if (value != null) {
      el.setAttribute(key, value);
    }
  });

  children.forEach((child) => {
    if (typeof child === "string") {
      el.appendChild(document.createTextNode(child));
    } else if (child instanceof Node) {
      el.appendChild(child);
    }
  });

  return el;
};

export const serializeForm = (form) => {
  const data = new FormData(form);
  const result = {};
  for (const [key, value] of data.entries()) {
    result[key] = value;
  }
  return result;
};

export const clearCache = () => selectorCache.clear();
