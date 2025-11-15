import os
from pathlib import Path

BASE_LOG_DIR = Path(os.getenv("LOG_DIR", Path(__file__).resolve().parent.parent / "logs"))
BASE_LOG_DIR.mkdir(exist_ok=True, parents=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,

    # ===============================
    # FORMATOS DE SALIDA
    # ===============================
    "formatters": {
        "verbose": {
            "format": "[{levelname}] {asctime} — {name}:{lineno} — {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname}: {message}",
            "style": "{",
        },
    },

    # ===============================
    # FILTROS (Solo si DEBUG=False)
    # ===============================
    "filters": {
        "require_debug_false": {
            "()": "django.utils.log.RequireDebugFalse"
        },
    },

    # ===============================
    # HANDLERS
    # ===============================
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "file_info": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "verbose",
            "filename": BASE_LOG_DIR / "info.log",
            "maxBytes": 5 * 1024 * 1024,  # 5 MB
            "backupCount": 3,
            "encoding": "utf8",
            "level": "INFO",
        },
        "file_error": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "verbose",
            "filename": BASE_LOG_DIR / "errors.log",
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 3,
            "encoding": "utf8",
            "level": "ERROR",
        },
        "mail_admins": {
            "level": "ERROR",
            "filters": ["require_debug_false"],
            "class": "django.utils.log.AdminEmailHandler",
        },
    },

    # ===============================
    # REGISTROS (LOGGERS)
    # ===============================
    "loggers": {
        "django": {
            "handlers": ["console", "file_info", "file_error"],
            "level": "INFO",
            "propagate": True,
        },
        "django.request": {
            "handlers": ["file_error", "mail_admins"],
            "level": "ERROR",
            "propagate": False,
        },
        "security": {
            "handlers": ["file_error"],
            "level": "WARNING",
            "propagate": False,
        },
        "axes.watch_login": {
            "handlers": ["file_error"],
            "level": "WARNING",
            "propagate": False,
        },
        "django.db.backends": {
            "handlers": ["file_error"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}
