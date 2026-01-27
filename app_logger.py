"""
Structured Logging Module for Memecoin Analyzer

Provides:
- JSON structured logging
- Log levels (DEBUG, INFO, WARNING, ERROR)
- Sensitive data redaction (API keys, passwords, tokens)
- Performance timing helpers
- Context-aware logging for API calls and DB operations
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from contextlib import contextmanager
from datetime import datetime
from functools import wraps
from typing import Any, Callable, Generator

# Import centralized config
from config import LOG_LEVEL

# Sensitive patterns to redact
SENSITIVE_PATTERNS = [
    (re.compile(r'(api[_-]?key["\s:=]+)["\']?[\w-]{20,}["\']?', re.IGNORECASE), r'\1[REDACTED]'),
    (re.compile(r'(token["\s:=]+)["\']?[\w-]{20,}["\']?', re.IGNORECASE), r'\1[REDACTED]'),
    (re.compile(r'(password["\s:=]+)["\']?[^"\s,}]+["\']?', re.IGNORECASE), r'\1[REDACTED]'),
    (re.compile(r'(secret["\s:=]+)["\']?[\w-]{10,}["\']?', re.IGNORECASE), r'\1[REDACTED]'),
    (re.compile(r'(authorization["\s:=]+)["\']?[\w-]{20,}["\']?', re.IGNORECASE), r'\1[REDACTED]'),
    (re.compile(r'(Bearer\s+)[\w-]{20,}', re.IGNORECASE), r'\1[REDACTED]'),
]

# Sensitive field names to redact in dicts
SENSITIVE_FIELDS = {
    'api_key', 'apikey', 'api-key', 'token', 'access_token', 'refresh_token',
    'password', 'secret', 'authorization', 'auth', 'key', 'private_key',
    'birdeye_api_key', 'database_url', 'db_password'
}


class StructuredFormatter(logging.Formatter):
    """JSON structured log formatter."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }

        # Add extra fields from record
        if hasattr(record, 'extra_data'):
            log_data.update(record.extra_data)

        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        # Add source location for errors
        if record.levelno >= logging.ERROR:
            log_data['source'] = {
                'file': record.filename,
                'line': record.lineno,
                'function': record.funcName,
            }

        return json.dumps(log_data, default=str)


class ConsoleFormatter(logging.Formatter):
    """Human-readable console formatter with colors."""

    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
    }
    RESET = '\033[0m'

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.RESET)
        timestamp = datetime.now().strftime('%H:%M:%S')

        # Format extra data if present
        extra = ''
        if hasattr(record, 'extra_data') and record.extra_data:
            extra_items = [f'{k}={v}' for k, v in record.extra_data.items()]
            extra = f' [{", ".join(extra_items)}]'

        return f'{color}{timestamp} {record.levelname:7}{self.RESET} {record.getMessage()}{extra}'


def redact_sensitive(data: Any) -> Any:
    """Redact sensitive data from strings and dicts."""
    if isinstance(data, str):
        result = data
        for pattern, replacement in SENSITIVE_PATTERNS:
            result = pattern.sub(replacement, result)
        return result

    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            if key.lower() in SENSITIVE_FIELDS:
                result[key] = '[REDACTED]'
            elif isinstance(value, (dict, str)):
                result[key] = redact_sensitive(value)
            else:
                result[key] = value
        return result

    return data


class AppLogger:
    """Application logger with structured logging and context support."""

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

        # Remove existing handlers
        self.logger.handlers.clear()

        # Console handler (human-readable)
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(ConsoleFormatter())
        self.logger.addHandler(console_handler)

        # File handler (JSON structured)
        log_dir = os.path.dirname(os.path.abspath(__file__))
        log_file = os.path.join(log_dir, 'app.log')
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(StructuredFormatter())
        self.logger.addHandler(file_handler)

        # Prevent propagation to root logger
        self.logger.propagate = False

    def _log(self, level: int, message: str, **kwargs: Any) -> None:
        """Internal log method with extra data support."""
        # Redact sensitive data
        safe_kwargs = redact_sensitive(kwargs)

        record = self.logger.makeRecord(
            self.logger.name, level, '', 0, message, (), None
        )
        record.extra_data = safe_kwargs
        self.logger.handle(record)

    def debug(self, message: str, **kwargs: Any) -> None:
        """Debug level log."""
        self._log(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        """Info level log."""
        self._log(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        """Warning level log."""
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        """Error level log."""
        self._log(logging.ERROR, message, **kwargs)

    def exception(self, message: str, **kwargs: Any) -> None:
        """Error level log with exception info."""
        self._log(logging.ERROR, message, exc_info=True, **kwargs)


# Global loggers for different components
api_logger = AppLogger('api')
db_logger = AppLogger('database')
tracker_logger = AppLogger('tracker')
analyzer_logger = AppLogger('analyzer')


@contextmanager
def log_api_call(
    logger: AppLogger,
    endpoint: str,
    method: str = 'GET',
    **context: Any
) -> Generator[dict, None, None]:
    """Context manager for logging API calls with timing.

    Usage:
        with log_api_call(api_logger, 'https://api.example.com/data', token='abc') as ctx:
            response = requests.get(...)
            ctx['status_code'] = response.status_code
            ctx['response_size'] = len(response.content)
    """
    start_time = time.time()
    ctx: dict[str, Any] = {'success': False}

    logger.debug(f'API request started', endpoint=endpoint, method=method, **context)

    try:
        yield ctx
        ctx['success'] = True
    except Exception as e:
        ctx['error'] = str(e)
        ctx['error_type'] = type(e).__name__
        raise
    finally:
        duration_ms = round((time.time() - start_time) * 1000, 2)
        ctx['duration_ms'] = duration_ms

        if ctx['success']:
            logger.info(
                f'API request completed',
                endpoint=endpoint,
                method=method,
                duration_ms=duration_ms,
                **{k: v for k, v in ctx.items() if k not in ('success',)},
                **context
            )
        else:
            logger.error(
                f'API request failed',
                endpoint=endpoint,
                method=method,
                duration_ms=duration_ms,
                **ctx,
                **context
            )


@contextmanager
def log_db_operation(
    logger: AppLogger,
    operation: str,
    table: str | None = None,
    **context: Any
) -> Generator[dict, None, None]:
    """Context manager for logging database operations with timing.

    Usage:
        with log_db_operation(db_logger, 'INSERT', table='calls_received', call_id=123) as ctx:
            cursor.execute(...)
            ctx['rows_affected'] = cursor.rowcount
    """
    start_time = time.time()
    ctx: dict[str, Any] = {'success': False}

    logger.debug(f'DB operation started', operation=operation, table=table, **context)

    try:
        yield ctx
        ctx['success'] = True
    except Exception as e:
        ctx['error'] = str(e)
        ctx['error_type'] = type(e).__name__
        raise
    finally:
        duration_ms = round((time.time() - start_time) * 1000, 2)
        ctx['duration_ms'] = duration_ms

        log_data = {
            'operation': operation,
            'duration_ms': duration_ms,
            **{k: v for k, v in ctx.items() if k not in ('success',)},
            **context
        }
        if table:
            log_data['table'] = table

        if ctx['success']:
            logger.debug(f'DB operation completed', **log_data)
        else:
            logger.error(f'DB operation failed', **log_data)


def log_performance(logger: AppLogger, operation: str):
    """Decorator for logging function performance.

    Usage:
        @log_performance(tracker_logger, 'update_token_prices')
        def update_all_prices():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            logger.info(f'{operation} started')

            try:
                result = func(*args, **kwargs)
                duration_ms = round((time.time() - start_time) * 1000, 2)
                logger.info(f'{operation} completed', duration_ms=duration_ms)
                return result
            except Exception as e:
                duration_ms = round((time.time() - start_time) * 1000, 2)
                logger.error(
                    f'{operation} failed',
                    duration_ms=duration_ms,
                    error=str(e),
                    error_type=type(e).__name__
                )
                raise

        return wrapper
    return decorator


# Convenience function to get a logger
def get_logger(name: str) -> AppLogger:
    """Get a logger for a specific component."""
    return AppLogger(name)
