#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Feb  5 19:05:13 2022

@author: fatihaltun
"""

import os
import subprocess
import threading
from datetime import datetime

import gi

gi.require_version("GLib", "2.0")
gi.require_version("Gtk", "3.0")
gi.require_version("Vte", "2.91")
gi.require_version("Notify", "0.7")
from gi.repository import Gtk, GObject, Gdk, GLib, Pango, Vte, Notify

try:
    gi.require_version('AppIndicator3', '0.1')
    from gi.repository import AppIndicator3 as appindicator
except:
    # fall back to Ayatana
    gi.require_version('AyatanaAppIndicator3', '0.1')
    from gi.repository import AyatanaAppIndicator3 as appindicator

from UserSettings import UserSettings
from Package import Package

import locale
from locale import gettext as _

locale.bindtextdomain('pardus-update', '/usr/share/locale')
locale.textdomain('pardus-update')

def getenv(str):
    env = os.environ.get(str)
    return env if env else ""

gnome_desktop = False
if "gnome" in getenv("SESSION").lower() or "gnome" in getenv("XDG_CURRENT_DESKTOP").lower():
    gnome_desktop = True

class MainWindow(object):
    def __init__(self, application):
        self.Application = application

        self.main_window_ui_filename = os.path.dirname(os.path.abspath(__file__)) + "/../ui/MainWindow.glade"
        try:
            self.GtkBuilder = Gtk.Builder.new_from_file(self.main_window_ui_filename)
            self.GtkBuilder.connect_signals(self)
        except GObject.GError:
            print("Error reading GUI file: " + self.main_window_ui_filename)
            raise

        self.define_components()
        self.define_variables()
        self.main_window.set_application(application)

        self.user_settings()
        self.UserSettings.set_autostart(self.UserSettings.config_autostart)
        self.init_indicator()
        self.init_ui()

        self.about_dialog.set_program_name(_("Pardus Update"))
        # Set version
        # If not getted from __version__ file then accept version in MainWindow.glade file
        try:
            version = open(os.path.dirname(os.path.abspath(__file__)) + "/__version__").readline()
            self.about_dialog.set_version(version)
        except:
            pass

        if "tray" in self.Application.args.keys():
            self.main_window.set_visible(False)
        else:
            self.main_window.set_visible(True)
            self.main_window.show_all()

        self.set_indicator()

        p1 = threading.Thread(target=self.worker)
        p1.daemon = True
        p1.start()

    def worker(self):
        self.package()
        GLib.idle_add(self.aptUpdate)

    def package(self):
        self.Package = Package()
        if self.Package.updatecache():
            self.isbroken = False
            self.Package.getApps()
        else:
            self.isbroken = True
            print("Error while updating Cache")
        print("package completed")

    def aptUpdate(self, force=False):
        print("in aptUpdate")
        if force:
            self.start_aptupdate()
            return
        if self.UserSettings.config_interval == -1:  # never auto update
            self.set_upgradable_page_and_notify()
            return
        if self.UserSettings.config_lastupdate + self.UserSettings.config_interval - 10 <= int(datetime.now().timestamp()):
            print("started timed update check")
            print("lu:{} inv:{} now:{}".format(self.UserSettings.config_lastupdate,
                                               self.UserSettings.config_interval, int(datetime.now().timestamp())))
            self.start_aptupdate()
            return
        else:
            print("not started timed update check")
            print("lu:{} inv:{} now:{}".format(self.UserSettings.config_lastupdate,
                                               self.UserSettings.config_interval, int(datetime.now().timestamp())))
            self.set_upgradable_page_and_notify()
            return

    def control_args(self):
        if "page" in self.Application.args.keys():
            page = self.Application.args["page"]
            self.ui_main_stack.set_visible_child_name(page)

    def define_components(self):
        self.main_window = self.GtkBuilder.get_object("ui_main_window")
        self.about_dialog = self.GtkBuilder.get_object("ui_about_dialog")
        self.ui_main_stack = self.GtkBuilder.get_object("ui_main_stack")
        self.ui_upgrade_button = self.GtkBuilder.get_object("ui_upgrade_button")
        self.ui_versionupgrade_button = self.GtkBuilder.get_object("ui_versionupgrade_button")
        self.ui_upgradeoptions_button = self.GtkBuilder.get_object("ui_upgradeoptions_button")
        self.ui_upgrade_buttonbox = self.GtkBuilder.get_object("ui_upgrade_buttonbox")
        self.ui_upgrade_buttonbox.set_homogeneous(False)

        self.ui_menu_popover = self.GtkBuilder.get_object("ui_menu_popover")
        self.ui_menusettings_image = self.GtkBuilder.get_object("ui_menusettings_image")
        self.ui_menusettings_label = self.GtkBuilder.get_object("ui_menusettings_label")
        self.ui_updatefreq_combobox = self.GtkBuilder.get_object("ui_updatefreq_combobox")
        self.ui_updatefreq_spin = self.GtkBuilder.get_object("ui_updatefreq_spin")
        self.ui_updatefreq_stack = self.GtkBuilder.get_object("ui_updatefreq_stack")
        self.ui_settingslastupdate_label = self.GtkBuilder.get_object("ui_settingslastupdate_label")
        self.ui_autostart_switch = self.GtkBuilder.get_object("ui_autostart_switch")

        self.ui_upgradable_sw = self.GtkBuilder.get_object("ui_upgradable_sw")
        self.ui_newly_sw = self.GtkBuilder.get_object("ui_newly_sw")
        self.ui_removable_sw = self.GtkBuilder.get_object("ui_removable_sw")
        self.ui_kept_sw = self.GtkBuilder.get_object("ui_kept_sw")

        self.ui_upgradable_listbox = self.GtkBuilder.get_object("ui_upgradable_listbox")
        self.ui_newly_listbox = self.GtkBuilder.get_object("ui_newly_listbox")
        self.ui_removable_listbox = self.GtkBuilder.get_object("ui_removable_listbox")
        self.ui_kept_listbox = self.GtkBuilder.get_object("ui_kept_listbox")

        self.ui_downloadsize_box = self.GtkBuilder.get_object("ui_downloadsize_box")
        self.ui_installsize_box = self.GtkBuilder.get_object("ui_installsize_box")
        self.ui_upgradecount_box = self.GtkBuilder.get_object("ui_upgradecount_box")
        self.ui_newlycount_box = self.GtkBuilder.get_object("ui_newlycount_box")
        self.ui_removecount_box = self.GtkBuilder.get_object("ui_removecount_box")
        self.ui_keptcount_box = self.GtkBuilder.get_object("ui_keptcount_box")

        self.ui_downloadsize_label = self.GtkBuilder.get_object("ui_downloadsize_label")
        self.ui_installsize_label = self.GtkBuilder.get_object("ui_installsize_label")
        self.ui_upgradecount_label = self.GtkBuilder.get_object("ui_upgradecount_label")
        self.ui_newlycount_label = self.GtkBuilder.get_object("ui_newlycount_label")
        self.ui_removecount_label = self.GtkBuilder.get_object("ui_removecount_label")
        self.ui_keptcount_label = self.GtkBuilder.get_object("ui_keptcount_label")

        self.ui_upgradeoptions_popover = self.GtkBuilder.get_object("ui_upgradeoptions_popover")
        self.ui_upgrade_defaults_button = self.GtkBuilder.get_object("ui_upgrade_defaults_button")
        self.ui_upgradenewconf_radiobutton = self.GtkBuilder.get_object("ui_upgradenewconf_radiobutton")
        self.ui_upgradeoldconf_radiobutton = self.GtkBuilder.get_object("ui_upgradeoldconf_radiobutton")
        self.ui_upgradeaskconf_radiobutton = self.GtkBuilder.get_object("ui_upgradeaskconf_radiobutton")
        self.ui_upgradewithyq_radiobutton = self.GtkBuilder.get_object("ui_upgradewithyq_radiobutton")
        self.ui_upgradewithoutyq_radiobutton = self.GtkBuilder.get_object("ui_upgradewithoutyq_radiobutton")

        self.ui_upgradevte_sw = self.GtkBuilder.get_object("ui_upgradevte_sw")
        self.ui_upgradeinfo_box = self.GtkBuilder.get_object("ui_upgradeinfo_box")
        self.ui_upgradeinfo_label = self.GtkBuilder.get_object("ui_upgradeinfo_label")
        self.ui_upgradeinfoback_button = self.GtkBuilder.get_object("ui_upgradeinfoback_button")
        self.ui_upgradeinfook_button = self.GtkBuilder.get_object("ui_upgradeinfook_button")

        # upgrade vte box
        self.upgrade_vteterm = Vte.Terminal()
        self.upgrade_vteterm.set_scrollback_lines(-1)
        upgrade_vte_menu = Gtk.Menu()
        upgrade_vte_menu_items = Gtk.MenuItem(label=_("Copy selected text"))
        upgrade_vte_menu.append(upgrade_vte_menu_items)
        upgrade_vte_menu_items.connect("activate", self.upgrade_vte_menu_action, self.upgrade_vteterm)
        upgrade_vte_menu_items.show()
        self.upgrade_vteterm.connect_object("event", self.upgrade_vte_event, upgrade_vte_menu)
        self.ui_upgradevte_sw.add(self.upgrade_vteterm)

    def define_variables(self):
        system_wide = "usr/share" in os.path.dirname(os.path.abspath(__file__))
        self.icon_available = "pardus-update-available-symbolic" if system_wide else "software-update-available-symbolic"
        self.icon_normal = "pardus-update-symbolic" if system_wide else "security-medium-symbolic"
        self.icon_inprogress = "pardus-update-inprogress-symbolic" if system_wide else "emblem-synchronizing-symbolic"
        self.icon_error = "pardus-update-error-symbolic" if system_wide else "security-low-symbolic"

        if gnome_desktop:
            self.icon_available = "software-update-available-symbolic"
            self.icon_normal = "security-medium-symbolic"
            self.icon_inprogress = "emblem-synchronizing-symbolic"
            self.icon_error = "security-low-symbolic"

        self.autoupdate_glibid = None
        self.update_inprogress = False
        self.upgrade_inprogress = False
        self.laststack = None

    def user_settings(self):
        self.UserSettings = UserSettings()
        self.UserSettings.createDefaultConfig()
        self.UserSettings.readConfig()

        print("{} {}".format("config_interval", self.UserSettings.config_interval))
        print("{} {}".format("config_lastupdate", self.UserSettings.config_lastupdate))
        print("{} {}".format("config_autostart", self.UserSettings.config_autostart))

    def init_ui(self):
        self.ui_main_stack.set_visible_child_name("spinner")
        system_wide = "usr/share" in os.path.dirname(os.path.abspath(__file__))
        if not system_wide:
            self.main_window.set_default_icon_from_file(
                os.path.dirname(os.path.abspath(__file__)) + "/../data/pardus-update.svg")
            self.about_dialog.set_logo(None)

    def init_indicator(self):
        self.indicator = appindicator.Indicator.new(
            "pardus-update", self.icon_normal, appindicator.IndicatorCategory.APPLICATION_STATUS)
        self.indicator.set_status(appindicator.IndicatorStatus.ACTIVE)
        self.indicator.set_title(_("Pardus Update"))
        self.menu = Gtk.Menu()
        self.item_update = Gtk.MenuItem()
        self.item_update.set_label(_("Check Updates"))
        self.item_update.connect("activate", self.on_menu_update)
        self.item_sh_app = Gtk.MenuItem()
        self.item_sh_app.connect("activate", self.on_menu_show_app)
        self.item_separator1 = Gtk.SeparatorMenuItem()
        self.item_separator2 = Gtk.SeparatorMenuItem()
        self.item_quit = Gtk.MenuItem()
        self.item_quit.set_label(_("Quit"))
        self.item_quit.connect('activate', self.on_menu_quit_app)
        self.item_lastcheck = Gtk.MenuItem()
        self.item_lastcheck.set_sensitive(False)
        self.item_lastcheck.set_label("{}: {}".format(_("Last Check"),
                                                      datetime.fromtimestamp(self.UserSettings.config_lastupdate)))
        self.menu.append(self.item_sh_app)
        self.menu.append(self.item_separator1)
        self.menu.append(self.item_update)
        self.menu.append(self.item_lastcheck)
        self.menu.append(self.item_separator2)
        self.menu.append(self.item_quit)
        self.menu.show_all()
        self.indicator.set_menu(self.menu)

    def set_indicator(self):
        if self.main_window.is_visible():
            self.item_sh_app.set_label(_("Hide App"))
        else:
            self.item_sh_app.set_label(_("Show App"))

    def on_menu_update(self, *args):
        if self.autoupdate_glibid:
            GLib.source_remove(self.autoupdate_glibid)
            self.autoupdate_glibid = None
        self.aptUpdate(force=True)

    def on_menu_show_app(self, *args):
        window_state = self.main_window.is_visible()
        if window_state:
            self.main_window.set_visible(False)
            self.item_sh_app.set_label(_("Show App"))
        else:
            self.main_window.set_visible(True)
            self.item_sh_app.set_label(_("Hide App"))

    def on_ui_checkupdates_button_clicked(self, button):
        self.ui_main_stack.set_visible_child_name("spinner")
        if self.autoupdate_glibid:
            GLib.source_remove(self.autoupdate_glibid)
            self.autoupdate_glibid = None
        self.aptUpdate(force=True)

    def on_ui_upgradeinfoback_button_clicked(self, button):
        self.ui_main_stack.set_visible_child_name("updateinfo")

    def on_ui_upgradeinfook_button_clicked(self, button):
        if self.Package.upgradable() and not self.keep_ok_clicked:
            self.aptUpdate()
        else:
            self.ui_main_stack.set_visible_child_name("ok")

    def on_ui_upgradeconf_radiobutton_toggled(self, button):
        self.ui_upgrade_defaults_button.set_visible(
            not self.ui_upgradenewconf_radiobutton.get_active() or not self.ui_upgradewithyq_radiobutton.get_active())

    def on_ui_upgrade_defaults_button_clicked(self, button):
        self.ui_upgradenewconf_radiobutton.set_active(True)
        self.ui_upgradewithyq_radiobutton.set_active(True)

    def on_ui_upgradeoptions_button_clicked(self, button):
        self.ui_upgradeoptions_popover.popup()
        self.ui_upgrade_defaults_button.set_visible(
            not self.ui_upgradenewconf_radiobutton.get_active() or not self.ui_upgradewithyq_radiobutton.get_active())

    def on_ui_upgrade_button_clicked(self, button):
        self.upgrade_vteterm.reset(True, True)
        self.ui_upgradeinfo_box.set_visible(False)
        self.ui_upgradevte_sw.set_visible(True)
        self.ui_upgradeinfook_button.set_visible(False)
        self.ui_main_stack.set_visible_child_name("upgrade")

        yq_conf = ""
        if self.ui_upgradewithyq_radiobutton.get_active():
            yq_conf = "-y -q"
        elif self.ui_upgradewithoutyq_radiobutton.get_active():
            yq_conf = ""

        dpkg_conf = ""
        if self.ui_upgradenewconf_radiobutton.get_active():
            dpkg_conf = "-o Dpkg::Options::=--force-confnew"
        elif self.ui_upgradeoldconf_radiobutton.get_active():
            dpkg_conf = "-o Dpkg::Options::=--force-confold"
        elif self.ui_upgradeaskconf_radiobutton.get_active():
            dpkg_conf = ""

        print("yq_conf: {}\ndpkg_conf: {}".format(yq_conf, dpkg_conf))
        if not self.upgrade_inprogress:
            command = ["/usr/bin/pkexec", os.path.dirname(os.path.abspath(__file__)) + "/SysActions.py",
                       "upgrade", yq_conf, dpkg_conf]
            self.upgrade_vte_start_process(command)
            self.upgrade_inprogress = True
        else:
            self.ui_upgradeinfo_label.set_markup(
                "<span color='red'>{}</span>".format(_("Package manager is busy, try again later.")))
            self.ui_upgradeinfo_box.set_visible(True)
            self.ui_upgradevte_sw.set_visible(False)

    def on_ui_homepage_button_clicked(self, button):
        if self.ui_main_stack.get_visible_child_name() == "settings":
            self.ui_menusettings_image.set_from_icon_name("preferences-system-symbolic", Gtk.IconSize.BUTTON)
            self.ui_menusettings_label.set_text(_("Settings"))
            self.ui_main_stack.set_visible_child_name(self.laststack)

    def on_ui_menuabout_button_clicked(self, button):
        self.about_dialog.run()
        self.about_dialog.hide()
        self.ui_menu_popover.popdown()

    def on_ui_menusettings_button_clicked(self, button):

        if self.ui_main_stack.get_visible_child_name() != "settings":
            self.laststack = self.ui_main_stack.get_visible_child_name()

        if self.ui_main_stack.get_visible_child_name() == "settings":
            self.ui_menusettings_image.set_from_icon_name("preferences-system-symbolic", Gtk.IconSize.BUTTON)
            self.ui_menusettings_label.set_text(_("Settings"))
            self.ui_main_stack.set_visible_child_name(self.laststack)
        else:
            self.ui_menusettings_image.set_from_icon_name("user-home-symbolic", Gtk.IconSize.BUTTON)
            self.ui_menusettings_label.set_text(_("Home Page"))
            self.ui_main_stack.set_visible_child_name("settings")

            interval = self.interval_to_combo(self.UserSettings.config_interval)

            if interval is not None:
                self.ui_updatefreq_stack.set_visible_child_name("combo")
                self.ui_updatefreq_combobox.set_active(interval)
            else:
                self.ui_updatefreq_stack.set_visible_child_name("spin")
                self.ui_updatefreq_spin.set_value(self.UserSettings.config_interval)

            self.ui_settingslastupdate_label.set_markup("{}".format(
                datetime.fromtimestamp(self.UserSettings.config_lastupdate)))

            self.ui_autostart_switch.set_state(self.UserSettings.config_autostart)

        self.ui_menu_popover.popdown()

    def interval_to_combo(self, interval):
        if interval == 3600:  # Hourly
            combo = 0
        elif interval == 86400:  # Daily
            combo = 1
        elif interval == 604800:  # Weekly
            combo = 2
        elif interval == -1:  # Never
            combo = 3
        else:
            return None
        return combo

    def on_ui_updatefreq_combobox_changed(self, combo_box):
        seconds = 86400
        if combo_box.get_active() == 0:  # Hourly
            seconds = 3600
        elif combo_box.get_active() == 1:  # Daily
            seconds = 86400
        elif combo_box.get_active() == 2:  # Weekly
            seconds = 604800
        elif combo_box.get_active() == 3:  # Never
            seconds = -1

        user_interval = self.UserSettings.config_interval
        if seconds != user_interval:
            self.UserSettings.writeConfig(seconds, self.UserSettings.config_lastupdate,
                                          self.UserSettings.config_autostart)
            self.user_settings()

            # update autoupdate timer
            if self.autoupdate_glibid:
                GLib.source_remove(self.autoupdate_glibid)
            self.create_autoupdate_glibid()

    def on_ui_updatefreq_spin_value_changed(self, spin_button):
        seconds = int(spin_button.get_value())
        user_interval = self.UserSettings.config_interval
        if seconds != user_interval:
            self.UserSettings.writeConfig(seconds, self.UserSettings.config_lastupdate,
                                          self.UserSettings.config_autostart)
            self.user_settings()

            # update autoupdate timer
            if self.autoupdate_glibid:
                GLib.source_remove(self.autoupdate_glibid)
            self.create_autoupdate_glibid()

    def on_ui_autostart_switch_state_set(self, switch, state):
        self.UserSettings.set_autostart(state)

        user_autostart = self.UserSettings.config_autostart
        if state != user_autostart:
            self.UserSettings.writeConfig(self.UserSettings.config_interval, self.UserSettings.config_lastupdate, state)
            self.user_settings()

    def on_ui_main_window_delete_event(self, widget, event):
        self.main_window.hide()
        self.item_sh_app.set_label(_("Show App"))
        return True

    def on_menu_quit_app(self, *args):
        self.main_window.get_application().quit()

    def control_required_changes(self):
        def start_thread():
            self.ui_upgradable_listbox.foreach(lambda child: self.ui_upgradable_listbox.remove(child))
            self.ui_newly_listbox.foreach(lambda child: self.ui_newly_listbox.remove(child))
            self.ui_removable_listbox.foreach(lambda child: self.ui_removable_listbox.remove(child))
            self.ui_kept_listbox.foreach(lambda child: self.ui_kept_listbox.remove(child))

            self.ui_upgradable_sw.set_visible(False)
            self.ui_newly_sw.set_visible(False)
            self.ui_removable_sw.set_visible(False)
            self.ui_kept_sw.set_visible(False)

            self.ui_downloadsize_box.set_visible(False)
            self.ui_installsize_box.set_visible(False)
            self.ui_upgradecount_box.set_visible(False)
            self.ui_newlycount_box.set_visible(False)
            self.ui_removecount_box.set_visible(False)
            self.ui_keptcount_box.set_visible(False)

            GLib.idle_add(self.ui_upgrade_buttonbox.set_sensitive, False)
            GLib.idle_add(self.ui_versionupgrade_button.set_visible, False)

            upg_thread = threading.Thread(target=self.upgradables_worker_thread, daemon=True)
            upg_thread.start()

        start_thread()

    def upgradables_worker_thread(self):
        rcu = self.rcu_worker()
        GLib.idle_add(self.on_upgradables_worker_done, rcu)

    def rcu_worker(self):
        return self.Package.required_changes_upgrade()

    def on_upgradables_worker_done(self, requireds):
        def add_to_listbox(iconname, package, listbox, pagename):
            image = Gtk.Image.new_from_icon_name(iconname, Gtk.IconSize.BUTTON)
            name = Gtk.Label.new()
            name.set_markup("<b>{}</b>".format(GLib.markup_escape_text(package, -1)))
            name.props.halign = Gtk.Align.START

            summarylabel = Gtk.Label.new()
            summarylabel.set_markup(
                "<small>{}</small>".format(GLib.markup_escape_text(self.Package.summary(package), -1)))
            summarylabel.set_ellipsize(Pango.EllipsizeMode.END)
            summarylabel.props.halign = Gtk.Align.START

            old_version = Gtk.Label.new()
            old_version.set_markup("<span size='x-small'>{}</span>".format(
                GLib.markup_escape_text(self.Package.installed_version(package), -1)))
            old_version.set_ellipsize(Pango.EllipsizeMode.END)

            sep_label = Gtk.Label.new()
            sep_label.set_markup("<span size='x-small'>>></span>")

            new_version = Gtk.Label.new()
            new_version.set_markup("<span size='x-small'>{}</span>".format(
                GLib.markup_escape_text(self.Package.candidate_version(package), -1)))
            new_version.set_ellipsize(Pango.EllipsizeMode.END)

            box_version = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 5)
            box_version.pack_start(old_version, False, True, 0)
            box_version.pack_start(sep_label, False, True, 0)
            box_version.pack_start(new_version, False, True, 0)

            box1 = Gtk.Box.new(Gtk.Orientation.VERTICAL, 3)
            box1.pack_start(name, False, True, 0)
            box1.pack_start(summarylabel, False, True, 0)
            box1.pack_start(box_version, False, True, 0)
            box1.props.valign = Gtk.Align.CENTER
            box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 3)
            box.set_margin_top(5)
            box.set_margin_bottom(5)
            box.set_margin_start(5)
            box.set_margin_end(5)
            box.pack_start(image, False, True, 5)
            box.pack_start(box1, False, True, 5)
            GLib.idle_add(listbox.insert, box, GLib.PRIORITY_DEFAULT_IDLE)
            GLib.idle_add(self.ui_upgrade_buttonbox.set_sensitive, True)
            GLib.idle_add(pagename.set_visible, True)

        if requireds["to_upgrade"] and requireds["to_upgrade"] is not None:
            for package in requireds["to_upgrade"]:
                add_to_listbox("go-up-symbolic", package, self.ui_upgradable_listbox, self.ui_upgradable_sw)

        if requireds["to_install"] and requireds["to_install"] is not None:
            for package in requireds["to_install"]:
                add_to_listbox("list-add-symbolic", package, self.ui_newly_listbox, self.ui_newly_sw)

        if requireds["to_delete"] and requireds["to_delete"] is not None:
            for package in requireds["to_delete"]:
                add_to_listbox("list-remove-symbolic", package, self.ui_removable_listbox, self.ui_removable_sw)

        if requireds["to_keep"] and requireds["to_keep"] is not None:
            for package in requireds["to_keep"]:
                add_to_listbox("view-grid-symbolic", package, self.ui_kept_listbox, self.ui_kept_sw)

        GLib.idle_add(self.ui_upgradable_listbox.show_all)
        GLib.idle_add(self.ui_newly_listbox.show_all)
        GLib.idle_add(self.ui_removable_listbox.show_all)
        GLib.idle_add(self.ui_kept_listbox.show_all)

        if requireds["download_size"] and requireds["download_size"] is not None:
            GLib.idle_add(self.ui_downloadsize_label.set_markup,
                          "{}".format(self.Package.beauty_size(requireds["download_size"])))
            GLib.idle_add(self.ui_downloadsize_box.set_visible, True)

        if requireds["install_size"] and requireds["install_size"] is not None and requireds["install_size"] > 0:
            GLib.idle_add(self.ui_installsize_label.set_markup,
                          "{}".format(self.Package.beauty_size(requireds["install_size"])))
            GLib.idle_add(self.ui_installsize_box.set_visible, True)

        if requireds["to_upgrade"] and requireds["to_upgrade"] is not None:
            GLib.idle_add(self.ui_upgradecount_label.set_markup,
                          "{}".format(len(requireds["to_upgrade"])))
            GLib.idle_add(self.ui_upgradecount_box.set_visible, True)

        if requireds["to_install"] and requireds["to_install"] is not None:
            GLib.idle_add(self.ui_newlycount_label.set_markup, "{}".format(len(requireds["to_install"])))
            GLib.idle_add(self.ui_newlycount_box.set_visible, True)

        if requireds["to_delete"] and requireds["to_delete"] is not None:
            GLib.idle_add(self.ui_removecount_label.set_markup, "{}".format(len(requireds["to_delete"])))
            GLib.idle_add(self.ui_removecount_box.set_visible, True)

        if requireds["to_keep"] and requireds["to_keep"] is not None:
            GLib.idle_add(self.ui_keptcount_label.set_markup, "{}".format(len(requireds["to_keep"])))
            GLib.idle_add(self.ui_keptcount_box.set_visible, True)

        print("on_upgradables_worker_done")

    def start_aptupdate(self):
        if not self.upgrade_inprogress and not self.update_inprogress:
            GLib.idle_add(self.indicator.set_icon, self.icon_inprogress)
            command = ["/usr/bin/pkexec", os.path.dirname(os.path.abspath(__file__)) + "/AutoAptUpdate.py"]
            self.startAptUpdateProcess(command)
            self.update_inprogress = True
        else:
            print("aptUpdate: upgrade_inprogress | update_inprogress")

    def update_lastcheck_labels(self):
        self.ui_settingslastupdate_label.set_markup("{}".format(
            datetime.fromtimestamp(self.UserSettings.config_lastupdate)))

        self.item_lastcheck.set_label("{}: {}".format(_("Last Check"),
                                                      datetime.fromtimestamp(self.UserSettings.config_lastupdate)))

    def create_autoupdate_glibid(self):
        if self.UserSettings.config_interval != -1:
            self.autoupdate_glibid = GLib.timeout_add_seconds(self.UserSettings.config_interval, self.aptUpdate)

    def set_upgradable_page_and_notify(self):
        upgradable = self.Package.upgradable()
        if upgradable:
            self.control_required_changes()
            self.indicator.set_icon(self.icon_available)
            if self.ui_main_stack.get_visible_child_name() == "spinner":
                self.ui_main_stack.set_visible_child_name("updateinfo")
            if len(upgradable) > 1:
                notification = Notification(summary=_("Software Update"),
                                            body=_("There are {} software updates available.".format(len(upgradable))),
                                            icon=self.icon_available, appid=self.Application.get_application_id())
                notification.show()

            else:
                notification = Notification(summary=_("Software Update"),
                                            body=_("There is {} software update available.".format(len(upgradable))),
                                            icon=self.icon_available, appid=self.Application.get_application_id())
                notification.show()
        else:
            self.ui_main_stack.set_visible_child_name("ok")
            self.indicator.set_icon(self.icon_normal)



    def startAptUpdateProcess(self, params):
        pid, stdin, stdout, stderr = GLib.spawn_async(params, flags=GLib.SpawnFlags.DO_NOT_REAP_CHILD,
                                                      standard_output=True, standard_error=True)
        GLib.io_add_watch(GLib.IOChannel(stdout), GLib.IO_IN | GLib.IO_HUP, self.onAptUpdateProcessStdout)
        GLib.io_add_watch(GLib.IOChannel(stderr), GLib.IO_IN | GLib.IO_HUP, self.onAptUpdateProcessStderr)
        GLib.child_watch_add(GLib.PRIORITY_DEFAULT, pid, self.onAptUpdateProcessExit)

        return pid

    def onAptUpdateProcessStdout(self, source, condition):
        if condition == GLib.IO_HUP:
            return False
        line = source.readline()
        print("onAptUpdateProcessStdout: {}".format(line))
        return True

    def onAptUpdateProcessStderr(self, source, condition):
        if condition == GLib.IO_HUP:
            return False
        line = source.readline()
        print("onAptUpdateProcessStderr: {}".format(line))
        return True

    def onAptUpdateProcessExit(self, pid, status):
        print("onAptUpdateProcessExit: {}".format(status))
        self.Package.updatecache()
        if status == 0:
            try:
                timestamp = int(datetime.now().timestamp())
            except Exception as e:
                print("timestamp Error: {}".format(e))
                timestamp = 0

            self.UserSettings.writeConfig(self.UserSettings.config_interval, timestamp,
                                          self.UserSettings.config_autostart)
            self.user_settings()
            self.update_lastcheck_labels()
            self.create_autoupdate_glibid()
            self.set_upgradable_page_and_notify()
        else:
            self.indicator.set_icon(self.icon_error)

        self.update_inprogress = False

    def upgrade_vte_event(self, widget, event):
        if event.type == Gdk.EventType.BUTTON_PRESS:
            if event.button.button == 3:
                widget.popup_for_device(None, None, None, None, None,
                                        event.button.button, event.time)
                return True
        return False

    def upgrade_vte_menu_action(self, widget, terminal):
        terminal.copy_clipboard()

    def upgrade_vte_start_process(self, command):
        pty = Vte.Pty.new_sync(Vte.PtyFlags.DEFAULT)
        self.upgrade_vteterm.set_pty(pty)
        try:
            self.upgrade_vteterm.spawn_async(
                Vte.PtyFlags.DEFAULT,
                os.environ['HOME'],
                command,
                None,
                GLib.SpawnFlags.DO_NOT_REAP_CHILD,
                None,
                None,
                -1,
                None,
                self.upgrade_vte_create_spawn_callback,
                None
            )
        except Exception as e:
            # old version VTE doesn't have spawn_async so use spawn_sync
            print("{}".format(e))
            self.upgrade_vteterm.connect("child-exited", self.upgrade_vte_on_done)
            self.upgrade_vteterm.spawn_sync(
                Vte.PtyFlags.DEFAULT,
                os.environ['HOME'],
                command,
                [],
                GLib.SpawnFlags.DO_NOT_REAP_CHILD,
                None,
                None,
            )

    def upgrade_vte_create_spawn_callback(self, terminal, pid, error, userdata):
        self.upgrade_vteterm.connect("child-exited", self.upgrade_vte_on_done)

    def upgrade_vte_on_done(self, terminal, status):
        print("upgrade_vte_on_done status: {}".format(status))
        if status == 32256:  # operation cancelled | Request dismissed
            self.ui_main_stack.set_visible_child_name("updateinfo")
        else:
            self.Package.updatecache()
            GLib.idle_add(self.ui_upgradeinfo_label.set_markup, "<b>{}</b>".format(_("Process completed.")))
            GLib.idle_add(self.ui_upgradeinfo_box.set_visible, True)
            GLib.idle_add(self.ui_upgradeinfoback_button.set_visible, False)
            GLib.idle_add(self.ui_upgradeinfook_button.set_visible, True)
        self.upgrade_inprogress = False


class Notification(GObject.GObject):
    __gsignals__ = {
        'notify-action': (GObject.SIGNAL_RUN_FIRST, None,
                          (str,))
    }

    def __init__(self, summary="", body="", icon="pardus-update", appid="tr.org.pardus-update"):
        GObject.GObject.__init__(self)
        self.appid = appid
        if Notify.is_initted():
            Notify.uninit()
        Notify.init(appid)
        self.notification = Notify.Notification.new(summary, body, icon)
        self.notification.set_timeout(Notify.EXPIRES_NEVER)
        self.notification.add_action('update', 'Update', self.update_callback)
        self.notification.connect('closed', self.on_closed)

    def show(self):
        self.notification.show()

    def update_callback(self, widget, action):
        # subprocess.Popen(["/home/fatih/Desktop/pardus-update/src/Main.py", "--page", "updateinfo"])
        subprocess.Popen(["/usr/bin/pardus-update", "--page", "updateinfo"])
        # subprocess.Popen(["gtk-launch", self.appid])
        self.emit('notify-action', action)

    def on_closed(self, widget):
        self.emit('notify-action', 'closed')
