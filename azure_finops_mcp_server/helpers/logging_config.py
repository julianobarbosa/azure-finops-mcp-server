"""Comprehensive logging configuration for Azure FinOps MCP Server."""

import json
import logging
import logging.handlers
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from azure_finops_mcp_server.config import get_config


class StructuredFormatter(logging.Formatter):
    """Formatter that outputs structured JSON logs."""

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON.

        Args:
            record: Log record to format

        Returns:
            JSON formatted log string
        """
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields if present
        if hasattr(record, "subscription_id"):
            log_data["subscription_id"] = record.subscription_id
        if hasattr(record, "operation"):
            log_data["operation"] = record.operation
        if hasattr(record, "duration"):
            log_data["duration"] = record.duration
        if hasattr(record, "error_code"):
            log_data["error_code"] = record.error_code

        return json.dumps(log_data)


class ColoredFormatter(logging.Formatter):
    """Formatter that adds colors to console output."""

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record with colors.

        Args:
            record: Log record to format

        Returns:
            Colored log string
        """
        if record.levelname in self.COLORS:
            record.levelname = f"{self.COLORS[record.levelname]}{record.levelname}{self.RESET}"
        return super().format(record)


class PerformanceLogger:
    """Logger for performance metrics."""

    def __init__(self, logger: logging.Logger):
        """
        Initialize performance logger.

        Args:
            logger: Logger instance to use
        """
        self.logger = logger
        self.operations = {}

    def start_operation(self, operation_id: str, operation_type: str) -> None:
        """
        Start tracking an operation.

        Args:
            operation_id: Unique operation identifier
            operation_type: Type of operation
        """
        self.operations[operation_id] = {"type": operation_type, "start_time": datetime.utcnow()}

        self.logger.debug(
            f"Started operation: {operation_type}", extra={"operation": operation_type, "operation_id": operation_id}
        )

    def end_operation(self, operation_id: str, success: bool = True, details: Optional[Dict[str, Any]] = None) -> None:
        """
        End tracking an operation.

        Args:
            operation_id: Operation identifier
            success: Whether operation succeeded
            details: Additional details to log
        """
        if operation_id not in self.operations:
            self.logger.warning(f"Unknown operation ID: {operation_id}")
            return

        operation = self.operations.pop(operation_id)
        duration = (datetime.utcnow() - operation["start_time"]).total_seconds()

        log_level = logging.INFO if success else logging.ERROR
        log_data = {
            "operation": operation["type"],
            "operation_id": operation_id,
            "duration": duration,
            "success": success,
        }

        if details:
            log_data.update(details)

        self.logger.log(log_level, f"Completed operation: {operation['type']} in {duration:.2f}s", extra=log_data)


class AuditLogger:
    """Logger for audit events."""

    def __init__(self, logger: logging.Logger):
        """
        Initialize audit logger.

        Args:
            logger: Logger instance to use
        """
        self.logger = logger

    def log_api_call(
        self,
        method: str,
        endpoint: str,
        subscription_id: str,
        user: Optional[str] = None,
        status_code: Optional[int] = None,
    ) -> None:
        """
        Log an API call for audit purposes.

        Args:
            method: HTTP method
            endpoint: API endpoint
            subscription_id: Azure subscription ID
            user: User making the call
            status_code: Response status code
        """
        self.logger.info(
            f"API Call: {method} {endpoint}",
            extra={
                "audit_type": "api_call",
                "method": method,
                "endpoint": endpoint,
                "subscription_id": subscription_id,
                "user": user or "system",
                "status_code": status_code,
            },
        )

    def log_cost_query(
        self, subscription_id: str, date_range: str, total_cost: float, user: Optional[str] = None
    ) -> None:
        """
        Log a cost query for audit purposes.

        Args:
            subscription_id: Azure subscription ID
            date_range: Date range queried
            total_cost: Total cost found
            user: User making the query
        """
        self.logger.info(
            f"Cost Query: {subscription_id} for {date_range}",
            extra={
                "audit_type": "cost_query",
                "subscription_id": subscription_id,
                "date_range": date_range,
                "total_cost": total_cost,
                "user": user or "system",
            },
        )

    def log_resource_action(
        self, action: str, resource_type: str, resource_id: str, subscription_id: str, user: Optional[str] = None
    ) -> None:
        """
        Log a resource action for audit purposes.

        Args:
            action: Action taken
            resource_type: Type of resource
            resource_id: Resource identifier
            subscription_id: Azure subscription ID
            user: User performing action
        """
        self.logger.info(
            f"Resource Action: {action} on {resource_type}",
            extra={
                "audit_type": "resource_action",
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "subscription_id": subscription_id,
                "user": user or "system",
            },
        )


def setup_logging(
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    structured: bool = False,
    colored_console: bool = True,
) -> None:
    """
    Set up comprehensive logging for the application.

    Args:
        log_level: Logging level (uses config if not provided)
        log_file: Optional log file path
        structured: Use structured JSON logging
        colored_console: Use colored console output
    """
    config = get_config()
    level = getattr(logging, log_level or config.log_level)

    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers
    root_logger.handlers = []

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    if structured:
        console_formatter = StructuredFormatter()
    elif colored_console:
        console_formatter = ColoredFormatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    else:
        console_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # File handler if specified
    if log_file:
        # Create log directory if it doesn't exist
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Rotating file handler (10MB max, keep 5 backups)
        file_handler = logging.handlers.RotatingFileHandler(log_file, maxBytes=10 * 1024 * 1024, backupCount=5)  # 10MB
        file_handler.setLevel(level)

        if structured:
            file_formatter = StructuredFormatter()
        else:
            file_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    # Set specific loggers
    logging.getLogger("azure").setLevel(logging.WARNING)  # Reduce Azure SDK verbosity
    logging.getLogger("urllib3").setLevel(logging.WARNING)  # Reduce HTTP logging

    # Log startup
    root_logger.info(
        "Logging initialized",
        extra={"log_level": log_level or config.log_level, "structured": structured, "log_file": log_file},
    )


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the given name.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)


def get_performance_logger(name: str) -> PerformanceLogger:
    """
    Get a performance logger instance.

    Args:
        name: Logger name

    Returns:
        PerformanceLogger instance
    """
    return PerformanceLogger(logging.getLogger(name))


def get_audit_logger(name: str) -> AuditLogger:
    """
    Get an audit logger instance.

    Args:
        name: Logger name

    Returns:
        AuditLogger instance
    """
    return AuditLogger(logging.getLogger(f"audit.{name}"))
