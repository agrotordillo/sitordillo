export const formatCurrency = (amount, currency = "MXN") => {
  return new Intl.NumberFormat("es-MX", {
    style: "currency",
    currency,
  }).format(amount);
};

export const formatNumber = (number, decimals = 2) => {
  return new Intl.NumberFormat("es-MX", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(number);
};

export const calculateIVA = (amount, rate = 0.16) => amount * rate;

export const calculateTotal = (subtotal, taxRate = 0.16) => {
  const tax = subtotal * taxRate;
  return {
    subtotal: formatCurrency(subtotal),
    tax: formatCurrency(tax),
    total: formatCurrency(subtotal + tax),
  };
};

export const isValidEmail = (email) => {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
};

export const debounce = (func, wait) => {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
};

export const throttle = (func, limit) => {
  let inThrottle;
  return function executedFunction(...args) {
    if (!inThrottle) {
      func(...args);
      inThrottle = true;
      setTimeout(() => (inThrottle = false), limit);
    }
  };
};
