import queue
import threading
import trio

from PyQt5.QtCore import QCoreApplication
from PyQt5.QtWidgets import QMainWindow, QMenu, QSystemTrayIcon
from PyQt5.QtGui import QIcon
from structlog import get_logger

from parsec import __version__ as PARSEC_VERSION

from parsec.core.devices_manager import (
    DeviceManagerError,
    load_device_with_password,
    load_device_with_pkcs11,
)

from parsec.core.backend_connection import BackendHandshakeError
from parsec.core.gui import settings
from parsec.core import logged_core_factory
from parsec.core.gui.login_widget import LoginWidget
from parsec.core.gui.central_widget import CentralWidget
from parsec.core.gui.custom_widgets import ask_question, show_error
from parsec.core.gui.starting_guide_dialog import StartingGuideDialog
from parsec.core.gui.ui.main_window import Ui_MainWindow


logger = get_logger()


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self, core_config, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.current_device = None
        self.core_config = core_config
        self.portal = None
        self.core = None
        self.cancel_scope = None
        self.core_thread = None
        self.core_queue = queue.Queue(3)
        self.force_close = False
        self.close_requested = False
        self.tray = None

        self.login_widget = LoginWidget(core_config=self.core_config, parent=self)
        self.widget_center.layout().addWidget(self.login_widget)
        self.central_widget = CentralWidget(core_config=self.core_config, parent=self)
        self.widget_center.layout().addWidget(self.central_widget)

        self.add_tray_icon()
        self.setWindowTitle("Parsec - Community Edition - {}".format(PARSEC_VERSION))
        self.tray_message_shown = False

        self.central_widget.logout_requested.connect(self.logout)
        self.login_widget.login_with_password_clicked.connect(self.login_with_password)
        self.login_widget.login_with_pkcs11_clicked.connect(self.login_with_pkcs11)

        self.show_login_widget()

    def show_starting_guide(self):
        s = StartingGuideDialog(parent=self)
        s.exec_()

    def add_tray_icon(self):
        if not QSystemTrayIcon.isSystemTrayAvailable() or not settings.get_value(
            "global/tray_enabled", "true"
        ):
            return
        self.tray = QSystemTrayIcon(self)
        menu = QMenu()
        action = menu.addAction(QCoreApplication.translate(self.__class__.__name__, "Show window"))
        action.triggered.connect(self.show_top)
        action = menu.addAction(QCoreApplication.translate(self.__class__.__name__, "Exit"))
        action.triggered.connect(self.close_app)
        self.tray.setContextMenu(menu)
        self.tray.setIcon(QIcon(":/icons/images/icons/parsec.png"))
        self.tray.activated.connect(self.tray_activated)
        self.tray.show()

    def showMaximized(self):
        super().showMaximized()
        QCoreApplication.processEvents()
        # self.show_starting_guide()

    def tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_top()

    def show_top(self):
        self.show()
        self.raise_()

    def start_core(self):
        def _run_core():
            async def _run():
                try:
                    portal = trio.BlockingTrioPortal()
                    self.core_queue.put(portal)
                    with trio.open_cancel_scope() as cancel_scope:
                        self.core_queue.put(cancel_scope)
                        async with logged_core_factory(
                            self.core_config, self.current_device
                        ) as core:
                            self.core_queue.put(core)
                            await trio.sleep_forever()
                # If we have an exception, we never put the core object in the queue. Since the
                # main thread except something to be there, we put the exception.
                except Exception as exc:
                    self.core_queue.put(exc)

            trio.run(_run)

        self.core_config = self.core_config.evolve(mountpoint_enabled=True)
        self.core_thread = threading.Thread(target=_run_core)
        self.core_thread.start()
        self.portal = self.core_queue.get()
        self.cancel_scope = self.core_queue.get()
        self.core = self.core_queue.get()
        # Core object can be an exception if one occured with the logged_core_factory.
        # We join the thread by calling stop_core(), then re-raise the exception.
        if isinstance(self.core, Exception):
            exc = self.core
            self.portal = None
            self.cancel_scope = None
            self.stop_core()
            raise exc
        self.central_widget.set_core_attributes(core=self.core, portal=self.portal)
        settings.set_value(
            "last_device",
            "{}:{}".format(
                self.core.device.organization_addr.organization_id, self.core.device.device_id
            ),
        )

    def stop_core(self):
        if self.portal and self.cancel_scope:
            self.portal.run_sync(self.cancel_scope.cancel)
        if self.core_thread:
            self.core_thread.join()
        self.portal = None
        self.core = None
        self.current_device = None
        self.cancel_scope = None
        self.core_thread = None
        self.central_widget.set_core_attributes(None, None)

    def logout(self):
        if self.core_thread:
            self.stop_core()
        self.show_login_widget()

    def login_with_password(self, organization_id, device_id, password):
        try:
            self.current_device = load_device_with_password(
                self.core_config.config_dir, organization_id, device_id, password
            )
            self.start_core()
            self.show_central_widget()
        except DeviceManagerError:
            show_error(self, QCoreApplication.translate("MainWindow", "Authentication failed."))
        except BackendHandshakeError:
            show_error(
                self,
                QCoreApplication.translate("MainWindow", "User not registered in the backend."),
            )
        except RuntimeError:
            show_error(self, QCoreApplication.translate("MainWindow", "Mountpoint already in use."))

    def login_with_pkcs11(self, organization_id, device_id, pkcs11_pin, pkcs11_key, pkcs11_token):
        try:
            self.current_device = load_device_with_pkcs11(
                self.core_config.config_dir, organization_id, device_id
            )
            self.start_core()
            self.show_central_widget()
        except DeviceManagerError:
            show_error(self, QCoreApplication.translate("MainWindow", "Authentication failed."))
        except BackendHandshakeError:
            show_error(
                self,
                QCoreApplication.translate("MainWindow", "User not registered in the backend."),
            )
        except RuntimeError:
            show_error(self, QCoreApplication.translate("MainWindow", "Mountpoint already in use."))

    def close_app(self):
        self.close_requested = True
        self.close()

    def closeEvent(self, event):
        if (
            not settings.get_value("global/tray_enabled")
            or not QSystemTrayIcon.isSystemTrayAvailable()
            or self.close_requested
            or self.core_config.debug
            or self.force_close
        ):
            if not self.force_close:
                result = ask_question(
                    self,
                    QCoreApplication.translate(self.__class__.__name__, "Confirmation"),
                    QCoreApplication.translate("MainWindow", "Are you sure you want to quit ?"),
                )
                if not result:
                    event.ignore()
                    self.close_requested = False
                    return
                event.accept()
            else:
                event.accept()
            if self.tray:
                self.tray.hide()
            self.stop_core()
        else:
            if self.tray and not self.tray_message_shown:
                self.tray.showMessage(
                    "Parsec", QCoreApplication.translate("MainWindow", "Parsec is still running.")
                )
                self.tray_message_shown = True
            event.ignore()
            self.hide()

    def show_central_widget(self):
        self._hide_all_widgets()
        self.central_widget.show()
        self.central_widget.reset()

    def show_login_widget(self):
        self._hide_all_widgets()
        self.login_widget.reset()
        self.login_widget.show()

    def _hide_all_widgets(self):
        self.login_widget.hide()
        self.central_widget.hide()
