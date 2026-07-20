"""Tests for the Session Listener."""

import pytest
from PySide6.QtCore import QCoreApplication
from githelper.system_state.session_listener import SessionListener

def test_session_listener_callbacks() -> None:
    """Verify that callbacks are invoked when internal handlers are called."""
    # We can mock a QCoreApplication or use a real one if available,
    # but the simplest is to just instantiate with a dummy.
    app = QCoreApplication.instance()
    if not app:
        app = QCoreApplication([])

    listener = SessionListener(app)
    
    shutdown_called = False
    sleep_called = False
    resume_called = False
    
    def on_shutdown():
        nonlocal shutdown_called
        shutdown_called = True
        
    def on_sleep():
        nonlocal sleep_called
        sleep_called = True
        
    def on_resume():
        nonlocal resume_called
        resume_called = True
        
    listener.register_shutdown_handler(on_shutdown)
    listener.register_sleep_handler(on_sleep)
    listener.register_resume_handler(on_resume)
    
    # Trigger handlers directly
    listener._handle_shutdown()
    listener._handle_sleep()
    listener._handle_resume()
    
    assert shutdown_called is True
    assert sleep_called is True
    assert resume_called is True
