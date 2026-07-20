"""Logger configuration and initialization.

Cross-cutting infrastructure used by all modules. Logs are local-only,
never transmitted anywhere.
"""

import logging


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for the given module name.
    
    Usage:
        from githelper.diagnostics.logger import get_logger
        logger = get_logger(__name__)
    """
    return logging.getLogger(name)
