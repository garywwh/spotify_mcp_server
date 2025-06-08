"""
Logging Configuration Module

This module provides centralized logging configuration for the Spotify MCP Server.
It supports both standard console logging and structured JSON logging.
"""

import logging
import json
import sys
from datetime import datetime, timezone
from typing import Any, Dict


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields if present
        if hasattr(record, 'extra_fields'):
            log_entry.update(record.extra_fields)
            
        return json.dumps(log_entry, ensure_ascii=False)


class ConsoleFormatter(logging.Formatter):
    """Custom console formatter with colors and structured output."""
    
    # Color codes for different log levels
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record for console output with colors."""
        color = self.COLORS.get(record.levelname, '')
        reset = self.RESET
        
        # Format timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')
        
        # Build the log message
        log_message = (
            f"{color}[{record.levelname}]{reset} "
            f"{timestamp} "
            f"{record.name} "
            f"({record.module}:{record.lineno}) - "
            f"{record.getMessage()}"
        )
        
        # Add exception info if present
        if record.exc_info:
            log_message += f"\n{self.formatException(record.exc_info)}"
            
        return log_message


def setup_logging(
    logger_name: str = "spotify_mcp_server",
    level: int = logging.INFO,
    enable_json: bool = True,
    enable_console: bool = True
) -> logging.Logger:
    """
    Set up logging configuration for the application.
    
    Args:
        logger_name: Name of the logger
        level: Logging level (default: INFO)
        enable_json: Whether to enable JSON structured logging to stderr
        enable_console: Whether to enable console logging to stdout
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)
    
    # Clear any existing handlers
    logger.handlers.clear()
    
    if enable_console:
        # Console handler for human-readable output
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(ConsoleFormatter())
        logger.addHandler(console_handler)
    
    if enable_json:
        # JSON handler for structured logging
        json_handler = logging.StreamHandler(sys.stderr)
        json_handler.setLevel(level)
        json_handler.setFormatter(JSONFormatter())
        logger.addHandler(json_handler)
    
    # Prevent propagation to root logger
    logger.propagate = False
    
    return logger


def get_logger(name: str = None) -> logging.Logger:
    """
    Get a logger instance with the specified name.
    
    Args:
        name: Logger name (defaults to calling module name)
        
    Returns:
        Logger instance
    """
    if name is None:
        # Get the calling module name
        import inspect
        frame = inspect.currentframe().f_back
        name = frame.f_globals.get('__name__', 'spotify_mcp_server')
    
    return logging.getLogger(name)


def log_with_context(logger: logging.Logger, level: int, message: str, **context: Any) -> None:
    """
    Log a message with additional context fields.
    
    Args:
        logger: Logger instance
        level: Log level
        message: Log message
        **context: Additional context fields to include in structured logs
    """
    # Create a log record with extra fields
    record = logger.makeRecord(
        logger.name, level, "", 0, message, (), None
    )
    record.extra_fields = context
    logger.handle(record)


# Convenience functions for different log levels with context
def log_info(logger: logging.Logger, message: str, **context: Any) -> None:
    """Log info message with context."""
    log_with_context(logger, logging.INFO, message, **context)


def log_error(logger: logging.Logger, message: str, **context: Any) -> None:
    """Log error message with context."""
    log_with_context(logger, logging.ERROR, message, **context)


def log_warning(logger: logging.Logger, message: str, **context: Any) -> None:
    """Log warning message with context."""
    log_with_context(logger, logging.WARNING, message, **context)


def log_debug(logger: logging.Logger, message: str, **context: Any) -> None:
    """Log debug message with context."""
    log_with_context(logger, logging.DEBUG, message, **context)