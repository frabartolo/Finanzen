#!/usr/bin/env python3
"""
Zentrales Error-Handling und Retry-Mechanismus
"""

import time
import logging
from functools import wraps
from typing import Callable, Any, Optional

logger = logging.getLogger(__name__)


class FinanzenError(Exception):
    """Basis-Exception für alle Finanzen-App Fehler"""
    pass


class DatabaseError(FinanzenError):
    """Datenbankfehler"""
    pass


class FinTSError(FinanzenError):
    """FinTS/Banking-Fehler"""
    pass


class ConfigError(FinanzenError):
    """Konfigurationsfehler"""
    pass


class PDFParseError(FinanzenError):
    """PDF-Parsing-Fehler"""
    pass


def retry(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0, 
          exceptions: tuple = (Exception,)):
    """
    Decorator für automatische Wiederholungen bei Fehlern
    
    Args:
        max_attempts: Maximale Anzahl Versuche
        delay: Initiale Wartezeit zwischen Versuchen (Sekunden)
        backoff: Multiplikator für Wartezeit bei jedem Versuch
        exceptions: Tuple von Exceptions die wiederholt werden sollen
    
    Example:
        @retry(max_attempts=3, delay=2.0)
        def unstable_function():
            # Code der fehlschlagen kann
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            current_delay = delay
            last_exception = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_attempts:
                        logger.error(
                            f"❌ {func.__name__} fehlgeschlagen nach {max_attempts} Versuchen: {e}"
                        )
                        raise
                    
                    logger.warning(
                        f"⚠️ {func.__name__} fehlgeschlagen (Versuch {attempt}/{max_attempts}): {e}"
                    )
                    logger.info(f"   Warte {current_delay:.1f}s vor erneutem Versuch...")
                    
                    time.sleep(current_delay)
                    current_delay *= backoff
            
            if last_exception:
                raise last_exception
        
        return wrapper
    return decorator


def safe_execute(func: Callable, *args, default: Any = None, 
                 log_error: bool = True, **kwargs) -> Any:
    """
    Führt eine Funktion sicher aus und fängt alle Exceptions ab
    
    Args:
        func: Auszuführende Funktion
        *args: Argumente für die Funktion
        default: Rückgabewert bei Fehler
        log_error: Ob Fehler geloggt werden sollen
        **kwargs: Keyword-Argumente für die Funktion
    
    Returns:
        Funktions-Rückgabewert oder default bei Fehler
    
    Example:
        result = safe_execute(risky_function, arg1, arg2, default=[], log_error=True)
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        if log_error:
            logger.error(f"❌ Fehler in {func.__name__}: {e}")
        return default


class ErrorContext:
    """Context Manager für strukturiertes Error-Handling"""
    
    def __init__(self, operation_name: str, 
                 suppress_errors: bool = False,
                 on_error: Optional[Callable] = None):
        """
        Args:
            operation_name: Name der Operation für Logs
            suppress_errors: Ob Fehler unterdrückt werden sollen
            on_error: Callback-Funktion bei Fehler
        """
        self.operation_name = operation_name
        self.suppress_errors = suppress_errors
        self.on_error = on_error
        self.error = None
    
    def __enter__(self):
        logger.info(f"▶️ Starte: {self.operation_name}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            logger.info(f"✅ Abgeschlossen: {self.operation_name}")
            return False
        
        self.error = exc_val
        logger.error(f"❌ Fehler in {self.operation_name}: {exc_val}")
        
        if self.on_error:
            try:
                self.on_error(exc_val)
            except Exception as e:
                logger.error(f"❌ Fehler im Error-Handler: {e}")
        
        # True = Exception unterdrücken, False = Exception weitergeben
        return self.suppress_errors


def validate_config(config: dict, required_fields: list) -> bool:
    """
    Validiert ob alle erforderlichen Felder in der Config vorhanden sind
    
    Args:
        config: Config-Dictionary
        required_fields: Liste erforderlicher Felder
    
    Returns:
        True wenn valid, sonst Exception
    
    Raises:
        ConfigError: Wenn erforderliche Felder fehlen
    """
    missing = [field for field in required_fields if field not in config]
    
    if missing:
        raise ConfigError(f"Fehlende Konfigurationsfelder: {', '.join(missing)}")
    
    return True


# Beispiel-Verwendung
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Retry-Decorator
    @retry(max_attempts=3, delay=1.0)
    def unstable_function():
        import random
        if random.random() < 0.7:
            raise Exception("Zufälliger Fehler")
        return "Erfolg"
    
    # ErrorContext
    with ErrorContext("Test Operation", suppress_errors=True) as ctx:
        print("In ErrorContext")
        # raise Exception("Test-Fehler")
    
    print(f"Error was: {ctx.error}")
    
    # Safe Execute
    result = safe_execute(lambda: 1/0, default=-1)
    print(f"Safe result: {result}")
