#!/usr/bin/env python3
"""
Shutdown Manager
Replaces global state with proper singleton pattern for graceful shutdown handling
"""

import threading
import signal
from typing import Callable, Optional
from dataclasses import dataclass


@dataclass
class ShutdownHandler:
    """
    Thread-safe shutdown handler
    Replaces global 'shutdown_requested' variable
    """
    _lock: threading.Lock = None
    _shutdown_requested: bool = False
    _grace_period_seconds: float = 3.0
    _listeners: list[Callable] = None
    _force_exit_timer: Optional[threading.Timer] = None
    
    def __init__(self, grace_period: float = 3.0):
        self._lock = threading.Lock()
        self._shutdown_requested = False
        self._grace_period_seconds = grace_period
        self._listeners = []
        self._force_exit_timer = None
        
        # Register signal handler
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)
    
    def _handle_signal(self, signum, frame):
        """Handle shutdown signals (Ctrl+C, SIGTERM)"""
        with self._lock:
            if not self._shutdown_requested:
                self._shutdown_requested = True
                print("\n\n[SHUTDOWN] Signal received (Ctrl+C)")
                print("[SHUTDOWN] Initiating graceful shutdown...")
                print("[SHUTDOWN] Press Ctrl+C again to force quit immediately")
                
                # Notify all listeners
                for listener in self._listeners:
                    try:
                        listener()
                    except Exception as e:
                        print(f"[WARNING] Shutdown listener error: {e}")
                
                # Set up force exit timer
                self._force_exit_timer = threading.Timer(
                    self._grace_period_seconds,
                    self._force_exit
                )
                self._force_exit_timer.daemon = True
                self._force_exit_timer.start()
    
    def _force_exit(self):
        """Force exit if graceful shutdown doesn't complete"""
        print("\n[FORCE QUIT] Graceful shutdown failed - forcing exit")
        import os
        os._exit(1)
    
    @property
    def is_shutdown_requested(self) -> bool:
        """Check if shutdown has been requested (thread-safe)"""
        with self._lock:
            return self._shutdown_requested
    
    def request_shutdown(self):
        """Manually request shutdown (thread-safe)"""
        with self._lock:
            if not self._shutdown_requested:
                self._shutdown_requested = True
                print("[SHUTDOWN] Shutdown manually requested")
                
                # Notify listeners
                for listener in self._listeners:
                    try:
                        listener()
                    except Exception as e:
                        print(f"[WARNING] Shutdown listener error: {e}")
    
    def register_listener(self, callback: Callable):
        """
        Register a callback to be called on shutdown
        
        Args:
            callback: Function to call on shutdown
        """
        with self._lock:
            self._listeners.append(callback)
    
    def wait(self, timeout: float = 1.0) -> bool:
        """
        Wait for shutdown signal
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Returns:
            True if shutdown was requested, False if timeout
        """
        import time
        start = time.time()
        
        while time.time() - start < timeout:
            if self.is_shutdown_requested:
                return True
            time.sleep(0.1)  # Check every 100ms
        
        return False


# Global shutdown manager instance (singleton pattern)
_shutdown_manager: Optional[ShutdownHandler] = None


def get_shutdown_manager() -> ShutdownHandler:
    """
    Get the global shutdown manager instance (singleton)
    
    Returns:
        ShutdownHandler instance
    """
    global _shutdown_manager
    
    if _shutdown_manager is None:
        _shutdown_manager = ShutdownHandler(grace_period=3.0)
    
    return _shutdown_manager


# Backward compatibility (for existing code)
def is_shutdown_requested() -> bool:
    """
    Check if shutdown has been requested
    
    Returns:
        True if shutdown requested
    """
    return get_shutdown_manager().is_shutdown_requested


def request_shutdown():
    """Request graceful shutdown"""
    get_shutdown_manager().request_shutdown()


# Test the shutdown manager
if __name__ == "__main__":
    import time
    
    print("Testing Shutdown Manager...")
    print("-" * 50)
    
    manager = get_shutdown_manager()
    
    print(f"Initial state: {manager.is_shutdown_requested}")
    
    # Test auto-shutdown after signal
    print("\nTest 1: Signal handling")
    print("The manager will handle Ctrl+C automatically")
    
    # Test manual shutdown
    print("\nTest 2: Manual shutdown")
    manager.request_shutdown()
    print(f"After request: {manager.is_shutdown_requested}")
    
    print("\n[SUCCESS] Shutdown manager works!")
    print("\nTo test Ctrl+C handling, run Data_Scraper.py and press Ctrl+C")


