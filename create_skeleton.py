import os

base_dir = r"D:\Project\Project\GitHelper"
src_dir = os.path.join(base_dir, "src", "githelper")
test_dir = os.path.join(base_dir, "tests")

# 1. Create Source Packages
packages = {
    "": "GitHelper — A lightweight desktop companion for protecting uncommitted Git work.",
    "app": "Application Layer — Orchestration and lifecycle coordination.",
    "domain": "Domain Core — Pure business logic with zero external dependencies.",
    "git_integration": "Git Integration Layer — The only module permitted to invoke the git executable.",
    "monitor": "Repository Monitor Service — Change detection via filesystem events and reconciliation polling.",
    "system_state": "System State Listener — OS shutdown, sleep, and battery detection.",
    "system_state/platform": "Platform-specific adapters for OS signal detection.",
    "snapshot": "Snapshot Manager — Recovery snapshot creation, storage, retrieval, and cleanup.",
    "stable_compare": "Stable and Compare Module — Stable version marking and comparison.",
    "persistence": "Persistence Layer — All locally persisted application state.",
    "ui": "UI Layer — PySide6 code exclusively. Contains no business logic.",
    "ui/dialogs": "UI dialogs — One file per dialog, named after what the dialog shows.",
    "ui/widgets": "Reusable UI widgets shared across dialogs.",
    "diagnostics": "Diagnostics — Logging subsystem. Named 'diagnostics' to avoid shadowing Python's standard library 'logging' module.",
    "common": "Narrow shared utilities. NOT a general-purpose dumping ground. Only genuinely cross-cutting constants and base exception types."
}

for pkg, docstring in packages.items():
    pkg_path = os.path.join(src_dir, pkg)
    os.makedirs(pkg_path, exist_ok=True)
    init_file = os.path.join(pkg_path, "__init__.py")
    if not os.path.exists(init_file):
        with open(init_file, "w") as f:
            f.write(f'"""{docstring}"""\n')

# 2. Create __main__.py
main_file = os.path.join(src_dir, "__main__.py")
if not os.path.exists(main_file):
    with open(main_file, "w") as f:
        f.write('"""Application entry point. Contains no logic — launches the app."""\n\nimport sys\n\n\ndef main() -> int:\n    """Launch GitHelper application."""\n    from githelper.app.orchestrator import Orchestrator\n\n    app = Orchestrator()\n    return app.run(sys.argv)\n\n\nif __name__ == "__main__":\n    sys.exit(main())\n')

# 3. Create empty modules with docstrings
modules = {
    "app/orchestrator.py": "Application Layer orchestrator. Owns the QApplication lifecycle, creates and wires all services, mediates between UI and backend modules.",
    "app/events.py": "Cross-module event definitions. Shared vocabulary of events the Orchestrator routes between modules.",
    "git_integration/git_client.py": "Git client. Wraps the system git binary via subprocess. Provides a narrow set of operations: status, commit, push, log, diff-against-commit.",
    "git_integration/errors.py": "Structured error types for the Git Integration Layer.",
    "monitor/repository_monitor.py": "Repository Monitor coordinator. Combines filesystem watcher and reconciliation poller signals into change-state summaries.",
    "monitor/filesystem_watcher.py": "Filesystem watcher. Wraps the watchdog library.",
    "monitor/reconciliation_poller.py": "Reconciliation poller. Low-frequency correctness backstop that periodically verifies repository state via git.",
    "system_state/power_listener.py": "Power listener. Wraps psutil for battery-state polling.",
    "system_state/session_listener.py": "Session listener. Platform-agnostic coordinator for shutdown, restart, and sleep signal detection.",
    "system_state/platform/windows_adapter.py": "Windows adapter. Handles WM_QUERYENDSESSION, WM_ENDSESSION, WM_POWERBROADCAST via Qt native event filters.",
    "system_state/platform/macos_adapter.py": "macOS adapter. Stub for future macOS shutdown/sleep/battery signal detection.",
    "system_state/platform/linux_adapter.py": "Linux adapter. Stub for future Linux shutdown/sleep/battery signal detection.",
    "snapshot/snapshot_manager.py": "Snapshot Manager coordinator. Handles startup recovery detection, restore, and discard.",
    "snapshot/rolling_snapshot_service.py": "Rolling snapshot service. Background-timer-driven service that periodically creates recovery snapshots when uncommitted work exists.",
    "snapshot/snapshot_storage.py": "Snapshot storage. The only module in the codebase permitted to perform snapshot file I/O.",
    "stable_compare/stable_manager.py": "Stable manager. Owns reading/writing the Stable marker for a repository via the Persistence Layer.",
    "stable_compare/compare_service.py": "Compare service. Computes the categorized file-level comparison between current working state and the Stable commit via the Git Integration Layer.",
    "persistence/state_store.py": "State store. The only module permitted to perform direct I/O against GitHelper's local state store.",
    "persistence/schema.py": "Database schema definition and migration logic.",
    "ui/main_window.py": "Main window. Currently unused — GitHelper is tray-first with no persistent main window.",
    "ui/tray_icon.py": "System tray icon. The persistent entry point to GitHelper.",
    "ui/dialogs/reminder_dialog.py": "Commit Popup (Reminder dialog).",
    "ui/dialogs/snapshot_recovery_dialog.py": "Recovery Popup. Surfaces on startup when an unexpected shutdown is detected.",
    "ui/dialogs/stable_compare_view.py": "Stable Version Window and Compare Window.",
    "ui/dialogs/settings_dialog.py": "Settings Window. Tabbed configuration surface.",
    "ui/widgets/repository_list_widget.py": "Repository list widget. Reusable component displaying watched repositories with status indicators.",
    "diagnostics/logger.py": "Logger configuration and initialization.",
    "diagnostics/log_config.py": "Logging configuration.",
    "common/constants.py": "Application-wide constants.",
    "common/exceptions.py": "Base exception types that other packages' error modules may extend."
}

for mod, docstring in modules.items():
    mod_path = os.path.join(src_dir, mod)
    if not os.path.exists(mod_path):
        with open(mod_path, "w") as f:
            f.write(f'"""{docstring}"""\n')

# 4. Create Tests directory and subdirectories
test_pkgs = ["domain", "git_integration", "monitor", "system_state", "snapshot", "stable_compare", "persistence", "ui", "app", "fixtures", "fixtures/sample_repositories", "fixtures/sample_state_files"]
for pkg in test_pkgs:
    os.makedirs(os.path.join(test_dir, pkg), exist_ok=True)
    if "fixtures" not in pkg:
        init_file = os.path.join(test_dir, pkg, "__init__.py")
        if not os.path.exists(init_file):
            open(init_file, "w").close()

# 5. Create test modules
test_modules = {
    "domain/test_risk_engine.py": "Tests for the Risk Engine.",
    "domain/test_time_engine.py": "Tests for the Time Engine.",
    "domain/test_reminder_scheduler.py": "Tests for the Reminder Scheduler.",
    "domain/test_models.py": "Tests for domain models.",
    "git_integration/test_git_client.py": "Integration tests for the Git client.",
    "monitor/test_repository_monitor.py": "Tests for the Repository Monitor coordinator.",
    "monitor/test_filesystem_watcher.py": "Tests for the Filesystem Watcher.",
    "system_state/test_session_listener.py": "Tests for the Session Listener.",
    "snapshot/test_snapshot_manager.py": "Tests for the Snapshot Manager.",
    "snapshot/test_rolling_snapshot_service.py": "Tests for the Rolling Snapshot Service.",
    "stable_compare/test_stable_manager.py": "Tests for the Stable Manager.",
    "stable_compare/test_compare_service.py": "Tests for the Compare Service.",
    "persistence/test_state_store.py": "Tests for the State Store.",
    "ui/test_tray_icon.py": "Tests for the Tray Icon.",
    "app/test_orchestrator.py": "Tests for the Orchestrator."
}

test_template = '"""{docstring}"""\n\n\nclass TestPlaceholder:\n    """Placeholder tests to verify test infrastructure."""\n\n    def test_module_importable(self) -> None:\n        """Verify the module can be imported."""\n        assert True\n'

for mod, docstring in test_modules.items():
    mod_path = os.path.join(test_dir, mod)
    if not os.path.exists(mod_path):
        with open(mod_path, "w") as f:
            f.write(test_template.format(docstring=docstring))

# 6. Conftest
conftest_file = os.path.join(test_dir, "conftest.py")
if not os.path.exists(conftest_file):
    with open(conftest_file, "w") as f:
        f.write('"""Shared test fixtures for GitHelper test suite."""\n\nimport pytest\n')

# 7. Other directories
for d in ["resources/icons", "resources/tray", "resources/styles", "packaging/windows", "packaging/macos", "packaging/linux", "scripts", "docs"]:
    p = os.path.join(base_dir, d)
    os.makedirs(p, exist_ok=True)
    open(os.path.join(p, ".gitkeep"), "w").close()

# 8. Build script
build_script = os.path.join(base_dir, "scripts", "build.bat")
if not os.path.exists(build_script):
    with open(build_script, "w") as f:
        f.write('@echo off\nREM GitHelper Build Script\nREM Requires: pip install pyinstaller\necho Building GitHelper...\npyinstaller --name GitHelper --windowed --icon resources/icons/githelper.ico --add-data "resources;resources" src/githelper/__main__.py\necho Build complete. Output in dist/GitHelper/\n')

print("Skeleton created successfully.")
