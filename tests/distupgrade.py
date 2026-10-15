"""GTK regression tests; no package operations or network requests are run."""
import contextlib
import io
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import MainWindow as module
from gi.repository import Gtk, GLib


def drain():
    context = GLib.MainContext.default()
    for _ in range(1000):
        if not context.pending():
            return
        context.iteration(False)
    raise AssertionError("GTK event queue did not drain")


class DistUpgradeTests(unittest.TestCase):
    def setUp(self):
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)
        self.errors = []
        self.patch = patch.object(sys, "excepthook", lambda *args: self.errors.append(args[1]))
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.w = module.MainWindow.__new__(module.MainWindow)
        builder = Gtk.Builder.new_from_file(str(Path(module.__file__).parents[1] / "ui/MainWindow.glade"))
        self.w.GtkBuilder = builder
        self.w.define_components()
        self.w.define_variables()
        # Also permits running these tests against the unmodified baseline.
        self.w.distupgrade_operation = None
        self.w.dist_new_sources = "deb http://depo.pardus.org.tr/pardus yirmibes main"
        self.w.dist_new_version = "Pardus 25"
        self.w.Package = SimpleNamespace(required_changes_upgrade=Mock(return_value={
            "changes_available": False, "to_install": [], "to_upgrade": []}))
        self.w.set_settings_widgets = Mock()
        self.w.startControlDistUpgradeProcess = Mock()
        self.w.startDistUpgradeProcess = Mock()
        self.w.distupgrade_vte_start_process = Mock()
        self.w.distupgrade_vteterm = Mock()
        self.w.apt_update = Mock()
        self.w.upgrade_vte_start_process = Mock()
        self.w.fix_vte_start_process = Mock()
        self.w.dpkgconfigure_vte_start_process = Mock()
        self.w.settings_vte_start_process = Mock()
        self.w.item_sh_app = Gtk.MenuItem()
        self.w.Application = SimpleNamespace(args={"page": "updateinfo"})
        self.w.ui_main_stack.set_visible_child_name("ok")
        self.w.ui_distupgrade_stack.set_visible_child_name("control")
        self.w.laststack = "ok"
        self.home = next(o for o in builder.get_objects()
                         if isinstance(o, Gtk.Button) and o.get_name() == "homecontrol")
        self.home.connect("clicked", self.w.on_ui_controldistup_button_clicked)
        self.w.ui_menusettings_button = builder.get_object("ui_menusettings_button")
        self.w.ui_menusettings_button.connect("clicked", self.w.on_ui_menusettings_button_clicked)
        self.thread_patch = patch.object(module.threading, "Thread")
        self.thread = self.thread_patch.start()
        self.addCleanup(self.thread_patch.stop)
        self.dialog_patch = patch.object(module, "ErrorDialog")
        self.dialog = self.dialog_patch.start()
        self.addCleanup(self.dialog_patch.stop)

    def tearDown(self):
        if self.w.autoupdate_monitoring_glibid:
            GLib.source_remove(self.w.autoupdate_monitoring_glibid)
        if self.w.autoupdate_glibid:
            GLib.source_remove(self.w.autoupdate_glibid)
        drain()
        for obj in self.w.GtkBuilder.get_objects():
            if isinstance(obj, Gtk.Window):
                obj.destroy()
        drain()
        self.assertEqual(self.errors, [])

    def control(self):
        self.home.emit("clicked")

    def preflight_done(self):
        self.w.before_distupgradables_worker_thread()
        drain()

    def prepare(self):
        self.w.ui_main_stack.set_visible_child_name("distupgrade")
        self.w.ui_distupgrade_stack.set_visible_child_name("install")
        self.w.on_ui_distupgrade_button_clicked(None)

    def download(self):
        self.w.ui_main_stack.set_visible_child_name("distupgrade")
        self.w.ui_distupgrade_stack.set_visible_child_name("distupdateinfo")
        self.w.on_ui_distuptodown_button_clicked(None)

    def roundtrip(self):
        self.w.ui_menusettings_button.emit("clicked")
        self.w.ui_menusettings_button.emit("clicked")
        self.home.emit("clicked")

    def test_control_reserved_before_worker_and_double_click(self):
        self.control()
        self.assertTrue(self.w.upgrade_inprogress)
        self.control()
        self.assertEqual(self.thread.call_count, 1)

    def test_navigation_does_not_restart_control(self):
        self.control()
        self.preflight_done()
        self.roundtrip()
        self.assertEqual(self.thread.call_count, 1)
        self.w.startControlDistUpgradeProcess.assert_called_once()
        self.assertTrue(self.w.upgrade_inprogress)

    def test_preparing_reboot_survives_settings_home(self):
        self.prepare()
        self.roundtrip()
        self.thread.assert_not_called()
        self.assertEqual(self.w.ui_distupgrade_stack.get_visible_child_name(), "install")
        self.assertTrue(self.w.upgrade_inprogress)

    def test_downloaded_packages_are_resumed(self):
        self.download()
        self.w.distupgrade_vte_on_done(self.w.distupgrade_vteterm, 0)
        self.roundtrip()
        self.thread.assert_not_called()
        self.assertEqual(self.w.ui_distupgrade_stack.get_visible_child_name(), "install")

    def test_download_cannot_be_started_twice(self):
        self.download()
        self.roundtrip()
        self.w.on_ui_distuptodown_button_clicked(None)
        self.w.distupgrade_vte_start_process.assert_called_once()
        self.thread.assert_not_called()

    def test_package_changes_invalidate_completed_plan_only(self):
        self.download()
        file = SimpleNamespace(get_path=lambda: "/var/lib/dpkg/status")
        self.w.on_apt_changed(None, file, None, None)
        self.assertEqual(self.w.ui_distupgrade_stack.get_visible_child_name(), "download")
        self.w.distupgrade_vte_on_done(self.w.distupgrade_vteterm, 0)
        self.w.on_apt_changed(None, file, None, None)
        self.assertEqual(self.w.ui_distupgrade_stack.get_visible_child_name(), "control")

    def test_explicit_cache_cleanup_invalidates_downloaded_plan(self):
        self.download()
        self.w.distupgrade_vte_on_done(self.w.distupgrade_vteterm, 0)
        self.w.on_ui_settingsaptclear_button_clicked(None)
        self.w.settings_vte_start_process.assert_called_once()
        self.assertEqual(self.w.ui_distupgrade_stack.get_visible_child_name(), "control")

    def test_prepare_cannot_be_started_twice(self):
        self.prepare()
        self.w.on_ui_distupgrade_button_clicked(None)
        self.w.startDistUpgradeProcess.assert_called_once()

    def test_other_apt_operation_prevents_distupgrade(self):
        for flag in ("upgrade_inprogress", "update_inprogress"):
            for action in (self.control, self.download, self.prepare):
                with self.subTest(flag=flag, action=action.__name__):
                    self.w.upgrade_inprogress = self.w.update_inprogress = False
                    setattr(self.w, flag, True)
                    self.w.ui_distupgrade_stack.set_visible_child_name("control")
                    action()
        self.thread.assert_not_called()
        self.w.startDistUpgradeProcess.assert_not_called()
        self.w.distupgrade_vte_start_process.assert_not_called()

    def test_busy_refresh_keeps_cached_page_and_scheduled_checks(self):
        self.w.Package.updatecache = Mock(return_value=True)
        self.w.Package.upgradable = Mock(return_value=[])
        self.w.indicator = Mock()
        self.w.item_systemstatus = Gtk.MenuItem()
        self.w.pargnome23 = False
        self.w.isbroken = False
        self.w.icon_normal = "normal"
        self.w.UserSettings = SimpleNamespace(config_update_interval=3600,
                                             config_update_lastupdate=123, writeConfig=Mock())
        self.w.SystemSettings = SimpleNamespace(config_update_interval=None)
        for interval in (3600, -1):
            with self.subTest(interval=interval):
                self.w.UserSettings.config_update_interval = interval
                self.w.update_inprogress = True
                self.w.ui_main_stack.set_visible_child_name("spinner")
                self.w.onAptUpdateProcessExit(123, 11 << 8)
                self.assertFalse(self.w.update_inprogress)
                self.assertEqual(self.w.ui_main_stack.get_visible_child_name(), "ok")
                self.w.UserSettings.writeConfig.assert_not_called()
                self.assertEqual(self.w.UserSettings.config_update_lastupdate, 123)
                if interval == -1:
                    self.assertIsNone(self.w.autoupdate_glibid)
                else:
                    self.assertIsNotNone(self.w.autoupdate_glibid)
                    self.assertIsNotNone(GLib.MainContext.default().find_source_by_id(self.w.autoupdate_glibid))
                    GLib.source_remove(self.w.autoupdate_glibid)
                    self.w.autoupdate_glibid = None

    def test_regular_updates_required_releases_control(self):
        self.w.Package.required_changes_upgrade.return_value = {
            "changes_available": True, "to_install": [], "to_upgrade": ["example"]}
        self.control()
        self.preflight_done()
        self.assertFalse(self.w.upgrade_inprogress)
        self.assertTrue(self.w.ui_distupgotoupdates_box.get_visible())
        self.w.startControlDistUpgradeProcess.assert_not_called()

    def test_preflight_exception_allows_retry(self):
        self.w.Package.required_changes_upgrade.side_effect = RuntimeError("cache unavailable")
        self.control()
        self.preflight_done()
        self.assertFalse(self.w.upgrade_inprogress)
        self.assertTrue(self.w.ui_controldistup_button.get_sensitive())
        self.assertIn("cache unavailable", self.w.ui_controldistuperror_label.get_text())
        self.control()
        self.assertEqual(self.thread.call_count, 2)

    def test_worker_start_failure_allows_retry(self):
        self.thread.return_value.start.side_effect = RuntimeError("thread unavailable")
        self.control()
        drain()
        self.assertFalse(self.w.upgrade_inprogress)
        self.assertTrue(self.w.ui_controldistup_button.get_sensitive())
        self.assertTrue(self.w.ui_controldistuperror_box.get_visible())

    def test_control_spawn_failure_allows_retry(self):
        self.w.startControlDistUpgradeProcess.side_effect = GLib.Error("spawn failed")
        self.control()
        self.preflight_done()
        self.assertFalse(self.w.upgrade_inprogress)
        self.assertIn("spawn failed", self.w.ui_controldistuperror_label.get_text())

    def test_control_permission_denied_allows_retry(self):
        self.control()
        self.preflight_done()
        self.w.onControlDistUpgradeExit(123, 32256)
        self.assertFalse(self.w.upgrade_inprogress)
        self.assertTrue(self.w.ui_controldistuperror_box.get_visible())
        self.control()
        self.assertEqual(self.thread.call_count, 2)

    def test_download_permission_denied_allows_retry(self):
        self.download()
        self.w.distupgrade_vte_on_done(self.w.distupgrade_vteterm, 32256)
        self.assertFalse(self.w.upgrade_inprogress)
        self.assertEqual(self.w.ui_distupgrade_stack.get_visible_child_name(), "distupdateinfo")
        self.w.on_ui_distuptodown_button_clicked(None)
        self.assertEqual(self.w.distupgrade_vte_start_process.call_count, 2)

    def test_failed_download_keeps_retry_screen(self):
        self.download()
        self.w.distupgrade_vte_on_done(self.w.distupgrade_vteterm, 256)
        self.roundtrip()
        self.thread.assert_not_called()
        self.assertTrue(self.w.ui_distuptodownretry_button.get_visible())
        self.assertFalse(self.w.upgrade_inprogress)
        self.w.on_ui_distuptodown_button_clicked(None)
        self.assertEqual(self.w.distupgrade_vte_start_process.call_count, 2)

    def test_async_download_spawn_failure_releases_operation(self):
        self.download()
        self.w.distupgrade_vte_create_spawn_callback(
            self.w.distupgrade_vteterm, -1, GLib.Error("spawn failed"), None)
        self.assertFalse(self.w.upgrade_inprogress)
        self.assertTrue(self.w.ui_distuptodownretry_button.get_visible())

    def test_prepare_spawn_failure_releases_operation(self):
        self.w.startDistUpgradeProcess.side_effect = GLib.Error("spawn failed")
        self.prepare()
        self.assertFalse(self.w.upgrade_inprogress)
        self.assertTrue(self.w.ui_distupgrade_buttonbox.get_sensitive())

    def test_prepare_exit_allows_retry(self):
        self.prepare()
        self.w.onDistUpgradeExit(123, 32256)
        self.assertFalse(self.w.upgrade_inprogress)
        self.assertTrue(self.w.ui_distuptoinstallcancel_button.get_sensitive())
        self.w.on_ui_distupgrade_button_clicked(None)
        self.assertEqual(self.w.startDistUpgradeProcess.call_count, 2)

    def test_foreign_download_callback_does_not_finish_current_operation(self):
        self.download()
        self.w.distupgrade_vte_on_done(object(), 0)
        self.assertTrue(self.w.upgrade_inprogress)
        self.assertEqual(self.w.ui_distupgrade_stack.get_visible_child_name(), "download")

    def test_tray_and_command_line_return_to_distupgrade(self):
        self.prepare()
        for action in (self.w.on_menu_updatespage_app, self.w.control_args):
            with self.subTest(action=action.__name__):
                self.w.ui_main_stack.set_visible_child_name("settings")
                action()
                self.assertEqual(self.w.ui_main_stack.get_visible_child_name(), "distupgrade")

    def test_other_actions_cannot_replace_active_distupgrade(self):
        self.prepare()
        for name in ("on_ui_homepage_button_clicked", "on_ui_upgrade_button_clicked",
                     "on_ui_checkupdates_button_clicked", "on_ui_autoremovable_button_clicked",
                     "on_ui_residual_button_clicked", "on_ui_fixaccept_button_clicked",
                     "on_ui_dpkgconfigurefix_button_clicked"):
            with self.subTest(action=name):
                getattr(self.w, name)(self.home)
                self.assertEqual(self.w.ui_main_stack.get_visible_child_name(), "distupgrade")
                self.assertTrue(self.w.upgrade_inprogress)

    def test_cancel_after_download_starts_fresh_control(self):
        self.download()
        self.w.distupgrade_vte_on_done(self.w.distupgrade_vteterm, 0)
        button = self.w.GtkBuilder.get_object("ui_distuptoinstallcancel_button")
        # Resolve the actual Glade handler, including on the unmodified baseline.
        import xml.etree.ElementTree as ET
        tree = ET.parse(Path(module.__file__).parents[1] / "ui/MainWindow.glade")
        handler = tree.find(".//object[@id='ui_distuptoinstallcancel_button']/signal").get("handler")
        getattr(self.w, handler)(button)
        self.assertEqual(self.w.ui_distupgrade_stack.get_visible_child_name(), "control")
        self.control()
        self.thread.assert_called_once()


if __name__ == "__main__":
    unittest.main(verbosity=2)
