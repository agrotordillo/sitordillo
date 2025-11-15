# # ======================================
# # CABECERAS SEGURAS
# # ======================================
# SECURE_BROWSER_XSS_FILTER = True
# SECURE_CONTENT_TYPE_NOSNIFF = True

# SECURE_HSTS_INCLUDE_SUBDOMAINS = True
# SECURE_HSTS_PRELOAD = True
# SECURE_SSL_REDIRECT = True
# SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
# X_FRAME_OPTIONS = 'DENY'

# # ======================================
# # AXES — Protección de fuerza bruta
# # ======================================
# AXES_FAILURE_LIMIT = 5
# AXES_COOLOFF_TIME = 30  # minutos
# AXES_LOCK_OUT_BY_COMBINATION_USER_AND_IP = True

# # ======================================
# # COOKIES SEGURAS
# # ======================================

# SESSION_COOKIE_HTTPONLY = True
# SESSION_COOKIE_SAMESITE = 'Lax'

# CSRF_COOKIE_HTTPONLY = True
# CSRF_COOKIE_SAMESITE = 'Lax'

# CORS_ALLOW_ALL_ORIGINS = False


