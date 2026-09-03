"""Cloudflare WARP GUI — a PyQt5 front-end for warp-cli.

Provides a main window and a system-tray icon to register a device, pick the
operating mode / tunnel protocol / DNS family filter, and connect or disconnect
WARP without touching a terminal.
"""

from __future__ import annotations

import datetime as _dt
import sys
from functools import partial

from PyQt5.QtCore import Qt, QThreadPool, QTimer
from PyQt5.QtWidgets import (
    QAction, QActionGroup, QApplication, QCheckBox, QComboBox, QDialog,
    QDialogButtonBox, QFormLayout, QFrame, QGridLayout, QGroupBox, QHBoxLayout,
    QInputDialog, QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox,
    QPlainTextEdit, QPushButton, QSizePolicy, QSystemTrayIcon, QVBoxLayout,
    QWidget,
)

from warp_gui import icons
from warp_gui.backend import (
    FAMILIES, MODES, PROTOCOLS, Result, WarpCli, WarpError,
)
from warp_gui.config import Config
from warp_gui.worker import Worker

APP_NAME = "Cloudflare WARP GUI"
POLL_MS = 3000


def derive_state(status: str | None) -> str:
    """Map a warp-cli status string onto one of our four visual states."""
    s = (status or "").strip().lower()
    if "disconnect" in s:  # matches "disconnected" and "disconnecting"
        return "disconnected"
    if s == "connected":
        return "connected"
    if "connecting" in s:
        return "connecting"
    if "unable" in s or "error" in s:
        return "error"
    return "disconnected"


PILL_STYLE = (
    "QLabel{{background:{bg};color:white;border-radius:11px;"
    "padding:3px 12px;font-weight:600;}}"
)


class RegisterDialog(QDialog):
    """Collects an optional Zero Trust org and a required ToS acceptance."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Register New Device")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        info = QLabel(
            "Register this device with Cloudflare WARP.\n"
            "Leave the organization blank for a free personal (Consumer) "
            "account. Enter your Zero Trust team name to join an organization."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        form = QFormLayout()
        self.org_edit = QLineEdit()
        self.org_edit.setPlaceholderText("Leave empty for a free personal account")
        form.addRow("Organization (optional):", self.org_edit)
        layout.addLayout(form)

        self.tos = QCheckBox(
            "I accept the Cloudflare WARP Terms of Service"
        )
        layout.addWidget(self.tos)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self.ok_button = buttons.button(QDialogButtonBox.Ok)
        self.ok_button.setText("Register")
        self.ok_button.setEnabled(False)
        self.tos.toggled.connect(self.ok_button.setEnabled)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self):
        return self.org_edit.text().strip() or None, self.tos.isChecked()


class MainWindow(QMainWindow):
    def __init__(self, warp: WarpCli, app: QApplication):
        super().__init__()
        self.warp = warp
        self.app = app
        self.config = Config()
        self.pool = QThreadPool.globalInstance()
        self.state = "disconnected"
        self._status_busy = False
        self._suppress_signals = False
        self._force_quit = False

        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(icons.state_icon("connected"))
        self.setMinimumWidth(460)

        self._build_ui()
        self._build_tray()

        # Restore persisted UI state (family filter + saved profiles).
        self._sync_family_combo()
        self.refresh_profiles()

        # First load + periodic status polling.
        self.refresh_all()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_status)
        self.timer.start(POLL_MS)

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        # --- header: title + status pill ---
        header = QHBoxLayout()
        title = QLabel("Cloudflare WARP")
        title.setStyleSheet("font-size:18px;font-weight:700;")
        header.addWidget(title)
        header.addStretch(1)
        self.status_pill = QLabel("…")
        self.status_pill.setStyleSheet(PILL_STYLE.format(bg="#8a8f98"))
        header.addWidget(self.status_pill)
        root.addLayout(header)

        self.reason_label = QLabel("")
        self.reason_label.setStyleSheet("color:gray;")
        root.addWidget(self.reason_label)

        # --- big connect / disconnect button ---
        self.toggle_button = QPushButton("Connect")
        self.toggle_button.setMinimumHeight(46)
        self.toggle_button.setStyleSheet(
            "QPushButton{font-size:15px;font-weight:600;border-radius:8px;}"
        )
        self.toggle_button.clicked.connect(self.on_toggle)
        root.addWidget(self.toggle_button)

        # --- settings group ---
        settings_box = QGroupBox("Configuration")
        grid = QGridLayout(settings_box)
        grid.setColumnStretch(1, 1)

        self.mode_combo = QComboBox()
        for value, label, desc in MODES:
            self.mode_combo.addItem(label, value)
            self.mode_combo.setItemData(
                self.mode_combo.count() - 1, desc, Qt.ToolTipRole
            )
        self.mode_combo.activated.connect(self.on_mode_changed)
        grid.addWidget(QLabel("Mode:"), 0, 0)
        grid.addWidget(self.mode_combo, 0, 1)

        self.protocol_combo = QComboBox()
        for value, label, desc in PROTOCOLS:
            self.protocol_combo.addItem(label, value)
            self.protocol_combo.setItemData(
                self.protocol_combo.count() - 1, desc, Qt.ToolTipRole
            )
        self.protocol_combo.activated.connect(self.on_protocol_changed)
        grid.addWidget(QLabel("Tunnel protocol:"), 1, 0)
        grid.addWidget(self.protocol_combo, 1, 1)

        self.family_combo = QComboBox()
        for value, label, desc in FAMILIES:
            self.family_combo.addItem(label, value)
            self.family_combo.setItemData(
                self.family_combo.count() - 1, desc, Qt.ToolTipRole
            )
        self.family_combo.setToolTip(
            "warp-cli cannot report the current filter, so this shows the last "
            "value applied here (defaults to Off)."
        )
        self.family_combo.activated.connect(self.on_family_changed)
        grid.addWidget(QLabel("DNS family filter:"), 2, 0)
        grid.addWidget(self.family_combo, 2, 1)

        root.addWidget(settings_box)

        # --- profiles group ---
        profile_box = QGroupBox("Profiles")
        profile_box.setToolTip(
            "Save the three settings above under a name and re-apply them later."
        )
        pl = QHBoxLayout(profile_box)
        self.profile_combo = QComboBox()
        self.profile_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.profile_apply_btn = QPushButton("Apply")
        self.profile_apply_btn.clicked.connect(self.on_profile_apply)
        self.profile_save_btn = QPushButton("Save Current…")
        self.profile_save_btn.clicked.connect(self.on_profile_save)
        self.profile_delete_btn = QPushButton("Delete")
        self.profile_delete_btn.clicked.connect(self.on_profile_delete)
        pl.addWidget(self.profile_combo, 1)
        pl.addWidget(self.profile_apply_btn)
        pl.addWidget(self.profile_save_btn)
        pl.addWidget(self.profile_delete_btn)
        root.addWidget(profile_box)

        # --- registration group ---
        reg_box = QGroupBox("Device Registration")
        reg_layout = QVBoxLayout(reg_box)
        self.reg_label = QLabel("Checking registration…")
        self.reg_label.setWordWrap(True)
        self.reg_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        reg_layout.addWidget(self.reg_label)

        reg_buttons = QHBoxLayout()
        self.register_button = QPushButton("Register New Device…")
        self.register_button.clicked.connect(self.on_register)
        self.delete_button = QPushButton("Delete Registration")
        self.delete_button.clicked.connect(self.on_delete_registration)
        reg_buttons.addWidget(self.register_button)
        reg_buttons.addWidget(self.delete_button)
        reg_buttons.addStretch(1)
        reg_layout.addLayout(reg_buttons)
        root.addWidget(reg_box)

        # --- actions row ---
        actions = QHBoxLayout()
        self.verify_button = QPushButton("Verify (warp=on)")
        self.verify_button.clicked.connect(self.on_verify)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_all)
        actions.addWidget(self.verify_button)
        actions.addWidget(self.refresh_button)
        actions.addStretch(1)
        root.addLayout(actions)

        # --- log ---
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        root.addWidget(line)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(120)
        self.log_view.setPlaceholderText("Activity log…")
        root.addWidget(self.log_view)

    def _build_tray(self):
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(icons.state_icon(self.state))
        self.tray.setToolTip(APP_NAME)

        menu = QMenu()
        self.tray_status = menu.addAction("Status: …")
        self.tray_status.setEnabled(False)
        menu.addSeparator()

        self.tray_toggle = menu.addAction("Connect")
        self.tray_toggle.triggered.connect(self.on_toggle)

        # Mode submenu (radio group).
        mode_menu = menu.addMenu("Mode")
        self.mode_group = QActionGroup(self)
        self.mode_group.setExclusive(True)
        self.tray_mode_actions = {}
        for value, label, desc in MODES:
            act = QAction(label, self, checkable=True)
            act.setToolTip(desc)
            act.triggered.connect(partial(self.apply_mode, value))
            self.mode_group.addAction(act)
            mode_menu.addAction(act)
            self.tray_mode_actions[value] = act

        menu.addSeparator()
        show_action = menu.addAction("Show Window")
        show_action.triggered.connect(self.show_and_raise)
        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(self.quit_app)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.on_tray_activated)
        self.tray.show()

    # -------------------------------------------------------------- logging

    def log(self, message: str):
        if not message:
            return
        stamp = _dt.datetime.now().strftime("%H:%M:%S")
        # Collapse multi-line output into the log readably.
        first, *rest = message.strip().splitlines()
        self.log_view.appendPlainText(f"[{stamp}] {first}")
        for extra in rest:
            self.log_view.appendPlainText(f"          {extra}")

    # ------------------------------------------------------------- refresh

    def refresh_all(self):
        self.refresh_status()
        self.refresh_settings()
        self.refresh_registration()

    def refresh_status(self):
        if self._status_busy:
            return
        self._status_busy = True
        self._spawn(self.warp.status, self.on_status, self.on_bg_error)

    def on_status(self, data: dict):
        self._status_busy = False
        state = derive_state(data.get("status"))
        self.state = state
        # Coerce to str defensively — warp-cli can return structured values.
        status_text = str(data.get("status", "Unknown"))
        reason = str(data.get("reason", "") or "")

        self.status_pill.setText(status_text)
        self.status_pill.setStyleSheet(
            PILL_STYLE.format(bg=icons.STATE_COLORS.get(state, "#8a8f98"))
        )
        self.reason_label.setText(reason)
        self.setWindowIcon(icons.state_icon(state))
        self.tray.setIcon(icons.state_icon(state))
        self.tray.setToolTip(f"{APP_NAME} — {status_text}")
        self.tray_status.setText(f"Status: {status_text}")

        connected = state in ("connected", "connecting")
        label = "Disconnect" if connected else "Connect"
        self.toggle_button.setText(label)
        self.tray_toggle.setText(label)
        self.toggle_button.setEnabled(state != "connecting")

    def on_bg_error(self, message: str):
        self._status_busy = False
        self.log(f"Error: {message}")

    def refresh_settings(self):
        self._spawn(self.warp.settings, self.on_settings, self.on_bg_error)

    def on_settings(self, settings: dict):
        mode = settings.get("operation_mode")
        protocol = (settings.get("warp_tunnel_protocol") or "").lower()
        self._suppress_signals = True
        if mode is not None:
            idx = self.mode_combo.findData(mode)
            if idx >= 0:
                self.mode_combo.setCurrentIndex(idx)
            act = self.tray_mode_actions.get(mode)
            if act:
                act.setChecked(True)
        for value, _, _ in PROTOCOLS:
            if value.lower() == protocol:
                pidx = self.protocol_combo.findData(value)
                if pidx >= 0:
                    self.protocol_combo.setCurrentIndex(pidx)
                break
        self._suppress_signals = False

    def refresh_registration(self):
        self._spawn(
            self.warp.registration_show, self.on_registration, self.on_bg_error
        )

    def on_registration(self, data: dict):
        if not data.get("registered"):
            self.reg_label.setText(
                "No device is registered yet.\n"
                "Click “Register New Device…” to get started."
            )
            self.register_button.setText("Register New Device…")
            self.delete_button.setEnabled(False)
            return
        fields = data.get("fields", {})
        account = fields.get("Account type", "Unknown")
        device_id = fields.get("Device ID") or fields.get("ID", "—")
        self.reg_label.setText(
            f"Registered — {account} account\nDevice ID: {device_id}"
        )
        self.register_button.setText("Re-register Device…")
        self.delete_button.setEnabled(True)

    # --------------------------------------------------------------- actions

    def _spawn(self, fn, on_done, on_error):
        worker = Worker(fn)
        worker.signals.finished.connect(on_done)
        worker.signals.error.connect(on_error)
        self.pool.start(worker)

    def run_action(self, fn, busy_msg: str, reconnect_hint: bool = False):
        self.log(busy_msg)
        # Applying a mode/protocol/DNS change on a live tunnel can leave WARP
        # reporting "Connected" while DNS/routing is briefly broken until the
        # tunnel is re-established. Warn the user so they know the recovery.
        hint = reconnect_hint and self.state in ("connected", "connecting")
        self._set_busy(True)

        def done(result):
            self._set_busy(False)
            if isinstance(result, Result):
                self.log(result.message)
            if hint and (not isinstance(result, Result) or result.ok):
                self.log("Note: if connectivity drops, click Disconnect then "
                         "Connect to re-establish the tunnel.")
            self.refresh_all()

        def failed(message):
            self._set_busy(False)
            self.log(f"Error: {message}")

        self._spawn(fn, done, failed)

    def _set_busy(self, busy: bool):
        for w in (
            self.toggle_button, self.mode_combo, self.protocol_combo,
            self.family_combo, self.register_button, self.delete_button,
            self.verify_button, self.refresh_button, self.profile_combo,
            self.profile_save_btn,
        ):
            w.setEnabled(not busy)
        # Apply/Delete additionally require at least one saved profile.
        has_profiles = bool(self.config.profiles)
        self.profile_apply_btn.setEnabled(not busy and has_profiles)
        self.profile_delete_btn.setEnabled(not busy and has_profiles)

    def on_toggle(self):
        if self.state in ("connected", "connecting"):
            self.run_action(self.warp.disconnect, "Disconnecting…")
        else:
            self.run_action(self.warp.connect, "Connecting…")

    # NOTE: A QComboBox emits `activated` while its popup is still being torn
    # down. Mutating the combo (disabling it, changing its index) synchronously
    # inside that handler re-enters Qt's popup code and can crash. So every
    # combo handler defers its real work to the next event-loop tick with
    # QTimer.singleShot(0, ...), by which point the popup has fully closed.

    def on_mode_changed(self, index: int):
        if self._suppress_signals:
            return
        mode = self.mode_combo.itemData(index)
        QTimer.singleShot(0, lambda: self.apply_mode(mode))

    def apply_mode(self, mode: str):
        if self._suppress_signals or not mode:
            return
        self.run_action(partial(self.warp.set_mode, mode),
                        f"Setting mode → {mode}…", reconnect_hint=True)

    def on_protocol_changed(self, index: int):
        if self._suppress_signals:
            return
        protocol = self.protocol_combo.itemData(index)
        QTimer.singleShot(0, lambda: self.run_action(
            partial(self.warp.set_protocol, protocol),
            f"Setting tunnel protocol → {protocol}…", reconnect_hint=True,
        ))

    def on_family_changed(self, index: int):
        if self._suppress_signals:
            return
        value = self.family_combo.itemData(index)
        if not value:
            return
        QTimer.singleShot(0, lambda: self._apply_family(value))

    def _apply_family(self, value: str):
        self.config.set_family(value)  # remember it (no read-back from warp-cli)
        self.run_action(
            partial(self.warp.set_families, value),
            f"Setting DNS family filter → {value}…", reconnect_hint=True,
        )

    def _sync_family_combo(self):
        """Reflect the persisted family value in the combo (defaults to Off)."""
        self._suppress_signals = True
        idx = self.family_combo.findData(self.config.family)
        self.family_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._suppress_signals = False

    # -------------------------------------------------------------- profiles

    def refresh_profiles(self, select: str | None = None):
        self._suppress_signals = True
        self.profile_combo.clear()
        names = sorted(self.config.profiles, key=str.lower)
        if names:
            for name in names:
                self.profile_combo.addItem(name, name)
            if select and select in names:
                self.profile_combo.setCurrentIndex(
                    self.profile_combo.findData(select)
                )
        else:
            self.profile_combo.addItem("(no profiles saved)", None)
        self._suppress_signals = False
        has = bool(names)
        self.profile_apply_btn.setEnabled(has)
        self.profile_delete_btn.setEnabled(has)

    def _current_selections(self):
        """The three settings currently shown in the dropdowns."""
        return (
            self.mode_combo.currentData(),
            self.protocol_combo.currentData(),
            self.family_combo.currentData(),
        )

    def on_profile_save(self):
        default = self.profile_combo.currentData() or ""
        name, ok = QInputDialog.getText(
            self, "Save Profile",
            "Profile name (saves the current Mode, Protocol and DNS filter):",
            QLineEdit.Normal, default,
        )
        name = name.strip()
        if not ok or not name:
            return
        if name in self.config.profiles:
            reply = QMessageBox.question(
                self, "Overwrite Profile",
                f"A profile named “{name}” already exists. Overwrite it?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return
        mode, protocol, family = self._current_selections()
        self.config.set_profile(name, mode, protocol, family)
        self.refresh_profiles(select=name)
        self.log(
            f"Saved profile “{name}” (mode={mode}, protocol={protocol}, "
            f"family={family})."
        )

    def on_profile_apply(self):
        name = self.profile_combo.currentData()
        if not name or name not in self.config.profiles:
            return
        p = self.config.profiles[name]
        mode, protocol, family = p.get("mode"), p.get("protocol"), p.get("family")
        # Optimistically reflect the profile in the dropdowns + persist family.
        self._suppress_signals = True
        if mode is not None:
            i = self.mode_combo.findData(mode)
            if i >= 0:
                self.mode_combo.setCurrentIndex(i)
        if protocol is not None:
            i = self.protocol_combo.findData(protocol)
            if i >= 0:
                self.protocol_combo.setCurrentIndex(i)
        if family is not None:
            i = self.family_combo.findData(family)
            if i >= 0:
                self.family_combo.setCurrentIndex(i)
            self.config.set_family(family)
        self._suppress_signals = False
        self.run_action(
            partial(self.warp.apply_settings, mode, protocol, family),
            f"Applying profile “{name}”…", reconnect_hint=True,
        )

    def on_profile_delete(self):
        name = self.profile_combo.currentData()
        if not name or name not in self.config.profiles:
            return
        reply = QMessageBox.question(
            self, "Delete Profile", f"Delete the profile “{name}”?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        self.config.delete_profile(name)
        self.refresh_profiles()
        self.log(f"Deleted profile “{name}”.")

    def on_register(self):
        dialog = RegisterDialog(self)
        if dialog.exec_() != QDialog.Accepted:
            return
        org, accepted = dialog.values()
        if not accepted:
            return
        target = org or "a free personal account"
        self.run_action(
            partial(self.warp.register_new, org, True),
            f"Registering device with {target}…",
        )

    def on_delete_registration(self):
        reply = QMessageBox.question(
            self,
            "Delete Registration",
            "Delete this device's WARP registration?\n"
            "You will need to register again before connecting.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.run_action(
                self.warp.registration_delete, "Deleting registration…"
            )

    def on_verify(self):
        self.log("Verifying via cloudflare.com/cdn-cgi/trace …")
        self._set_busy(True)

        def done(result: dict):
            self._set_busy(False)
            self.log(result.get("message", ""))
            if result.get("ok"):
                self.tray.showMessage(
                    APP_NAME, result["message"], icons.state_icon("connected"), 4000
                )

        self._spawn(self.warp.verify_trace, done, lambda m: (
            self._set_busy(False), self.log(f"Error: {m}")
        ))

    # ----------------------------------------------------------------- tray

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:  # left click
            if self.isVisible() and not self.isMinimized():
                self.hide()
            else:
                self.show_and_raise()

    def show_and_raise(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        """Closing the window hides it to the tray instead of quitting."""
        if self._force_quit or not self.tray.isVisible():
            event.accept()
            return
        event.ignore()
        self.hide()
        self.tray.showMessage(
            APP_NAME,
            "Still running in the system tray. Right-click the icon to quit.",
            icons.state_icon(self.state),
            3000,
        )

    def quit_app(self):
        self._force_quit = True
        self.timer.stop()
        self.tray.hide()
        # Let any in-flight warp-cli worker finish before tearing down, so the
        # interpreter never shuts down with live pool threads.
        self.pool.waitForDone(3000)
        self.app.quit()


def _install_excepthook():
    """Keep the app alive on an unhandled Python exception in a slot.

    Without a custom hook, PyQt5 aborts the whole process on an uncaught
    exception raised inside a signal handler. We log it and carry on instead.
    """
    import traceback

    def hook(exc_type, exc_value, exc_tb):
        traceback.print_exception(exc_type, exc_value, exc_tb)
        sys.stderr.flush()

    sys.excepthook = hook


def main() -> int:
    _install_excepthook()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)  # keep running in the tray

    warp = WarpCli()
    if not warp.available():
        QMessageBox.critical(
            None, APP_NAME,
            "warp-cli was not found on your PATH.\n\n"
            "Install the Cloudflare WARP client (cloudflare-warp) and ensure "
            "the warp-svc service is running, then start this app again.",
        )
        return 1

    if not QSystemTrayIcon.isSystemTrayAvailable():
        # Not fatal — the main window still works without a tray.
        print("Warning: no system tray detected; running window-only.")

    window = MainWindow(warp, app)
    window.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
