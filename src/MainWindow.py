#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Feb  5 19:05:13 2022

@author: fatihaltun
"""
import grp
import json
import os
import subprocess
import threading
from datetime import datetime

import distro
import gi

gi.require_version("GLib", "2.0")
gi.require_version("Gtk", "3.0")
gi.require_version("Vte", "2.91")
gi.require_version("Notify", "0.7")
from gi.repository import Gtk, GObject, Gdk, GLib, Pango, Vte, Notify, GdkPixbuf, Gio

try:
    gi.require_version('AppIndicator3', '0.1')
    from gi.repository import AppIndicator3 as appindicator
except:
    # fall back to Ayatana
    gi.require_version('AyatanaAppIndicator3', '0.1')
    from gi.repository import AyatanaAppIndicator3 as appindicator

from UserSettings import UserSettings
from SystemSettings import SystemSettings
from Package import Package
from RepoDistControl import RepoDistControl
from Utils import Utils, ErrorDialog

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

xfce_desktop = False
if "xfce" in getenv("SESSION").lower() or "xfce" in getenv("XDG_CURRENT_DESKTOP").lower():
    xfce_desktop = True


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
        self.control_display()
        self.css()

        self.utils()
        self.user_settings()
        self.system_settings()

        autostart = self.UserSettings.config_autostart
        if self.SystemSettings.config_autostart is not None:
            autostart = self.SystemSettings.config_autostart
        self.UserSettings.set_autostart(autostart)

        update_selectable = self.UserSettings.config_update_selectable
        if self.SystemSettings.config_update_selectable is not None:
            update_selectable = self.SystemSettings.config_update_selectable
        self.user_keep_list = self.UserSettings.get_user_keeps_from_file() if update_selectable else []

        self.init_indicator()
        self.init_ui()
        self.monitoring()

        self.about_dialog.set_program_name(_("Pardus Update"))
        if self.about_dialog.get_titlebar() is None:
            about_headerbar = Gtk.HeaderBar.new()
            about_headerbar.set_show_close_button(True)
            about_headerbar.set_title(_("About Pardus Update"))
            about_headerbar.pack_start(Gtk.Image.new_from_icon_name("pardus-update", Gtk.IconSize.LARGE_TOOLBAR))
            about_headerbar.show_all()
            self.about_dialog.set_titlebar(about_headerbar)
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

        self.set_initial_hide_widgets()

        self.define_last_variables()

        p1 = threading.Thread(target=self.worker)
        p1.daemon = True
        p1.start()

    def worker(self):
        self.package()
        self.control_distupgrade()
        GLib.idle_add(self.apt_update)

    def control_distupgrade(self):
        if self.user_distro_id == "pardus":
            try:
                # self.user_distro_version = 19
                # self.user_distro_codename = "ondokuz"

                self.repo_dist_control = RepoDistControl()
                self.repo_dist_control.ServerGet = self.server_get_dist
                self.repo_dist_control.get("http://depo.pardus.org.tr/dists.json")
            except Exception as e:
                print("{}".format(e))
        else:
            print("{} not yet supported for dist upgrade".format(distro.id()))

    def server_get_dist(self, response):
        def get_dist_key():
            if self.user_distro_codename == "ondokuz" or self.user_distro_codename == "yirmibir" or \
                    self.user_distro_codename == "yirmiuc" or self.user_distro_codename == "yirmibes" or \
                    self.user_distro_codename == "yirmiyedi" or self.user_distro_codename == "yirmidokuz":
                return "pardus"
            elif self.user_distro_codename == "etap-yirmiuc" or self.user_distro_codename == "etap-yirmibes":
                return "etap"
            else:
                return "none-{}".format(self.user_distro_codename)

        if "error" not in response.keys():
            if self.user_distro_version:
                dist_key = get_dist_key()
                datas = response["repo"][dist_key]
                for data in datas:
                    if data["version"] > self.user_distro_version:
                        if "stable" in data["status"]:
                            print("server:{} > user:{}".format(data["version"], self.user_distro_version))
                            self.dist_upgradable = True
                            self.dist_new_version = "{} {}".format(dist_key.title(), data["version"], data["name"])
                            self.dist_new_codename = "{}".format(data["name"])
                            self.dist_new_sources = data["sources"]
                            break
                if self.dist_upgradable:
                    GLib.idle_add(self.ui_menudistupgrade_separator.set_visible, True)
                    GLib.idle_add(self.ui_menudistupgrade_button.set_visible, True)
                    GLib.idle_add(self.ui_homedistupgrade_box.set_visible, True)

                    self.ui_distup_now_label.set_text("{} {} ({})".format(dist_key.title(), self.user_distro_version,
                                                                          self.user_distro_codename))
                    self.ui_distup_new_label.set_text("{} ({})".format(self.dist_new_version, self.dist_new_codename))

                    self.ui_controldistup_button.set_label(_("Start {} Upgrade").format(self.dist_new_version))
                    self.ui_homecontroldistup_label.set_label(_("Start {} Upgrade").format(self.dist_new_version))

                for data in datas:
                    if data["version"] == self.user_distro_version:
                        self.user_default_sources_list = data["sources"]

        else:
            error_message = response["message"]
            print(error_message)

    def utils(self):
        self.Utils = Utils()

    def css(self):
        cssProvider = Gtk.CssProvider()
        cssProvider.load_from_path(os.path.dirname(os.path.abspath(__file__)) + "/../data/style.css")
        screen = Gdk.Screen.get_default()
        styleContext = Gtk.StyleContext()
        styleContext.add_provider_for_screen(screen, cssProvider, Gtk.STYLE_PROVIDER_PRIORITY_USER)

    def package(self):
        self.Package = Package()
        if self.Package.updatecache():
            self.isbroken = False
        else:
            self.isbroken = True
            print("Error while updating Cache")

        print("package completed")
        print("broken: {}".format(self.isbroken))

    def apt_update(self, force=False):
        """
        auto update control function
        """
        print("in apt_update")

        interval = self.UserSettings.config_update_interval
        if self.SystemSettings.config_update_interval is not None:
            interval = self.SystemSettings.config_update_interval

        lastupdate = self.UserSettings.config_update_lastupdate
        if self.SystemSettings.config_update_lastupdate is not None:
            lastupdate = self.SystemSettings.config_update_lastupdate

        if force:
            self.start_aptupdate()
            return
        if interval == -1:  # never auto update
            self.set_upgradable_page_and_notify()
            return
        if lastupdate + interval - 10 <= int(datetime.now().timestamp()):
            print("started timed update check")
            print("lu:{} inv:{} now:{}".format(lastupdate, interval, int(datetime.now().timestamp())))
            self.start_aptupdate()
            return
        else:
            print("not started timed update check")
            print("lu:{} inv:{} now:{}".format(lastupdate, interval, int(datetime.now().timestamp())))
            self.set_upgradable_page_and_notify()
            return

    def apt_upgrade(self, force=False):
        """
        auto upgrade control function
        """
        print("in apt_upgrade")

        if self.SystemSettings.config_upgrade_enabled is None or self.SystemSettings.config_upgrade_interval is None:
            return

        enabled = self.SystemSettings.config_upgrade_enabled
        if not enabled:
            return

        interval = self.SystemSettings.config_upgrade_interval

        if self.SystemSettings.config_upgrade_lastupgrade is not None:
            lastupgrade = self.SystemSettings.config_upgrade_lastupgrade
        else:
            lastupgrade = 0

        if force:
            self.start_aptupgrade()
            return
        if interval == -1:  # never auto upgrade
            # self.set_upgradable_page_and_notify()
            return
        if lastupgrade + interval - 10 <= int(datetime.now().timestamp()):
            print("started timed upgrade check")
            print("lu:{} inv:{} now:{}".format(lastupgrade, interval, int(datetime.now().timestamp())))
            self.start_aptupgrade()
            return
        else:
            print("not started timed upgrade check")
            print("lu:{} inv:{} now:{}".format(lastupgrade, interval, int(datetime.now().timestamp())))
            # self.set_upgradable_page_and_notify()
            return

    def control_args(self):
        if "page" in self.Application.args.keys():
            page = self.Application.args["page"]

            if self.upgrade_inprogress:
                self.ui_main_stack.set_visible_child_name("upgrade")
            else:
                if page == "updateinfo":
                    if self.Package.upgradable():
                        self.ui_main_stack.set_visible_child_name(page)
                    else:
                        self.ui_main_stack.set_visible_child_name("ok")

            self.ui_menusettings_image.set_from_icon_name("preferences-system-symbolic", Gtk.IconSize.BUTTON)
            self.ui_menusettings_label.set_text(_("Settings"))
            self.ui_menudistupgrade_image.set_from_icon_name("go-up-symbolic", Gtk.IconSize.BUTTON)
            self.ui_menudistupgrade_label.set_text(_("Version Upgrade"))
            self.ui_headerbar_messageimage.set_from_icon_name("mail-unread-symbolic", Gtk.IconSize.BUTTON)
            self.main_window.set_visible(True)
            self.main_window.present()
            self.item_sh_app.set_label(_("Hide App"))

    def define_components(self):
        self.main_window = self.GtkBuilder.get_object("ui_main_window")
        self.about_dialog = self.GtkBuilder.get_object("ui_about_dialog")
        self.ui_quit_dialog = self.GtkBuilder.get_object("ui_quit_dialog")
        self.ui_main_stack = self.GtkBuilder.get_object("ui_main_stack")
        self.ui_upgrade_button = self.GtkBuilder.get_object("ui_upgrade_button")
        self.ui_upgradeoptions_button = self.GtkBuilder.get_object("ui_upgradeoptions_button")
        self.ui_upgrade_buttonbox = self.GtkBuilder.get_object("ui_upgrade_buttonbox")
        self.ui_upgrade_buttonbox.set_homogeneous(False)
        self.ui_uptodate_image = self.GtkBuilder.get_object("ui_uptodate_image")

        self.ui_menu_popover = self.GtkBuilder.get_object("ui_menu_popover")
        self.ui_menusettings_image = self.GtkBuilder.get_object("ui_menusettings_image")
        self.ui_menusettings_label = self.GtkBuilder.get_object("ui_menusettings_label")
        self.ui_menudistupgrade_image = self.GtkBuilder.get_object("ui_menudistupgrade_image")
        self.ui_menudistupgrade_label = self.GtkBuilder.get_object("ui_menudistupgrade_label")
        self.ui_menudistupgrade_separator = self.GtkBuilder.get_object("ui_menudistupgrade_separator")
        self.ui_menudistupgrade_button = self.GtkBuilder.get_object("ui_menudistupgrade_button")
        self.ui_headerbar_messagebutton = self.GtkBuilder.get_object("ui_headerbar_messagebutton")
        self.ui_headerbar_messageimage = self.GtkBuilder.get_object("ui_headerbar_messageimage")
        self.ui_updatefreq_combobox = self.GtkBuilder.get_object("ui_updatefreq_combobox")
        self.ui_updatefreq_spin = self.GtkBuilder.get_object("ui_updatefreq_spin")
        self.ui_updatefreq_stack = self.GtkBuilder.get_object("ui_updatefreq_stack")
        self.ui_settingslastupdate_label = self.GtkBuilder.get_object("ui_settingslastupdate_label")
        self.ui_autostart_switch = self.GtkBuilder.get_object("ui_autostart_switch")
        self.ui_selectable_updates_switch = self.GtkBuilder.get_object("ui_selectable_updates_switch")
        self.ui_notifications_switch = self.GtkBuilder.get_object("ui_notifications_switch")
        self.ui_update_selectable_info_popover = self.GtkBuilder.get_object("ui_update_selectable_info_popover")

        self.ui_autoremovable_box = self.GtkBuilder.get_object("ui_autoremovable_box")
        self.ui_residual_box = self.GtkBuilder.get_object("ui_residual_box")
        self.ui_autoremovable_textview = self.GtkBuilder.get_object("ui_autoremovable_textview")
        self.ui_residual_textview = self.GtkBuilder.get_object("ui_residual_textview")

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
        self.ui_upgradeinfo_label = self.GtkBuilder.get_object("ui_upgradeinfo_label")
        self.ui_upgradeinfook_button = self.GtkBuilder.get_object("ui_upgradeinfook_button")
        self.ui_upgradeinfo_spinner = self.GtkBuilder.get_object("ui_upgradeinfo_spinner")
        self.ui_upgradeinfobusy_box = self.GtkBuilder.get_object("ui_upgradeinfobusy_box")
        self.ui_upgradeinfofixdpkg_button = self.GtkBuilder.get_object("ui_upgradeinfofixdpkg_button")

        self.ui_fix_stack = self.GtkBuilder.get_object("ui_fix_stack")
        self.ui_fix_button = self.GtkBuilder.get_object("ui_fix_button")
        self.ui_fix_spinner = self.GtkBuilder.get_object("ui_fix_spinner")
        self.ui_fixvte_sw = self.GtkBuilder.get_object("ui_fixvte_sw")

        self.ui_dpkgconfigureinfo_box = self.GtkBuilder.get_object("ui_dpkgconfigureinfo_box")
        self.ui_dpkgconfigureinfo_label = self.GtkBuilder.get_object("ui_dpkgconfigureinfo_label")
        self.ui_dpkgconfigureinfo_spinner = self.GtkBuilder.get_object("ui_dpkgconfigureinfo_spinner")
        self.ui_dpkgconfigureok_button = self.GtkBuilder.get_object("ui_dpkgconfigureok_button")
        self.ui_dpkgconfigurevte_sw = self.GtkBuilder.get_object("ui_dpkgconfigurevte_sw")
        self.ui_dpkgconfigurefix_box = self.GtkBuilder.get_object("ui_dpkgconfigurefix_box")
        self.ui_dpkgconfigurefix_label = self.GtkBuilder.get_object("ui_dpkgconfigurefix_label")
        self.ui_dpkgconfigurefix_button = self.GtkBuilder.get_object("ui_dpkgconfigurefix_button")

        self.ui_distup_now_label = self.GtkBuilder.get_object("ui_distup_now_label")
        self.ui_distup_new_label = self.GtkBuilder.get_object("ui_distup_new_label")

        # Dist upgrade widgets
        self.ui_distupgrade_stack = self.GtkBuilder.get_object("ui_distupgrade_stack")
        self.ui_distupgradeoptions_popover = self.GtkBuilder.get_object("ui_distupgradeoptions_popover")
        self.ui_distupgradecontrol_spinner = self.GtkBuilder.get_object("ui_distupgradecontrol_spinner")
        self.ui_controldistup_button = self.GtkBuilder.get_object("ui_controldistup_button")
        self.ui_homedistupgrade_box = self.GtkBuilder.get_object("ui_homedistupgrade_box")
        self.ui_homecontroldistup_label = self.GtkBuilder.get_object("ui_homecontroldistup_label")
        self.ui_distupgotoupdates_box = self.GtkBuilder.get_object("ui_distupgotoupdates_box")
        self.ui_distuptodown_button = self.GtkBuilder.get_object("ui_distuptodown_button")
        self.ui_distuptodownretry_button = self.GtkBuilder.get_object("ui_distuptodownretry_button")
        self.ui_rootdisk_box = self.GtkBuilder.get_object("ui_rootdisk_box")
        self.ui_distupgradevte_sw = self.GtkBuilder.get_object("ui_distupgradevte_sw")
        self.ui_distuptoinstallcancel_button = self.GtkBuilder.get_object("ui_distuptoinstallcancel_button")
        self.ui_distupgrade_textview = self.GtkBuilder.get_object("ui_distupgrade_textview")
        self.ui_distupgradetextview_box = self.GtkBuilder.get_object("ui_distupgradetextview_box")
        self.ui_distupgrade_buttonbox = self.GtkBuilder.get_object("ui_distupgrade_buttonbox")
        self.ui_distupgrade_buttonbox.set_homogeneous(False)

        self.ui_controldistuperror_box = self.GtkBuilder.get_object("ui_controldistuperror_box")
        self.ui_controldistuperror_label = self.GtkBuilder.get_object("ui_controldistuperror_label")

        self.ui_distupgrade_defaults_button = self.GtkBuilder.get_object("ui_distupgrade_defaults_button")
        self.ui_distupgradenewconf_radiobutton = self.GtkBuilder.get_object("ui_distupgradenewconf_radiobutton")
        self.ui_distupgradeoldconf_radiobutton = self.GtkBuilder.get_object("ui_distupgradeoldconf_radiobutton")

        self.ui_distuptoinstall_button = self.GtkBuilder.get_object("ui_distuptoinstall_button")
        self.ui_distupdowninfo_label = self.GtkBuilder.get_object("ui_distupdowninfo_label")
        self.ui_distupdowninfo_spinner = self.GtkBuilder.get_object("ui_distupdowninfo_spinner")

        self.ui_distupgrade_button = self.GtkBuilder.get_object("ui_distupgrade_button")
        self.ui_distupgrade_lastinfo_box = self.GtkBuilder.get_object("ui_distupgrade_lastinfo_box")
        self.ui_distupgrade_lastinfo_spinner = self.GtkBuilder.get_object("ui_distupgrade_lastinfo_spinner")

        self.ui_distupgradable_sw = self.GtkBuilder.get_object("ui_distupgradable_sw")
        self.ui_distnewly_sw = self.GtkBuilder.get_object("ui_distnewly_sw")
        self.ui_distremovable_sw = self.GtkBuilder.get_object("ui_distremovable_sw")
        self.ui_distkept_sw = self.GtkBuilder.get_object("ui_distkept_sw")

        self.ui_distupgradable_listbox = self.GtkBuilder.get_object("ui_distupgradable_listbox")
        self.ui_distnewly_listbox = self.GtkBuilder.get_object("ui_distnewly_listbox")
        self.ui_distremovable_listbox = self.GtkBuilder.get_object("ui_distremovable_listbox")
        self.ui_distkept_listbox = self.GtkBuilder.get_object("ui_distkept_listbox")

        self.ui_distdownloadsize_box = self.GtkBuilder.get_object("ui_distdownloadsize_box")
        self.ui_distinstallsize_box = self.GtkBuilder.get_object("ui_distinstallsize_box")
        self.ui_distupgradecount_box = self.GtkBuilder.get_object("ui_distupgradecount_box")
        self.ui_distnewlycount_box = self.GtkBuilder.get_object("ui_distnewlycount_box")
        self.ui_distremovecount_box = self.GtkBuilder.get_object("ui_distremovecount_box")
        self.ui_distkeptcount_box = self.GtkBuilder.get_object("ui_distkeptcount_box")

        self.ui_distdownloadsize_label = self.GtkBuilder.get_object("ui_distdownloadsize_label")
        self.ui_distinstallsize_label = self.GtkBuilder.get_object("ui_distinstallsize_label")
        self.ui_distupgradecount_label = self.GtkBuilder.get_object("ui_distupgradecount_label")
        self.ui_distnewlycount_label = self.GtkBuilder.get_object("ui_distnewlycount_label")
        self.ui_distremovecount_label = self.GtkBuilder.get_object("ui_distremovecount_label")
        self.ui_distkeptcount_label = self.GtkBuilder.get_object("ui_distkeptcount_label")

        self.ui_rootusage_progressbar = self.GtkBuilder.get_object("ui_rootusage_progressbar")
        self.ui_rootfree_label = self.GtkBuilder.get_object("ui_rootfree_label")
        self.ui_roottotal_label = self.GtkBuilder.get_object("ui_roottotal_label")
        self.ui_distrequireddiskinfo_label = self.GtkBuilder.get_object("ui_distrequireddiskinfo_label")

        self.ui_settingsapt_stack = self.GtkBuilder.get_object("ui_settingsapt_stack")
        self.ui_settings_apt_clear_box = self.GtkBuilder.get_object("ui_settings_apt_clear_box")
        self.ui_settings_vte_box = self.GtkBuilder.get_object("ui_settings_vte_box")
        self.ui_aptclean_size_label = self.GtkBuilder.get_object("ui_aptclean_size_label")
        self.ui_aptautoremove_size_label = self.GtkBuilder.get_object("ui_aptautoremove_size_label")
        self.ui_aptlists_size_label = self.GtkBuilder.get_object("ui_aptlists_size_label")
        self.ui_settingsvte_sw = self.GtkBuilder.get_object("ui_settingsvte_sw")
        self.ui_settings_aptclear_ok_button = self.GtkBuilder.get_object("ui_settings_aptclear_ok_button")
        self.ui_apt_clean_checkbutton = self.GtkBuilder.get_object("ui_apt_clean_checkbutton")
        self.ui_apt_autoremove_checkbutton = self.GtkBuilder.get_object("ui_apt_autoremove_checkbutton")
        self.ui_apt_listsclean_checkbutton = self.GtkBuilder.get_object("ui_apt_listsclean_checkbutton")
        self.ui_settings_aptclear_popover = self.GtkBuilder.get_object("ui_settings_aptclear_popover")
        self.ui_settings_aptclear_textview = self.GtkBuilder.get_object("ui_settings_aptclear_textview")

        self.ui_sources_listbox = self.GtkBuilder.get_object("ui_sources_listbox")
        self.ui_settings_default_sources_button = self.GtkBuilder.get_object("ui_settings_default_sources_button")
        self.ui_settings_sourceslist_info_label = self.GtkBuilder.get_object("ui_settings_sourceslist_info_label")
        self.ui_settings_fix_slistd_checkbox = self.GtkBuilder.get_object("ui_settings_fix_slistd_checkbox")
        self.ui_settings_fixbroken_checkbox = self.GtkBuilder.get_object("ui_settings_fixbroken_checkbox")
        self.ui_settings_dpkgconfigure_checkbox = self.GtkBuilder.get_object("ui_settings_dpkgconfigure_checkbox")
        self.ui_settings_remove_slistd_radiobutton = self.GtkBuilder.get_object("ui_settings_remove_slistd_radiobutton")
        self.ui_settings_cout_slistd_radiobutton = self.GtkBuilder.get_object("ui_settings_cout_slistd_radiobutton")
        self.ui_settings_fix_slistd_sub_box = self.GtkBuilder.get_object("ui_settings_fix_slistd_sub_box")

        self.ui_passwordless_button = self.GtkBuilder.get_object("ui_passwordless_button")
        self.ui_passwordless_button_label = self.GtkBuilder.get_object("ui_passwordless_button_label")

        self.ui_conerror_info_label = self.GtkBuilder.get_object("ui_conerror_info_label")
        self.ui_conerror_info_popover = self.GtkBuilder.get_object("ui_conerror_info_popover")

        self.upgrade_vteterm = None
        self.distupgrade_vteterm = None
        self.fix_vteterm = None
        self.dpkgconfigure_vteterm = None
        self.settings_vteterm = None

    def define_variables(self):
        system_wide = "usr/share" in os.path.dirname(os.path.abspath(__file__))
        self.icon_available = "pardus-update-available-symbolic" if system_wide else "software-update-available-symbolic"
        self.icon_normal = "pardus-update-symbolic" if system_wide else "security-medium-symbolic"
        self.icon_inprogress = "pardus-update-inprogress-symbolic" if system_wide else "emblem-synchronizing-symbolic"
        self.icon_error = "pardus-update-error-symbolic" if system_wide else "security-low-symbolic"

        if not xfce_desktop:
            self.icon_available = "software-update-available-symbolic"
            self.icon_normal = "security-medium-symbolic"
            self.icon_inprogress = "emblem-synchronizing-symbolic"
            self.icon_error = "security-low-symbolic"

        self.autoupdate_glibid = None
        self.autoupgrade_glibid = None
        self.autoupdate_monitoring_glibid = None
        self.monitoring_timeoutadd_sec = 60
        self.update_inprogress = False
        self.upgrade_inprogress = False
        self.auto_upgrade_inprogress = False
        self.distup_download_inprogress = False
        self.laststack = None
        self.aptlist_directory = "/var/lib/apt/lists"
        self.dpkg_directory = "/var/lib/dpkg"

        self.clean_residuals_clicked = False

        self.dpkgconfiguring = False

        self.dist_upgradable = False

        self.autoupgrade_enabled = False

        self.user_keep_list = []
        self.user_keep_list_depends = []

        self.source_switch_clicked = False

        self.user_default_sources_list = None

        self.sources_err_count = 0
        self.sources_err_lines = ""

        try:
            self.user_distro_id = distro.id()
            self.user_distro_version = int(distro.major_version())
            self.user_distro_codename = distro.codename().lower()
            self.pargnome23 = gnome_desktop and self.user_distro_id == "pardus" and self.user_distro_version == 23
        except Exception as e:
            print("{}".format(e))
            self.user_distro_id = None
            self.user_distro_version = None
            self.user_distro_codename = None
            self.pargnome23 = False

        try:
            static_sources_file = os.path.dirname(os.path.abspath(__file__)) + "/../data/sources.json"
            if os.path.isfile(static_sources_file):
                with open(static_sources_file, "r", encoding="utf-8") as f:
                    static_sources = json.load(f)
                    if self.user_distro_id and self.user_distro_version and self.user_distro_codename:
                        if self.user_distro_id in static_sources.keys():
                            for codename in static_sources[self.user_distro_id]:
                                if codename["name"] == self.user_distro_codename:
                                    self.user_default_sources_list = codename["sources"]
        except Exception as e:
            print("{}".format(e))

    def define_last_variables(self):
        self.auto_upgrade_init = False

        if self.SystemSettings.config_upgrade_enabled is None or self.SystemSettings.config_upgrade_interval is None:
            self.autoupgrade_enabled = False
        else:
            self.autoupgrade_enabled = self.SystemSettings.config_upgrade_enabled

    def set_initial_hide_widgets(self):
        GLib.idle_add(self.ui_headerbar_messagebutton.set_visible, False)
        GLib.idle_add(self.ui_menudistupgrade_separator.set_visible, False)
        GLib.idle_add(self.ui_menudistupgrade_button.set_visible, False)
        GLib.idle_add(self.ui_distupgotoupdates_box.set_visible, False)
        GLib.idle_add(self.ui_rootdisk_box.set_visible, False)
        GLib.idle_add(self.ui_distuptodownretry_button.set_visible, False)
        GLib.idle_add(self.ui_controldistuperror_box.set_visible, False)
        GLib.idle_add(self.ui_homedistupgrade_box.set_visible, False)
        GLib.idle_add(self.ui_upgradeinfobusy_box.set_visible, False)
        GLib.idle_add(self.ui_dpkgconfigureinfo_box.set_visible, False)
        GLib.idle_add(self.ui_distupgradetextview_box.set_visible, False)
        GLib.idle_add(self.ui_upgradeinfofixdpkg_button.set_visible, False)
        GLib.idle_add(self.ui_settings_aptclear_ok_button.set_visible, False)
        GLib.idle_add(self.ui_settings_apt_clear_box.set_visible, False)
        GLib.idle_add(self.ui_settings_vte_box.set_visible, False)
        GLib.idle_add(self.ui_settings_default_sources_button.set_visible, False)

    def control_display(self):
        width = 575
        height = 650
        s = 1
        w = 1920
        h = 1080
        try:
            display = Gdk.Display.get_default()
            monitor = display.get_primary_monitor()
            geometry = monitor.get_geometry()
            w = geometry.width
            h = geometry.height
            s = Gdk.Monitor.get_scale_factor(monitor)

            if w > 1920 or h > 1080:
                width = int(w / 3.339)
                height = int(h / 1.661)

            self.main_window.resize(width, height)

        except Exception as e:
            print("Error in controlDisplay: {}".format(e))

        print("window w:{} h:{} | monitor w:{} h:{} s:{}".format(width, height, w, h, s))

    def update_vte_color(self, vte):
        style_context = self.main_window.get_style_context()
        background_color= style_context.get_background_color(Gtk.StateFlags.NORMAL);
        foreground_color= style_context.get_color(Gtk.StateFlags.NORMAL);
        vte.set_color_background(background_color)
        vte.set_color_foreground(foreground_color)

    def user_settings(self):
        self.UserSettings = UserSettings()
        self.UserSettings.createDefaultConfig()
        self.UserSettings.readConfig()

        print("{} {}".format("config_update_interval", self.UserSettings.config_update_interval))
        print("{} {} ({})".format("config_update_lastupdate", self.UserSettings.config_update_lastupdate,
                                  datetime.fromtimestamp(self.UserSettings.config_update_lastupdate)))
        print("{} {}".format("config_update_selectable", self.UserSettings.config_update_selectable))
        print("{} {}".format("config_autostart", self.UserSettings.config_autostart))
        print("{} {}".format("config_notifications", self.UserSettings.config_notifications))

    def system_settings(self):
        self.SystemSettings = SystemSettings()
        self.SystemSettings.readConfig()

        try:
            if self.SystemSettings.config_update_interval is not None:
                print("system: {} {}".format("config_update_interval", self.SystemSettings.config_update_interval))
            if self.SystemSettings.config_update_lastupdate is not None:
                print("system: {} {}".format("config_update_lastupdate", self.SystemSettings.config_update_lastupdate))
            if self.SystemSettings.config_update_selectable is not None:
                print("system: {} {}".format("config_update_selectable", self.SystemSettings.config_update_selectable))
            if self.SystemSettings.config_autostart is not None:
                print("system: {} {}".format("config_autostart", self.SystemSettings.config_autostart))
            if self.SystemSettings.config_notifications is not None:
                print("system: {} {}".format("config_notifications", self.SystemSettings.config_notifications))

            if self.SystemSettings.config_upgrade_enabled is not None:
                print("system: {} {}".format("config_upgrade_enabled",
                                             self.SystemSettings.config_upgrade_enabled))
            if self.SystemSettings.config_upgrade_interval is not None:
                print("system: {} {}".format("config_upgrade_interval",
                                             self.SystemSettings.config_upgrade_interval))
            if self.SystemSettings.config_upgrade_lastupgrade is not None:
                print("system: {} {}".format("config_upgrade_lastupgrade",
                                             self.SystemSettings.config_upgrade_lastupgrade))
            if self.SystemSettings.config_upgrade_fix is not None:
                print("system: {} {}".format("config_upgrade_fix", self.SystemSettings.config_upgrade_fix))
            if self.SystemSettings.config_upgrade_sources is not None:
                print("system: {} {}".format("config_upgrade_sources",
                                             self.SystemSettings.config_upgrade_sources))
        except Exception as e:
            print("system_settings exception: {}".format(e))

    def init_ui(self):
        self.ui_main_stack.set_visible_child_name("spinner")
        system_wide = "usr/share" in os.path.dirname(os.path.abspath(__file__))
        if not system_wide:
            self.main_window.set_default_icon_from_file(
                os.path.dirname(os.path.abspath(__file__)) + "/../data/pardus-update.svg")
            self.about_dialog.set_logo(None)
            self.ui_uptodate_image.set_from_pixbuf(
                GdkPixbuf.Pixbuf.new_from_file_at_size(
                    os.path.dirname(os.path.abspath(__file__)) + "/../data/pardus-update-uptodate.svg", 288, 288))

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
        self.item_separator3 = Gtk.SeparatorMenuItem()

        self.item_quit = Gtk.MenuItem()
        self.item_quit.set_label(_("Quit"))
        self.item_quit.connect('activate', self.on_menu_quit_app)

        self.item_lastcheck = Gtk.MenuItem()
        self.item_lastcheck.set_sensitive(False)
        self.item_lastcheck.set_label("{}: {}".format(_("Last Check"),
                                                      datetime.fromtimestamp(self.UserSettings.config_update_lastupdate)))

        self.item_settings = Gtk.MenuItem()
        self.item_settings.set_label(_("Settings"))
        self.item_settings.connect('activate', self.on_menu_settings_app)

        self.item_systemstatus = Gtk.MenuItem()
        self.item_systemstatus.set_label(_("System is Up to Date"))
        self.item_systemstatus.set_sensitive(False if not self.pargnome23 else True)
        self.item_systemstatus.connect('activate', self.on_menu_updatespage_app)

        self.menu.append(self.item_sh_app)
        self.menu.append(self.item_separator1)

        self.menu.append(self.item_systemstatus)
        self.menu.append(self.item_separator2)

        self.menu.append(self.item_update)
        self.menu.append(self.item_lastcheck)
        self.menu.append(self.item_separator3)

        self.menu.append(self.item_settings)
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
        self.apt_update(force=True)

    def on_menu_show_app(self, *args):
        window_state = self.main_window.is_visible()
        if window_state:
            self.main_window.set_visible(False)
            self.item_sh_app.set_label(_("Show App"))
        else:
            self.main_window.set_visible(True)
            self.item_sh_app.set_label(_("Hide App"))
            self.main_window.present()

    def on_menu_settings_app(self, *args):

        if self.ui_main_stack.get_visible_child_name() != "clean" and \
                self.ui_main_stack.get_visible_child_name() != "settings" and \
                self.ui_main_stack.get_visible_child_name() != "distupgrade":
            self.laststack = self.ui_main_stack.get_visible_child_name()

        self.ui_menusettings_image.set_from_icon_name("user-home-symbolic", Gtk.IconSize.BUTTON)
        self.ui_menusettings_label.set_text(_("Home Page"))
        self.ui_main_stack.set_visible_child_name("settings")

        self.ui_menudistupgrade_image.set_from_icon_name("go-up-symbolic", Gtk.IconSize.BUTTON)
        self.ui_menudistupgrade_label.set_text(_("Version Upgrade"))

        self.set_settings_widgets()

        self.main_window.set_visible(True)
        self.main_window.present()
        self.item_sh_app.set_label(_("Hide App"))

    def on_menu_updatespage_app(self, *args):
        if self.upgrade_inprogress or self.clean_residuals_clicked:
            self.ui_main_stack.set_visible_child_name("upgrade")
        else:
            if self.isbroken:
                self.ui_main_stack.set_visible_child_name("fix")
            else:
                if self.sources_err_count == 0:
                    if self.Package.upgradable():
                        self.ui_main_stack.set_visible_child_name("updateinfo")
                    else:
                        self.ui_main_stack.set_visible_child_name("ok")
                else:
                    self.ui_main_stack.set_visible_child_name("conerror")
        self.ui_menusettings_image.set_from_icon_name("preferences-system-symbolic", Gtk.IconSize.BUTTON)
        self.ui_menusettings_label.set_text(_("Settings"))
        self.ui_menudistupgrade_image.set_from_icon_name("go-up-symbolic", Gtk.IconSize.BUTTON)
        self.ui_menudistupgrade_label.set_text(_("Version Upgrade"))
        self.ui_headerbar_messageimage.set_from_icon_name("mail-unread-symbolic", Gtk.IconSize.BUTTON)
        self.main_window.set_visible(True)
        self.main_window.present()
        self.item_sh_app.set_label(_("Hide App"))

    def on_ui_checkupdates_button_clicked(self, button):
        if button.get_name() == "fromdist":
            self.ui_menudistupgrade_image.set_from_icon_name("go-up-symbolic", Gtk.IconSize.BUTTON)
            self.ui_menudistupgrade_label.set_text(_("Version Upgrade"))

        self.ui_main_stack.set_visible_child_name("spinner")
        if self.autoupdate_glibid:
            GLib.source_remove(self.autoupdate_glibid)
            self.autoupdate_glibid = None
        self.apt_update(force=True)

    def on_ui_upgradeinfook_button_clicked(self, button):
        self.control_update_residual_message_section()
        if self.Package.upgradable():
            self.apt_update()
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
        if self.upgrade_vteterm:
            self.upgrade_vteterm.reset(True, True)

        self.ui_upgradevte_sw.set_visible(True)
        self.ui_main_stack.set_visible_child_name("upgrade")

        self.ui_upgradeinfo_spinner.start()
        self.ui_upgradeinfo_spinner.set_visible(True)

        self.ui_upgradeinfobusy_box.set_visible(False)

        self.ui_upgradeinfook_button.set_visible(False)

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
            self.ui_upgradeinfo_label.set_markup(
                "<b>{}</b>".format(_("Updates are installing. Please wait...")))

            self.item_systemstatus.set_label(_("Updating"))

            command = ["/usr/bin/pkexec", os.path.dirname(os.path.abspath(__file__)) + "/SysActions.py",
                       "upgrade", yq_conf, dpkg_conf, " ".join(self.user_keep_list)]
            self.upgrade_vte_start_process(command)
            self.upgrade_inprogress = True
        else:
            print("upgrade in progress")
            self.ui_upgradeinfobusy_box.set_visible(True)

    def on_ui_autoremovable_button_clicked(self, button):
        self.clean_residuals_clicked = True
        if self.upgrade_vteterm:
            self.upgrade_vteterm.reset(True, True)
        self.ui_upgradevte_sw.set_visible(True)
        self.ui_main_stack.set_visible_child_name("upgrade")

        self.ui_upgradeinfo_spinner.start()
        self.ui_upgradeinfo_spinner.set_visible(True)

        self.ui_upgradeinfobusy_box.set_visible(False)

        self.ui_upgradeinfook_button.set_visible(False)

        if not self.upgrade_inprogress:
            self.ui_upgradeinfo_label.set_markup(
                "<b>{}</b>".format(_("Packages are removing. Please wait...")))

            command = ["/usr/bin/pkexec", os.path.dirname(os.path.abspath(__file__)) + "/SysActions.py", "removeauto"]
            self.upgrade_vte_start_process(command)
            self.upgrade_inprogress = True
        else:
            print("upgrade in progress")
            self.ui_upgradeinfobusy_box.set_visible(True)

    def on_ui_residual_button_clicked(self, button):
        self.clean_residuals_clicked = True
        if self.upgrade_vteterm:
            self.upgrade_vteterm.reset(True, True)

        self.ui_upgradevte_sw.set_visible(True)
        self.ui_main_stack.set_visible_child_name("upgrade")

        self.ui_upgradeinfo_spinner.start()
        self.ui_upgradeinfo_spinner.set_visible(True)

        self.ui_upgradeinfobusy_box.set_visible(False)

        self.ui_upgradeinfook_button.set_visible(False)

        if not self.upgrade_inprogress:
            self.ui_upgradeinfo_label.set_markup(
                "<b>{}</b>".format(_("Packages are removing. Please wait...")))

            command = ["/usr/bin/pkexec", os.path.dirname(os.path.abspath(__file__)) + "/SysActions.py",
                       "removeresidual", " ".join(self.Package.residual())]
            self.upgrade_vte_start_process(command)
            self.upgrade_inprogress = True
        else:
            print("upgrade in progress")
            self.ui_upgradeinfobusy_box.set_visible(True)

    def on_ui_clear_apt_button_clicked(self, button):
        GLib.idle_add(self.ui_settingsapt_stack.set_visible_child_name, "spinner")
        threading.Thread(target=self.clear_apt_worker_thread, daemon=True).start()

    def clear_apt_worker_thread(self):
        ret = self.clear_apt_worker()
        GLib.idle_add(self.clear_apt_worker_done, ret)

    def clear_apt_worker(self):
        self.Package.updatecache()
        self.aptclear_autoremove_list = self.Package.autoremovable()
        return self.Package.required_changes_autoremove(self.aptclear_autoremove_list)

    def clear_apt_worker_done(self, ret):
        GLib.idle_add(self.ui_settings_apt_clear_box.set_visible, True)
        GLib.idle_add(self.ui_settingsapt_stack.set_visible_child_name, "apt")

        apt_clean_path = "/var/cache/apt/archives"
        apt_lists_path = "/var/lib/apt/lists"

        self.aptclear_clean_list = self.Utils.get_path_files(apt_clean_path)
        self.aptclear_lists_list = self.Utils.get_path_files(apt_lists_path)

        GLib.idle_add(self.ui_aptclean_size_label.set_markup,
                      "{}".format(self.Package.beauty_size(self.Utils.get_path_size(apt_clean_path))))

        GLib.idle_add(self.ui_aptlists_size_label.set_markup,
                      "{}".format(self.Package.beauty_size(self.Utils.get_path_size(apt_lists_path))))

        GLib.idle_add(self.ui_aptautoremove_size_label.set_markup,
                      "{}".format(self.Package.beauty_size(ret["freed_size"])))

    def on_ui_settingsaptcancel_button_clicked(self, button):
        self.ui_settingsapt_stack.set_visible_child_name("main")

        self.ui_settings_apt_clear_box.set_visible(False)
        self.ui_settings_vte_box.set_visible(False)

    def on_ui_settingsaptclear_button_clicked(self, button):
        if not self.update_inprogress and not self.upgrade_inprogress and not self.auto_upgrade_inprogress:

            GLib.idle_add(self.ui_settings_aptclear_ok_button.set_visible, False)

            aptclean = "1" if self.ui_apt_clean_checkbutton.get_active() else "0"
            aptautoremove = "1" if self.ui_apt_autoremove_checkbutton.get_active() else "0"
            aptlistsclean = "1" if self.ui_apt_listsclean_checkbutton.get_active() else "0"

            command = ["/usr/bin/pkexec", os.path.dirname(os.path.abspath(__file__)) + "/SysActions.py",
                       "aptclear", aptclean, aptautoremove, aptlistsclean]
            self.settings_vte_start_process(command)

            self.ui_settings_vte_box.set_visible(True)
            self.ui_settingsapt_stack.set_visible_child_name("vte")

            self.update_inprogress = True

        else:
            ErrorDialog(_("Error"), _("Package manager is busy, try again after the process is completed."))


    def on_ui_settings_aptclear_ok_button_clicked(self, button):
        self.ui_settingsapt_stack.set_visible_child_name("main")

        self.ui_settings_apt_clear_box.set_visible(False)
        self.ui_settings_vte_box.set_visible(False)

        self.ui_main_stack.set_visible_child_name("spinner")
        self.ui_menusettings_image.set_from_icon_name("preferences-system-symbolic", Gtk.IconSize.BUTTON)
        self.ui_menusettings_label.set_text(_("Settings"))
        self.apt_update(force=True)

    def on_ui_settings_aptclear_info_button_clicked(self, button):
        def clear_textview():
            start, end = self.ui_settings_aptclear_textview.get_buffer().get_bounds()
            self.ui_settings_aptclear_textview.get_buffer().delete(start, end)

        self.ui_settings_aptclear_popover.set_relative_to(button)
        self.ui_settings_aptclear_popover.popup()

        clear_textview()

        if button.get_name() == "clean":
            self.ui_settings_aptclear_textview.get_buffer().insert(
                self.ui_settings_aptclear_textview.get_buffer().get_end_iter(),
                "\n".join(self.aptclear_clean_list))
        elif button.get_name() == "autoremove":
            self.ui_settings_aptclear_textview.get_buffer().insert(
                self.ui_settings_aptclear_textview.get_buffer().get_end_iter(),
                "\n".join(self.aptclear_autoremove_list))
        elif button.get_name() == "lists":
            self.ui_settings_aptclear_textview.get_buffer().insert(
                self.ui_settings_aptclear_textview.get_buffer().get_end_iter(),
                "\n".join(self.aptclear_lists_list))

    def on_ui_fix_sources_button_clicked(self, button):
        GLib.idle_add(self.clear_sources_listbox)

        GLib.idle_add(self.ui_settings_default_sources_button.set_visible, self.user_default_sources_list is not None)
        GLib.idle_add(self.ui_settings_sourceslist_info_label.set_tooltip_text, "{}\n\n{}".format(
            _("The default sources list is as follows."), self.user_default_sources_list))

        self.ui_settingsapt_stack.set_visible_child_name("sources")
        repos = self.Package.get_sources()

        for source in repos.values():
            # print(source)
            for sub in source:
                print(sub)
                repo_name = Gtk.Label.new()
                repo_name.set_markup("{} {} {} {}".format(sub["type"], sub["uri"], sub["dist"], " ".join(sub["comps"])))
                repo_name.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
                # repo_name.set_tooltip_text("{} {} {}".format(sub["type"], sub["uri"], " ".join(sub["comps"])))

                switch_button = Gtk.Switch.new()
                switch_button.set_active(not sub["disabled"])
                switch_button.connect("state_set", self.on_source_switch_state_set)
                switch_button.name = {"line": sub["line"], "path": sub["file"]}

                box1 = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 21)
                box1.pack_start(repo_name, False, True, 0)
                box1.pack_end(switch_button, False, True, 8)
                box1.props.valign = Gtk.Align.CENTER

                box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 3)
                box.set_margin_top(5)
                box.set_margin_bottom(5)
                box.set_margin_start(5)
                box.set_margin_end(5)

                box.pack_start(box1, False, True, 0)

                GLib.idle_add(self.ui_sources_listbox.insert, box, -1)


        GLib.idle_add(self.ui_sources_listbox.show_all)

    def clear_sources_listbox(self,):
        self.ui_sources_listbox.foreach(lambda child: self.ui_sources_listbox.remove(child))

    def on_source_switch_state_set(self, switch, state):
        if not self.update_inprogress and not self.upgrade_inprogress and not self.auto_upgrade_inprogress:

            self.source_switch_clicked = True

            GLib.idle_add(self.ui_settings_aptclear_ok_button.set_visible, False)

            command = ["/usr/bin/pkexec", os.path.dirname(os.path.abspath(__file__)) + "/SysActions.py",
                       "setsourcestate", "1" if state else "0", switch.name["line"], switch.name["path"]]
            self.settings_vte_start_process(command)
            self.ui_settings_vte_box.set_visible(True)
            self.ui_settingsapt_stack.set_visible_child_name("vte")

            self.update_inprogress = True

        else:
            ErrorDialog(_("Error"), _("Package manager is busy, try again after the process is completed."))

    def on_ui_settings_default_sources_button_clicked(self, button):
        self.ui_settingsapt_stack.set_visible_child_name("defaultsources")

    def on_ui_settings_default_sources_accept_button_clicked(self, button):
        if not self.update_inprogress and not self.upgrade_inprogress and not self.auto_upgrade_inprogress:

            if self.user_default_sources_list is None:
                ErrorDialog(_("Error"), "{}\n{}\n{}\n{}".format(_("Your system is not supported."),
                                                                self.user_distro_id, self.user_distro_version,
                                                                self.user_distro_codename))
                return

            GLib.idle_add(self.ui_settings_aptclear_ok_button.set_visible, False)

            command = ["/usr/bin/pkexec", os.path.dirname(os.path.abspath(__file__)) + "/SysActions.py", "fixsources",
                       self.user_default_sources_list,
                       "1" if self.ui_settings_fix_slistd_checkbox.get_active() else "0",
                       "1" if self.ui_settings_remove_slistd_radiobutton.get_active() else "0",
                       "1" if self.ui_settings_dpkgconfigure_checkbox.get_active() else "0",
                       "1" if self.ui_settings_fixbroken_checkbox.get_active() else "0"]
            self.settings_vte_start_process(command)
            self.ui_settings_vte_box.set_visible(True)
            self.ui_settingsapt_stack.set_visible_child_name("vte")

            self.update_inprogress = True

        else:
            ErrorDialog(_("Error"), _("Package manager is busy, try again after the process is completed."))


    def on_ui_settings_default_sources_cancel_button_clicked(self, button):
        self.ui_settingsapt_stack.set_visible_child_name("sources")

    def on_ui_settings_fix_slistd_checkbox_toggled(self, toggle_button):
        self.ui_settings_fix_slistd_sub_box.set_visible(toggle_button.get_active())

    def on_ui_controldistup_button_clicked(self, button):
        if self.ui_main_stack.get_visible_child_name() != "clean" and \
                self.ui_main_stack.get_visible_child_name() != "settings" and \
                self.ui_main_stack.get_visible_child_name() != "distupgrade":
            self.laststack = self.ui_main_stack.get_visible_child_name()
        self.ui_menudistupgrade_image.set_from_icon_name("user-home-symbolic", Gtk.IconSize.BUTTON)
        self.ui_menudistupgrade_label.set_text(_("Home Page"))
        self.ui_main_stack.set_visible_child_name("distupgrade")
        self.ui_menusettings_image.set_from_icon_name("preferences-system-symbolic", Gtk.IconSize.BUTTON)
        self.ui_menusettings_label.set_text(_("Settings"))
        self.ui_headerbar_messageimage.set_from_icon_name("mail-unread-symbolic", Gtk.IconSize.BUTTON)

        if button.get_name() == "retry":
            self.ui_distupgrade_stack.set_visible_child_name("control")
        elif button.get_name() == "homecontrol":
            self.ui_distupgrade_stack.set_visible_child_name("control")
            if self.distup_download_inprogress:
                self.ui_distupgrade_stack.set_visible_child_name("download")
                return

        GLib.idle_add(self.ui_controldistup_button.set_sensitive, False)

        GLib.idle_add(self.ui_distupgotoupdates_box.set_visible, False)
        GLib.idle_add(self.ui_controldistuperror_box.set_visible, False)

        upg_thread = threading.Thread(target=self.before_distupgradables_worker_thread, daemon=True)
        upg_thread.start()

    def before_distupgradables_worker_thread(self):
        rcbu = self.before_distupgradables_worker()
        GLib.idle_add(self.before_distupgradables_worker_thread_done, rcbu)

    def before_distupgradables_worker(self):
        return self.Package.required_changes_upgrade()

    def before_distupgradables_worker_thread_done(self, requireds):

        if requireds["changes_available"] and (requireds["to_install"] or requireds["to_upgrade"]):
            print("changes_available:{}, to_install:{}, to_upgrade:{}".format(
                requireds["changes_available"], requireds["to_install"], requireds["to_upgrade"]))

            GLib.idle_add(self.ui_distupgotoupdates_box.set_visible, True)
            GLib.idle_add(self.ui_controldistup_button.set_sensitive, True)

        else:
            self.control_distup_messages = ""

            command = ["/usr/bin/pkexec", os.path.dirname(os.path.abspath(__file__)) + "/SysActions.py",
                       "controldistupgrade", self.dist_new_sources]

            self.startControlDistUpgradeProcess(command)
            self.upgrade_inprogress = True
            self.ui_distupgradecontrol_spinner.start()
            GLib.idle_add(self.ui_controldistup_button.set_sensitive, False)
            GLib.idle_add(self.ui_controldistuperror_box.set_visible, False)

    def on_ui_distuptodown_button_clicked(self, button):
        command = ["/usr/bin/pkexec", os.path.dirname(os.path.abspath(__file__)) + "/SysActions.py",
                   "downupgrade", self.dist_new_sources]

        # self.startDownDistUpgradeProcess(command)

        if self.distupgrade_vteterm:
            self.distupgrade_vteterm.reset(True, True)

        self.ui_distupgradevte_sw.set_visible(True)

        self.ui_distupdowninfo_label.set_markup("<b>{}</b>".format(_("Packages are downloading, please wait.")))

        self.ui_distupdowninfo_spinner.start()
        self.ui_distupdowninfo_spinner.set_visible(True)

        self.ui_distuptoinstall_button.set_sensitive(False)
        self.ui_distuptoinstall_button.set_visible(False)

        self.ui_distuptodownretry_button.set_visible(False)
        self.ui_distuptodownretry_button.set_sensitive(False)

        self.ui_distupgrade_stack.set_visible_child_name("download")

        self.distupgrade_vte_start_process(command)
        self.upgrade_inprogress = True
        self.distup_download_inprogress = True

    def on_ui_distuptoinstall_button_clicked(self, button):
        self.ui_distupgrade_lastinfo_box.set_visible(False)
        self.ui_distupgrade_lastinfo_spinner.stop()
        self.ui_distupgrade_defaults_button.set_visible(not self.ui_distupgradenewconf_radiobutton.get_active())
        self.ui_distupgrade_stack.set_visible_child_name("install")

    def on_ui_distupgrade_button_clicked(self, button):
        self.upgrade_inprogress = True

        self.ui_distupgrade_buttonbox.set_sensitive(False)
        self.ui_distuptoinstallcancel_button.set_sensitive(False)

        start, end = self.ui_distupgrade_textview.get_buffer().get_bounds()
        self.ui_distupgrade_textview.get_buffer().delete(start, end)

        ask_conf = ""
        if self.ui_distupgradenewconf_radiobutton.get_active():
            ask_conf = "--force-confnew"
        elif self.ui_distupgradeoldconf_radiobutton.get_active():
            ask_conf = "--force-confold"

        print("dpkg_conf: {}".format(ask_conf))

        command = ["/usr/bin/pkexec", os.path.dirname(os.path.abspath(__file__)) + "/SysActions.py",
                   "distupgradeoffline", self.dist_new_sources, ask_conf]

        self.startDistUpgradeProcess(command)

        self.ui_distupgrade_lastinfo_box.set_visible(True)
        self.ui_distupgrade_lastinfo_spinner.start()
        self.ui_distupgradetextview_box.set_visible(True)

    def on_ui_distupgradeconf_radiobutton_toggled(self, button):
        self.ui_distupgrade_defaults_button.set_visible(not self.ui_distupgradenewconf_radiobutton.get_active())

    def on_ui_distupgrade_defaults_button_clicked(self, button):
        self.ui_distupgradenewconf_radiobutton.set_active(True)

    def on_ui_distupgradeoptions_button_clicked(self, button):
        self.ui_distupgradeoptions_popover.popup()
        self.ui_distupgrade_defaults_button.set_visible(not self.ui_distupgradenewconf_radiobutton.get_active())

    def on_ui_upgradeinfobusyok_button_clicked(self, button):
        self.ui_upgradeinfobusy_box.set_visible(False)

    def on_ui_homepage_button_clicked(self, button):
        if self.ui_main_stack.get_visible_child_name() == "clean" or \
                self.ui_main_stack.get_visible_child_name() == "settings" or \
                self.ui_main_stack.get_visible_child_name() == "distupgrade":
            self.ui_menusettings_image.set_from_icon_name("preferences-system-symbolic", Gtk.IconSize.BUTTON)
            self.ui_menusettings_label.set_text(_("Settings"))
            self.ui_menudistupgrade_image.set_from_icon_name("go-up-symbolic", Gtk.IconSize.BUTTON)
            self.ui_menudistupgrade_label.set_text(_("Version Upgrade"))
            self.ui_headerbar_messageimage.set_from_icon_name("mail-unread-symbolic", Gtk.IconSize.BUTTON)
            self.ui_main_stack.set_visible_child_name(self.laststack)

    def on_ui_menuabout_button_clicked(self, button):
        self.ui_menu_popover.popdown()
        self.about_dialog.run()
        self.about_dialog.hide()

    def on_ui_menusettings_button_clicked(self, button):

        if self.ui_main_stack.get_visible_child_name() != "clean" and \
                self.ui_main_stack.get_visible_child_name() != "settings" and \
                self.ui_main_stack.get_visible_child_name() != "distupgrade":
            self.laststack = self.ui_main_stack.get_visible_child_name()

        if self.ui_main_stack.get_visible_child_name() == "settings":
            self.ui_menusettings_image.set_from_icon_name("preferences-system-symbolic", Gtk.IconSize.BUTTON)
            self.ui_menusettings_label.set_text(_("Settings"))
            self.ui_main_stack.set_visible_child_name(self.laststack)
        else:
            self.ui_menusettings_image.set_from_icon_name("user-home-symbolic", Gtk.IconSize.BUTTON)
            self.ui_menusettings_label.set_text(_("Home Page"))

            self.ui_main_stack.set_visible_child_name("settings")

            self.ui_menudistupgrade_image.set_from_icon_name("go-up-symbolic", Gtk.IconSize.BUTTON)
            self.ui_menudistupgrade_label.set_text(_("Version Upgrade"))

            self.ui_headerbar_messageimage.set_from_icon_name("mail-unread-symbolic", Gtk.IconSize.BUTTON)

            self.set_settings_widgets()

        self.ui_menu_popover.popdown()

    def set_settings_widgets(self):
        interval = self.UserSettings.config_update_interval
        interval_combo = self.interval_to_combo(interval)
        if self.SystemSettings.config_update_interval is not None:
            interval = self.SystemSettings.config_update_interval
            interval_combo = self.interval_to_combo(interval)
            self.ui_updatefreq_combobox.set_sensitive(False)
            self.ui_updatefreq_spin.set_sensitive(False)

        if interval_combo is not None:
            self.ui_updatefreq_stack.set_visible_child_name("combo")
            self.ui_updatefreq_combobox.set_active(interval_combo)
        else:
            self.ui_updatefreq_stack.set_visible_child_name("spin")
            self.ui_updatefreq_spin.set_value(interval)

        self.ui_settingslastupdate_label.set_markup("{}".format(
            datetime.fromtimestamp(self.UserSettings.config_update_lastupdate)))

        update_selectable = self.UserSettings.config_update_selectable
        if self.SystemSettings.config_update_selectable is not None:
            update_selectable = self.SystemSettings.config_update_selectable
            self.ui_selectable_updates_switch.set_sensitive(False)
        self.ui_selectable_updates_switch.set_state(update_selectable)

        autostart = self.UserSettings.config_autostart
        if self.SystemSettings.config_autostart is not None:
            autostart = self.SystemSettings.config_autostart
            self.ui_autostart_switch.set_sensitive(False)
        self.ui_autostart_switch.set_state(autostart)

        notifications = self.UserSettings.config_notifications
        if self.SystemSettings.config_notifications is not None:
            notifications = self.SystemSettings.config_notifications
            self.ui_notifications_switch.set_sensitive(False)
        self.ui_notifications_switch.set_state(notifications)

        self.control_groups()

    def control_groups(self):
        try:
            self.user_groups = [g.gr_name for g in grp.getgrall() if self.UserSettings.user_name in g.gr_mem]
        except Exception as e:
            print("control_groups: {}".format(e))
            self.user_groups = []

        if self.user_groups:
            self.ui_passwordless_button.set_visible(True)
            if "pardus-update" in self.user_groups:
                self.ui_passwordless_button_label.set_label(_("Disable Passwordless Usage"))
            else:
                self.ui_passwordless_button_label.set_label(_("Enable Passwordless Usage"))
            self.ui_passwordless_button.set_sensitive(True)
        else:
            self.ui_passwordless_button.set_visible(False)

    def on_ui_passwordless_button_clicked(self, button):
        self.grouperrormessage = ""
        self.ui_passwordless_button.set_sensitive(False)
        if "pardus-update" in self.user_groups:
            command = ["/usr/bin/pkexec", os.path.dirname(os.path.abspath(__file__)) + "/Group.py", "del",
                       self.UserSettings.user_name]
        else:
            command = ["/usr/bin/pkexec", os.path.dirname(os.path.abspath(__file__)) + "/Group.py", "add",
                       self.UserSettings.user_name]
        self.start_group_process(command)

    def on_ui_menudistupgrade_button_clicked(self, button):
        self.ui_menu_popover.popdown()

        if self.ui_main_stack.get_visible_child_name() != "clean" and \
                self.ui_main_stack.get_visible_child_name() != "settings" and \
                self.ui_main_stack.get_visible_child_name() != "distupgrade":
            self.laststack = self.ui_main_stack.get_visible_child_name()

        if self.ui_main_stack.get_visible_child_name() == "distupgrade":
            self.ui_menudistupgrade_image.set_from_icon_name("go-up-symbolic", Gtk.IconSize.BUTTON)
            self.ui_menudistupgrade_label.set_text(_("Version Upgrade"))
            self.ui_main_stack.set_visible_child_name(self.laststack)
        else:

            GLib.idle_add(self.ui_distupgotoupdates_box.set_visible, False)
            GLib.idle_add(self.ui_controldistuperror_box.set_visible, False)

            self.ui_menudistupgrade_image.set_from_icon_name("user-home-symbolic", Gtk.IconSize.BUTTON)
            self.ui_menudistupgrade_label.set_text(_("Home Page"))

            self.ui_main_stack.set_visible_child_name("distupgrade")

            self.ui_menusettings_image.set_from_icon_name("preferences-system-symbolic", Gtk.IconSize.BUTTON)
            self.ui_menusettings_label.set_text(_("Settings"))

            self.ui_headerbar_messageimage.set_from_icon_name("mail-unread-symbolic", Gtk.IconSize.BUTTON)

    def on_ui_headerbar_messagebutton_clicked(self, button):
        self.ui_menu_popover.popdown()

        if self.ui_main_stack.get_visible_child_name() != "clean" and \
                self.ui_main_stack.get_visible_child_name() != "settings" and \
                self.ui_main_stack.get_visible_child_name() != "distupgrade":
            self.laststack = self.ui_main_stack.get_visible_child_name()

        if self.ui_main_stack.get_visible_child_name() == "clean":
            self.ui_headerbar_messageimage.set_from_icon_name("mail-unread-symbolic", Gtk.IconSize.BUTTON)
            self.ui_main_stack.set_visible_child_name(self.laststack)
        else:
            self.ui_headerbar_messageimage.set_from_icon_name("user-home-symbolic", Gtk.IconSize.BUTTON)
            self.ui_main_stack.set_visible_child_name("clean")

            self.ui_menusettings_image.set_from_icon_name("preferences-system-symbolic", Gtk.IconSize.BUTTON)
            self.ui_menusettings_label.set_text(_("Settings"))

            self.ui_menudistupgrade_image.set_from_icon_name("go-up-symbolic", Gtk.IconSize.BUTTON)
            self.ui_menudistupgrade_label.set_text(_("Version Upgrade"))

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
        if self.SystemSettings.config_update_interval is not None:
            return

        seconds = 86400
        if combo_box.get_active() == 0:  # Hourly
            seconds = 3600
        elif combo_box.get_active() == 1:  # Daily
            seconds = 86400
        elif combo_box.get_active() == 2:  # Weekly
            seconds = 604800
        elif combo_box.get_active() == 3:  # Never
            seconds = -1

        user_interval = self.UserSettings.config_update_interval
        if seconds != user_interval:
            self.UserSettings.writeConfig(seconds, self.UserSettings.config_update_lastupdate,
                                          self.UserSettings.config_update_selectable, self.UserSettings.config_autostart,
                                          self.UserSettings.config_notifications)
            self.user_settings()

            # update autoupdate timer
            if self.autoupdate_glibid:
                GLib.source_remove(self.autoupdate_glibid)
            # self.create_autoupdate_glibid()

            if self.UserSettings.config_update_interval == -1:  # never auto update
                return

            if not self.upgrade_inprogress and not self.update_inprogress:
                if self.UserSettings.config_update_lastupdate + self.UserSettings.config_update_interval - 10 <= int(
                        datetime.now().timestamp()):
                    print("started timed update check from on_ui_updatefreq_combobox_changed")
                    print("lu:{} inv:{} now:{}".format(self.UserSettings.config_update_lastupdate,
                                                       self.UserSettings.config_update_interval,
                                                       int(datetime.now().timestamp())))
                    self.start_aptupdate()
                else:
                    self.create_autoupdate_glibid()
            else:
                self.create_autoupdate_glibid()

    def on_ui_updatefreq_spin_value_changed(self, spin_button):
        if self.SystemSettings.config_update_interval is not None:
            return
        seconds = int(spin_button.get_value())
        user_interval = self.UserSettings.config_update_interval
        if seconds != user_interval:
            self.UserSettings.writeConfig(seconds, self.UserSettings.config_update_lastupdate,
                                          self.UserSettings.config_update_selectable, self.UserSettings.config_autostart,
                                          self.UserSettings.config_notifications)
            self.user_settings()

            # update autoupdate timer
            if self.autoupdate_glibid:
                GLib.source_remove(self.autoupdate_glibid)
            self.create_autoupdate_glibid()

    def on_ui_selectable_updates_switch_state_set(self, switch, state):
        if self.SystemSettings.config_update_selectable is not None:
            return

        user_selectable = self.UserSettings.config_update_selectable
        if state != user_selectable:
            self.UserSettings.writeConfig(self.UserSettings.config_update_interval,
                                          self.UserSettings.config_update_lastupdate, state,
                                          self.UserSettings.config_autostart,
                                          self.UserSettings.config_notifications)
            self.user_settings()
            if not state:
                self.user_keep_list.clear()
            self.control_required_changes()

    def on_ui_autostart_switch_state_set(self, switch, state):
        if self.SystemSettings.config_autostart is not None:
            return

        self.UserSettings.set_autostart(state)

        user_autostart = self.UserSettings.config_autostart
        if state != user_autostart:
            self.UserSettings.writeConfig(self.UserSettings.config_update_interval,
                                          self.UserSettings.config_update_lastupdate,
                                          self.UserSettings.config_update_selectable, state,
                                          self.UserSettings.config_notifications)
            self.user_settings()

    def on_ui_notifications_switch_state_set(self, switch, state):
        if self.SystemSettings.config_notifications is not None:
            return

        user_notifications = self.UserSettings.config_notifications
        if state != user_notifications:
            self.UserSettings.writeConfig(self.UserSettings.config_update_interval,
                                          self.UserSettings.config_update_lastupdate,
                                          self.UserSettings.config_update_selectable,
                                          self.UserSettings.config_autostart, state)
            self.user_settings()

    def on_ui_fix_button_clicked(self, button):
        self.ui_fix_stack.set_visible_child_name("info")

    def on_ui_fixaccept_button_clicked(self, button):
        if self.user_default_sources_list is None:
            ErrorDialog(_("Error"), "{}\n{}\n{}\n{}".format(_("Your system is not supported."),
                                                            self.user_distro_id, self.user_distro_version,
                                                            self.user_distro_codename))
            return
        command = ["/usr/bin/pkexec", os.path.dirname(os.path.abspath(__file__)) + "/SysActions.py", "fixsources",
                   self.user_default_sources_list, "1", "1", "1", "1"]
        self.ui_fix_stack.set_visible_child_name("main")
        self.ui_fix_button.set_sensitive(False)
        self.ui_fix_spinner.start()
        self.fix_vte_start_process(command)
        self.update_inprogress = True

    def on_ui_fixcancel_button_clicked(self, button):
        self.ui_fix_stack.set_visible_child_name("main")

    def on_ui_fixcompleted_button_clicked(self, button):
        self.ui_main_stack.set_visible_child_name("spinner")
        self.apt_update(force=True)

    def on_ui_upgradeinfofixdpkg_button_clicked(self, button):
        self.ui_main_stack.set_visible_child_name("dpkgconfigure")
        self.ui_dpkgconfigurefix_box.set_visible(True)
        self.ui_dpkgconfigureinfo_box.set_visible(False)
        self.ui_dpkgconfigurefix_button.set_sensitive(True)
        self.ui_dpkgconfigurefix_label.set_markup("<b>{}</b>".format(
            _("dpkg interrupt detected. Click the 'Fix' button or\n"
              "manually run 'sudo dpkg --configure -a' to fix the problem.")))
        self.on_ui_dpkgconfigurefix_button_clicked(None)

    def on_ui_dpkgconfigurefix_button_clicked(self, button):
        self.ui_dpkgconfigurefix_button.set_sensitive(False)

        self.ui_dpkgconfigureinfo_box.set_visible(True)

        self.ui_dpkgconfigureinfo_label.set_markup("<b>{}</b>".format(_("The process is in progress. Please wait...")))

        self.ui_dpkgconfigureinfo_spinner.start()
        self.ui_dpkgconfigureinfo_spinner.set_visible(True)

        self.ui_dpkgconfigureok_button.set_visible(False)

        command = ["/usr/bin/pkexec", os.path.dirname(os.path.abspath(__file__)) + "/SysActions.py", "dpkgconfigure"]

        if not self.dpkgconfiguring:
            self.dpkgconfigure_vte_start_process(command)
            self.dpkgconfiguring = True
            self.update_inprogress = True
        else:
            print("dpkgconfiguring in progress")

    def on_ui_dpkgconfigureok_button_clicked(self, button):
        self.ui_main_stack.set_visible_child_name("spinner")
        self.apt_update()

    def on_ui_conerror_tryfix_button_clicked(self, button):
        self.on_menu_settings_app()
        self.on_ui_fix_sources_button_clicked(button=None)
        self.ui_settingsapt_stack.set_visible_child_name("defaultsources")

    def on_ui_conerror_info_button_clicked(self, button):
        self.ui_conerror_info_popover.popup()

    def on_ui_quitdialogyes_button_clicked(self, button):
        self.ui_quit_dialog.hide()
        if self.about_dialog.is_visible():
            self.about_dialog.hide()
        self.main_window.get_application().quit()

    def on_ui_quitdialogno_button_clicked(self, button):
        self.ui_quit_dialog.hide()

    def on_ui_main_window_delete_event(self, widget, event):
        self.main_window.hide()
        self.item_sh_app.set_label(_("Show App"))
        return True

    def on_menu_quit_app(self, *args):
        if self.upgrade_inprogress:
            self.ui_quit_dialog.run()
            self.ui_quit_dialog.hide()
        else:
            if self.about_dialog.is_visible():
                self.about_dialog.hide()
            self.main_window.get_application().quit()

    def monitoring(self):
        self.aptlist_directory = "/var/lib/apt/lists"
        self.dpkg_status_path = "/var/lib/dpkg/status"

        self.apt_dir = Gio.file_new_for_path(self.aptlist_directory)
        self.apt_monitor = self.apt_dir.monitor_directory(0, None)
        self.apt_monitor.connect('changed', self.on_apt_changed)

        self.dpkg_status_file = Gio.file_new_for_path(self.dpkg_status_path)
        self.dpkg_monitor = self.dpkg_status_file.monitor_file(0, None)
        self.dpkg_monitor.connect('changed', self.on_apt_changed)

    def on_apt_changed(self, file_monitor, file, other_file, event_type):
        print("{} file changed, update_inprogress: {}, upgrade_inprogress: {}, auto_upgrade_inprogress {}".format(
            file.get_path(), self.update_inprogress, self.upgrade_inprogress, self.auto_upgrade_inprogress))
        if not self.update_inprogress and not self.upgrade_inprogress and not self.auto_upgrade_inprogress:
            print("Triggering control_upgradables from monitoring {}".format(file.get_path()))
            if self.autoupdate_monitoring_glibid:
                GLib.source_remove(self.autoupdate_monitoring_glibid)
            self.autoupdate_monitoring_glibid = GLib.timeout_add_seconds(
                self.monitoring_timeoutadd_sec, self.control_upgradables)

    def control_upgradables(self):
        print("STARTING control_upgradables from monitoring")
        if self.autoupdate_monitoring_glibid:
            GLib.source_remove(self.autoupdate_monitoring_glibid)
        if self.Package.updatecache():
            self.isbroken = False
        else:
            self.isbroken = True
        self.control_update_residual_message_section()
        self.set_upgradable_page_and_notify()

    def clear_upgrade_listboxes(self):
        self.ui_upgradable_listbox.foreach(lambda child: self.ui_upgradable_listbox.remove(child))
        self.ui_newly_listbox.foreach(lambda child: self.ui_newly_listbox.remove(child))
        self.ui_removable_listbox.foreach(lambda child: self.ui_removable_listbox.remove(child))
        self.ui_kept_listbox.foreach(lambda child: self.ui_kept_listbox.remove(child))

    def control_required_changes(self):
        self.UserSettings.set_user_keeps_file(self.user_keep_list)
        print("user_keep_list: {}".format(self.user_keep_list))
        def start_thread():
            GLib.idle_add(self.clear_upgrade_listboxes)

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

            upg_thread = threading.Thread(target=self.upgradables_worker_thread, daemon=True)
            upg_thread.start()

        start_thread()

    def upgradables_worker_thread(self):
        rcu = self.rcu_worker()
        GLib.idle_add(self.on_upgradables_worker_done, rcu)

    def rcu_worker(self, keep_list=None):
        return self.Package.required_changes_upgrade(keep_list=self.user_keep_list)

    def on_upgradables_worker_done(self, requireds):
        update_selectable_state = self.UserSettings.config_update_selectable
        if self.SystemSettings.config_update_selectable is not None:
            update_selectable_state = self.SystemSettings.config_update_selectable
        def add_to_listbox(iconname, package, listbox, pagename, check_active=True, check_sensitive=True):
            if update_selectable_state:
                checkbutton = Gtk.CheckButton.new()
                checkbutton.set_active(check_active)
                checkbutton.set_sensitive(check_sensitive)
                checkbutton.name = package
                checkbutton.connect("toggled", self.on_checkbutton_toggled)
            image = Gtk.Image.new_from_icon_name(iconname, Gtk.IconSize.BUTTON)
            name = Gtk.Label.new()
            name.set_markup("<b>{}</b>".format(GLib.markup_escape_text(package, -1)))
            name.set_ellipsize(Pango.EllipsizeMode.END)
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

            if update_selectable_state:
                box.pack_start(checkbutton, False, True, 5)

            box.pack_start(image, False, True, 5)
            box.pack_start(box1, False, True, 5)
            GLib.idle_add(listbox.insert, box, -1)
            GLib.idle_add(self.ui_upgrade_buttonbox.set_sensitive, True)
            GLib.idle_add(pagename.set_visible, True)

        if requireds["to_upgrade"] and requireds["to_upgrade"] is not None:
            for package in requireds["to_upgrade"]:
                add_to_listbox("go-up-symbolic", package, self.ui_upgradable_listbox, self.ui_upgradable_sw)

        if requireds["to_install"] and requireds["to_install"] is not None:
            for package in requireds["to_install"]:
                add_to_listbox("list-add-symbolic", package, self.ui_newly_listbox, self.ui_newly_sw,
                               check_sensitive=False)

        if requireds["to_delete"] and requireds["to_delete"] is not None:
            for package in requireds["to_delete"]:
                add_to_listbox("list-remove-symbolic", package, self.ui_removable_listbox, self.ui_removable_sw,
                               check_sensitive=False)

        if requireds["to_keep"] and requireds["to_keep"] is not None:
            for package in requireds["to_keep"]:
                sensitive = True
                if update_selectable_state:
                    sensitive = package in self.user_keep_list
                add_to_listbox("view-grid-symbolic", package, self.ui_kept_listbox, self.ui_kept_sw,
                               check_active=False, check_sensitive=sensitive)

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
            GLib.idle_add(self.ui_upgradecount_label.set_markup, "{}".format(len(requireds["to_upgrade"])))
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

            if update_selectable_state and self.user_keep_list:
                button = Gtk.Button.new()
                button.set_label(_("Clear All Selections"))
                button.props.halign = Gtk.Align.CENTER
                button.props.valign = Gtk.Align.CENTER
                button.connect("clicked", self.on_clear_update_selectables)
                GLib.idle_add(self.ui_kept_listbox.insert, button, 0)
                GLib.idle_add(self.ui_kept_listbox.show_all)

        print("on_upgradables_worker_done")

    def on_clear_update_selectables(self, button):
        self.user_keep_list.clear()
        self.control_required_changes()

    def on_checkbutton_toggled(self, toggle_button):
        print("{} {}".format(toggle_button.name, toggle_button.get_active()))
        if toggle_button.get_active():
            if toggle_button.name in self.user_keep_list:
                self.user_keep_list.remove(toggle_button.name)
        else:
            if toggle_button.name not in self.user_keep_list:
                self.user_keep_list.append(toggle_button.name)

        self.control_required_changes()

    def on_ui_update_selectable_info_button_clicked(self, button):
        self.ui_update_selectable_info_popover.popup()

    def start_aptupdate(self):
        if not self.upgrade_inprogress and not self.update_inprogress:
            GLib.idle_add(self.indicator.set_icon, self.icon_inprogress)
            command = ["/usr/bin/pkexec", os.path.dirname(os.path.abspath(__file__)) + "/AutoAptUpdate.py"]
            self.startAptUpdateProcess(command)
            self.sources_err_count = 0
            self.sources_err_lines = ""
            self.update_inprogress = True
        else:
            print("apt_update: upgrade_inprogress | update_inprogress")
            if self.ui_main_stack.get_visible_child_name() == "spinner":
                self.ui_main_stack.set_visible_child_name("ok")

    def update_lastcheck_labels(self):
        self.ui_settingslastupdate_label.set_markup("{}".format(
            datetime.fromtimestamp(self.UserSettings.config_update_lastupdate)))

        self.item_lastcheck.set_label("{}: {}".format(_("Last Check"),
                                                      datetime.fromtimestamp(self.UserSettings.config_update_lastupdate)))

    def create_autoupdate_glibid(self):
        interval = self.UserSettings.config_update_interval
        if self.SystemSettings.config_update_interval is not None:
            interval = self.SystemSettings.config_update_interval
        if interval != -1:
            self.autoupdate_glibid = GLib.timeout_add_seconds(interval, self.apt_update)

    def create_autoupgrade_glibid(self):
        interval = self.SystemSettings.config_upgrade_interval
        if interval != -1:
            if self.autoupgrade_glibid:
                GLib.source_remove(self.autoupgrade_glibid)
            self.autoupgrade_glibid = GLib.timeout_add_seconds(interval, self.apt_upgrade)

    def set_upgradable_page_and_notify(self):
        if self.isbroken:
            self.ui_main_stack.set_visible_child_name("fix")
            self.indicator.set_icon(self.icon_error)
            self.item_systemstatus.set_sensitive(False if not self.pargnome23 else True)
            self.item_systemstatus.set_label(_("System is Broken"))
            GLib.idle_add(self.ui_headerbar_messagebutton.set_visible, False)
        else:
            if self.sources_err_count == 0:
                upgradable = self.Package.upgradable()
                if upgradable:
                    self.control_required_changes()
                    if self.ui_main_stack.get_visible_child_name() == "spinner" or \
                            self.ui_main_stack.get_visible_child_name() == "ok":
                        self.ui_main_stack.set_visible_child_name("updateinfo")
                        self.ui_headerbar_messageimage.set_from_icon_name("mail-unread-symbolic", Gtk.IconSize.BUTTON)
                    if self.ui_main_stack.get_visible_child_name() == "upgrade" and not self.upgrade_inprogress:
                        self.ui_main_stack.set_visible_child_name("updateinfo")
                        self.ui_headerbar_messageimage.set_from_icon_name("mail-unread-symbolic", Gtk.IconSize.BUTTON)

                    notification = Notification(summary=_("Software Update"),
                                                body=_("There are {} software updates available.").format(len(upgradable))
                                                if len(upgradable) >= 1 else
                                                _("There is {} software update available.").format(len(upgradable)),
                                                icon=self.icon_available, appid=self.Application.get_application_id())
                    notification_state = self.UserSettings.config_notifications
                    if self.SystemSettings.config_notifications is not None:
                        notification_state = self.SystemSettings.config_notifications
                    GLib.idle_add(notification.show, notification_state)
                else:
                    if self.ui_main_stack.get_visible_child_name() != "distupgrade":
                        self.ui_main_stack.set_visible_child_name("ok")
                self.update_indicator_updates_labels(upgradable)
            else:
                if self.ui_main_stack.get_visible_child_name() != "distupgrade":
                    self.ui_main_stack.set_visible_child_name("conerror")
                self.indicator.set_icon(self.icon_error)
                self.item_systemstatus.set_sensitive(False if not self.pargnome23 else True)
                self.item_systemstatus.set_label(_("Repository Connection Error"))

        if self.autoupgrade_enabled:
            self.apt_upgrade()

    def control_update_residual_message_section(self):
        residual = self.Package.residual()
        autoremovable = self.Package.autoremovable()
        if residual or autoremovable:
            GLib.idle_add(self.ui_headerbar_messagebutton.set_visible, True)
            GLib.idle_add(self.ui_headerbar_messagebutton.set_tooltip_text, _("You have removable residual packages."))
            GLib.idle_add(self.ui_autoremovable_box.set_visible, autoremovable)
            GLib.idle_add(self.ui_residual_box.set_visible, residual)
            self.ui_autoremovable_textview.get_buffer().set_text("\n".join(autoremovable))
            self.ui_residual_textview.get_buffer().set_text("\n".join(residual))
            if self.ui_main_stack.get_visible_child_name() != "clean":
                self.ui_headerbar_messageimage.set_from_icon_name("mail-unread-symbolic", Gtk.IconSize.BUTTON)
        else:
            GLib.idle_add(self.ui_headerbar_messagebutton.set_visible, False)

    def update_indicator_updates_labels(self, upgradable):
        updates = _("System is Up to Date")
        if upgradable:
            if len(upgradable) > 1:
                updates = _("{} Updates Pending").format(len(upgradable))
            else:
                updates = _("{} Update Pending").format(len(upgradable))
            self.item_systemstatus.set_sensitive(True)
            self.item_systemstatus.set_label(updates)
            self.indicator.set_icon(self.icon_available)
        else:
            self.item_systemstatus.set_sensitive(False if not self.pargnome23 else True)
            self.item_systemstatus.set_label(updates)
            self.indicator.set_icon(self.icon_normal)

    def clear_distupgrade_listboxes(self):
        self.ui_distupgradable_listbox.foreach(lambda child: self.ui_distupgradable_listbox.remove(child))
        self.ui_distnewly_listbox.foreach(lambda child: self.ui_distnewly_listbox.remove(child))
        self.ui_distremovable_listbox.foreach(lambda child: self.ui_distremovable_listbox.remove(child))
        self.ui_distkept_listbox.foreach(lambda child: self.ui_distkept_listbox.remove(child))

    def start_aptupgrade(self):
        if not self.upgrade_inprogress:
            GLib.idle_add(self.indicator.set_icon, self.icon_inprogress)
            command = ["/usr/bin/pkexec", os.path.dirname(os.path.abspath(__file__)) + "/AutoAptUpgrade.py"]
            self.startAptUpgradeProcess(command)
            self.auto_upgrade_inprogress = True

            notification = Notification(summary=_("Pardus Update"),
                                    body=_("Automatic upgrade started in the background."),
                                    icon=self.icon_inprogress, appid=self.Application.get_application_id(),
                                    only_info=True)
            notification_state = self.UserSettings.config_notifications
            if self.SystemSettings.config_notifications is not None:
                notification_state = self.SystemSettings.config_notifications
            GLib.idle_add(notification.show, notification_state)

        else:
            print("auto_apt_upgrade: update_inprogress: {}, upgrade_inprogress: {}".format(self.update_inprogress,
                                                                                      self.upgrade_inprogress))
            if self.ui_main_stack.get_visible_child_name() == "spinner":
                self.ui_main_stack.set_visible_child_name("ok")

    def startControlDistUpgradeProcess(self, params):
        pid, stdin, stdout, stderr = GLib.spawn_async(params, flags=GLib.SpawnFlags.DO_NOT_REAP_CHILD,
                                                      standard_output=True, standard_error=True)
        GLib.io_add_watch(GLib.IOChannel(stdout), GLib.IO_IN | GLib.IO_HUP, self.onControlDistUpgradeStdout)
        GLib.io_add_watch(GLib.IOChannel(stderr), GLib.IO_IN | GLib.IO_HUP, self.onControlDistUpgradeStderr)
        GLib.child_watch_add(GLib.PRIORITY_DEFAULT, pid, self.onControlDistUpgradeExit)

        return pid

    def onControlDistUpgradeStdout(self, source, condition):
        if condition == GLib.IO_HUP:
            return False
        line = source.readline()
        print("onControlDistUpgradeStdout: {}".format(line))
        self.control_distup_messages += "{}".format(line)
        return True

    def onControlDistUpgradeStderr(self, source, condition):
        if condition == GLib.IO_HUP:
            return False
        line = source.readline()
        print("onControlDistUpgradeStderr: {}".format(line))
        self.control_distup_messages += "{}".format(line)
        return True

    def onControlDistUpgradeExit(self, pid, status):
        self.upgrade_inprogress = False

        self.ui_distupgradecontrol_spinner.stop()
        self.ui_controldistup_button.set_sensitive(True)
        self.ui_distuptodown_button.set_label(_("Upgrade to {}").format(self.dist_new_version))

        self.ui_controldistuperror_box.set_visible(False)

        print("onControlDistUpgradeExit: {}".format(status))
        self.control_distup_messages += "ControlDistUpgrade Exit Code: {}".format(status)

        if status != 0:
            print("onControlDistUpgradeExit exited with error")
            self.ui_controldistuperror_label.set_text("{}".format(self.control_distup_messages))
            self.ui_controldistuperror_box.set_visible(True)
            return

        ### read all changes from a file and set ui

        rc_file_path = os.path.dirname(os.path.abspath(__file__)) + "/../required_changes_for_upgrade.json"
        rc_file = open(rc_file_path, "r")

        if os.path.isfile(rc_file_path):
            requireds = json.load(rc_file)

            GLib.idle_add(self.clear_distupgrade_listboxes)

            self.ui_distupgradable_sw.set_visible(False)
            self.ui_distnewly_sw.set_visible(False)
            self.ui_distremovable_sw.set_visible(False)
            self.ui_distkept_sw.set_visible(False)
            self.ui_distdownloadsize_box.set_visible(False)
            self.ui_distinstallsize_box.set_visible(False)
            self.ui_distupgradecount_box.set_visible(False)
            self.ui_distnewlycount_box.set_visible(False)
            self.ui_distremovecount_box.set_visible(False)
            self.ui_distkeptcount_box.set_visible(False)

            def add_to_listbox(iconname, package, listbox, pagename):
                image = Gtk.Image.new_from_icon_name(iconname, Gtk.IconSize.BUTTON)
                name = Gtk.Label.new()
                name.set_markup("<b>{}</b>".format(GLib.markup_escape_text(package["name"], -1)))
                name.set_ellipsize(Pango.EllipsizeMode.END)
                name.props.halign = Gtk.Align.START

                summarylabel = Gtk.Label.new()
                summarylabel.set_markup(
                    "<small>{}</small>".format(GLib.markup_escape_text(package["summary"], -1)))
                summarylabel.set_ellipsize(Pango.EllipsizeMode.END)
                summarylabel.props.halign = Gtk.Align.START

                old_version = Gtk.Label.new()
                old_version.set_markup("<span size='x-small'>{}</span>".format(
                    GLib.markup_escape_text(package["oldversion"], -1)))
                old_version.set_ellipsize(Pango.EllipsizeMode.END)

                sep_label = Gtk.Label.new()
                sep_label.set_markup("<span size='x-small'>>></span>")

                new_version = Gtk.Label.new()
                new_version.set_markup("<span size='x-small'>{}</span>".format(
                    GLib.markup_escape_text(package["newversion"], -1)))
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
                GLib.idle_add(listbox.insert, box, -1)
                GLib.idle_add(pagename.set_visible, True)

            if requireds["to_upgrade"] and requireds["to_upgrade"] is not None:
                for package in requireds["to_upgrade"]:
                    add_to_listbox("go-up-symbolic", package, self.ui_distupgradable_listbox, self.ui_distupgradable_sw)

            if requireds["to_install"] and requireds["to_install"] is not None:
                for package in requireds["to_install"]:
                    add_to_listbox("list-add-symbolic", package, self.ui_distnewly_listbox, self.ui_distnewly_sw)

            if requireds["to_delete"] and requireds["to_delete"] is not None:
                for package in requireds["to_delete"]:
                    add_to_listbox("list-remove-symbolic", package, self.ui_distremovable_listbox,
                                   self.ui_distremovable_sw)

            if requireds["to_keep"] and requireds["to_keep"] is not None:
                for package in requireds["to_keep"]:
                    add_to_listbox("view-grid-symbolic", package, self.ui_distkept_listbox, self.ui_distkept_sw)

            GLib.idle_add(self.ui_distupgradable_listbox.show_all)
            GLib.idle_add(self.ui_distnewly_listbox.show_all)
            GLib.idle_add(self.ui_distremovable_listbox.show_all)
            GLib.idle_add(self.ui_distkept_listbox.show_all)

            if requireds["download_size"] and requireds["download_size"] is not None:
                GLib.idle_add(self.ui_distdownloadsize_label.set_markup,
                              "{}".format(self.Package.beauty_size(requireds["download_size"])))
                GLib.idle_add(self.ui_distdownloadsize_box.set_visible, True)

            if requireds["install_size"] and requireds["install_size"] is not None and requireds["install_size"] > 0:
                GLib.idle_add(self.ui_distinstallsize_label.set_markup,
                              "{}".format(self.Package.beauty_size(requireds["install_size"])))
                GLib.idle_add(self.ui_distinstallsize_box.set_visible, True)

            if requireds["to_upgrade"] and requireds["to_upgrade"] is not None:
                GLib.idle_add(self.ui_distupgradecount_label.set_markup,
                              "{}".format(len(requireds["to_upgrade"])))
                GLib.idle_add(self.ui_distupgradecount_box.set_visible, True)

            if requireds["to_install"] and requireds["to_install"] is not None:
                GLib.idle_add(self.ui_distnewlycount_label.set_markup, "{}".format(len(requireds["to_install"])))
                GLib.idle_add(self.ui_distnewlycount_box.set_visible, True)

            if requireds["to_delete"] and requireds["to_delete"] is not None:
                GLib.idle_add(self.ui_distremovecount_label.set_markup, "{}".format(len(requireds["to_delete"])))
                GLib.idle_add(self.ui_distremovecount_box.set_visible, True)

            if requireds["to_keep"] and requireds["to_keep"] is not None:
                GLib.idle_add(self.ui_distkeptcount_label.set_markup, "{}".format(len(requireds["to_keep"])))
                GLib.idle_add(self.ui_distkeptcount_box.set_visible, True)

            root_info = self.get_file_info("/")

            tolerance = 2000000000  # 2 GB
            if (requireds["download_size"] + requireds["install_size"] + tolerance) > int(root_info['free']):

                self.ui_rootfree_label.set_label(f"{self.Package.beauty_size(int(root_info['free']))}")
                self.ui_roottotal_label.set_label(f"{self.Package.beauty_size(int(root_info['total']))}")
                self.ui_rootusage_progressbar.set_fraction(root_info["usage_percent"])

                self.ui_distrequireddiskinfo_label.set_markup("{}: <b>{}</b>".format(
                    _("Total Required Size"),
                    self.Package.beauty_size(requireds["download_size"] + requireds["install_size"] + tolerance)))

                GLib.idle_add(self.ui_distuptodown_button.set_sensitive, False)
                GLib.idle_add(self.ui_rootdisk_box.set_visible, True)
            else:
                GLib.idle_add(self.ui_distuptodown_button.set_sensitive, True)
                GLib.idle_add(self.ui_rootdisk_box.set_visible, False)

            self.ui_distupgrade_stack.set_visible_child_name("distupdateinfo")

        else:
            print("{} not exists".format(rc_file_path))

    def get_file_info(self, file):
        process = subprocess.check_output(
            f"df '{file}' -B1 -T | awk 'NR==1 {{next}} {{print $1,$2,$3,$4,$5,$7; exit}}'", shell=True)
        if len(process.decode("utf-8").strip().split(" ")) == 6:
            keys = ["device", "fstype", "total", "usage", "free", "mountpoint"]
            obj = dict(zip(keys, process.decode("utf-8").strip().split(" ")))
            try:
                obj["usage_percent"] = (int(obj['total']) - int(obj['free'])) / int(obj['total'])
            except:
                obj["usage_percent"] = 0
            try:
                obj["free_percent"] = int(obj['free']) / int(obj['total'])
            except:
                obj["free_percent"] = 0
        else:
            obj = {"device": "", "fstype": "", "total": 0, "usage": 0, "free": 0, "mountpoint": "",
                   "usage_percent": 0, "free_percent": 0}

        print(obj)
        return obj

    def startDistUpgradeProcess(self, params):
        pid, stdin, stdout, stderr = GLib.spawn_async(params, flags=GLib.SpawnFlags.DO_NOT_REAP_CHILD,
                                                      standard_output=True, standard_error=True)
        GLib.io_add_watch(GLib.IOChannel(stdout), GLib.IO_IN | GLib.IO_HUP, self.onDistUpgradeStdout)
        GLib.io_add_watch(GLib.IOChannel(stderr), GLib.IO_IN | GLib.IO_HUP, self.onDistUpgradeStderr)
        GLib.child_watch_add(GLib.PRIORITY_DEFAULT, pid, self.onDistUpgradeExit)

        return pid

    def onDistUpgradeStdout(self, source, condition):
        if condition == GLib.IO_HUP:
            return False
        line = "{}".format(source.readline())
        print("onDistUpgradeStdout: {}".format(line))

        self.ui_distupgrade_textview.get_buffer().insert(self.ui_distupgrade_textview.get_buffer().get_end_iter(), line)

        text_mark_end = self.ui_distupgrade_textview.get_buffer().create_mark(
            "", self.ui_distupgrade_textview.get_buffer().get_end_iter(), False)
        self.ui_distupgrade_textview.scroll_to_mark(text_mark_end, 0, False, 0, 0)

        return True

    def onDistUpgradeStderr(self, source, condition):
        if condition == GLib.IO_HUP:
            return False
        line = "{}".format(source.readline())
        print("onDistUpgradeStderr: {}".format(line))

        self.ui_distupgrade_textview.get_buffer().insert(self.ui_distupgrade_textview.get_buffer().get_end_iter(), line)

        text_mark_end = self.ui_distupgrade_textview.get_buffer().create_mark(
            "", self.ui_distupgrade_textview.get_buffer().get_end_iter(), False)
        self.ui_distupgrade_textview.scroll_to_mark(text_mark_end, 0, False, 0, 0)

        return True

    def onDistUpgradeExit(self, pid, status):
        print("onDistUpgradeExit: {}".format(status))
        self.upgrade_inprogress = False
        self.ui_distupgrade_lastinfo_box.set_visible(False)
        self.ui_distupgrade_lastinfo_spinner.stop()
        self.ui_distupgrade_buttonbox.set_sensitive(True)
        self.ui_distuptoinstallcancel_button.set_sensitive(True)

        self.ui_distupgrade_textview.get_buffer().insert(
            self.ui_distupgrade_textview.get_buffer().get_end_iter(), "exit code: {}".format(status))

        text_mark_end = self.ui_distupgrade_textview.get_buffer().create_mark(
            "", self.ui_distupgrade_textview.get_buffer().get_end_iter(), False)
        self.ui_distupgrade_textview.scroll_to_mark(text_mark_end, 0, False, 0, 0)

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
        self.sources_err_lines += line
        if "Err:" in line:
            self.sources_err_count += 1
        return True

    def onAptUpdateProcessStderr(self, source, condition):
        if condition == GLib.IO_HUP:
            return False
        line = source.readline()
        self.sources_err_lines += line
        print("onAptUpdateProcessStderr: {}".format(line))
        if "Err:" in line:
            self.sources_err_count += 1
        return True

    def onAptUpdateProcessExit(self, pid, status):
        print("onAptUpdateProcessExit: {}".format(status))
        self.Package.updatecache()
        if status == 0:
            if self.sources_err_count == 0:
                try:
                    timestamp = int(datetime.now().timestamp())
                except Exception as e:
                    print("timestamp Error: {}".format(e))
                    timestamp = 0

                self.UserSettings.writeConfig(self.UserSettings.config_update_interval, timestamp,
                                              self.UserSettings.config_update_selectable,
                                              self.UserSettings.config_autostart, self.UserSettings.config_notifications)
                self.user_settings()
                self.update_lastcheck_labels()
                self.control_update_residual_message_section()
                self.create_autoupdate_glibid()
                self.set_upgradable_page_and_notify()

                if self.SystemSettings.config_update_interval is not None:
                    print("SystemSettings.config_update_lastupdate writed")
                    command = ["/usr/bin/pkexec", os.path.dirname(os.path.abspath(__file__)) + "/SystemSettingsWrite.py",
                               "write", "lastupdate", "{}".format(timestamp)]
                    subprocess.run(command)
            else:
                print("There is an error in the repository connections.")
                self.set_upgradable_page_and_notify()
                self.ui_conerror_info_label.set_text(self.sources_err_lines)
        else:
            self.indicator.set_icon(self.icon_error)

        self.update_inprogress = False
        print("update in progress set to " + str(self.update_inprogress))

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

        if self.upgrade_vteterm:
            self.upgrade_vteterm.get_parent().remove(self.upgrade_vteterm)

        self.upgrade_vteterm = Vte.Terminal()
        self.update_vte_color(self.upgrade_vteterm)
        self.upgrade_vteterm.set_scrollback_lines(-1)
        upgrade_vte_menu = Gtk.Menu()
        upgrade_vte_menu_items = Gtk.MenuItem(label=_("Copy selected text"))
        upgrade_vte_menu.append(upgrade_vte_menu_items)
        upgrade_vte_menu_items.connect("activate", self.upgrade_vte_menu_action, self.upgrade_vteterm)
        upgrade_vte_menu_items.show()
        self.upgrade_vteterm.connect_object("event", self.upgrade_vte_event, upgrade_vte_menu)
        self.ui_upgradevte_sw.add(self.upgrade_vteterm)
        self.upgrade_vteterm.show_all()

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

        self.ui_upgradeinfo_spinner.stop()
        self.ui_upgradeinfo_spinner.set_visible(False)
        self.ui_upgradeinfobusy_box.set_visible(False)
        GLib.idle_add(self.ui_upgradeinfofixdpkg_button.set_visible, False)
        GLib.idle_add(self.ui_upgradeinfook_button.set_visible, True)

        if status == 32256:  # operation cancelled | Request dismissed
            if self.clean_residuals_clicked:
                self.ui_main_stack.set_visible_child_name("clean")
            else:
                self.ui_main_stack.set_visible_child_name("updateinfo")
        elif status == 2816:  # dpkg lock error
            self.ui_upgradeinfo_label.set_markup("<span color='red'><b>{}</b></span>".format(
                _("Only one software management tool is allowed to run at the same time.\n"
                  "Please close the other application e.g. 'Update Manager', 'aptitude' or 'Synaptic' first.")))
        elif status == 3072:  # dpkg interrupt error
            self.ui_upgradeinfo_label.set_markup("<span color='red'><b>{}</b></span>".format(
                _("dpkg interrupt detected. Click the 'Fix' button or\n"
                  "manually run 'sudo dpkg --configure -a' to fix the problem.")))
            GLib.idle_add(self.ui_upgradeinfofixdpkg_button.set_visible, True)
        else:
            self.Package.updatecache()
            GLib.idle_add(self.ui_upgradeinfo_label.set_markup, "<b>{}</b>".format(_("Process completed.")))

        self.update_indicator_updates_labels(self.Package.upgradable())

        self.upgrade_inprogress = False
        self.clean_residuals_clicked = False

    def fix_vte_event(self, widget, event):
        if event.type == Gdk.EventType.BUTTON_PRESS:
            if event.button.button == 3:
                widget.popup_for_device(None, None, None, None, None,
                                        event.button.button, event.time)
                return True
        return False

    def fix_vte_menu_action(self, widget, terminal):
        terminal.copy_clipboard()

    def fix_vte_start_process(self, command):
        if self.fix_vteterm:
            self.fix_vteterm.get_parent().remove(self.fix_vteterm)

        self.fix_vteterm = Vte.Terminal()
        self.update_vte_color(self.fix_vteterm)
        self.fix_vteterm.set_scrollback_lines(-1)
        fix_vte_menu = Gtk.Menu()
        fix_vte_menu_items = Gtk.MenuItem(label=_("Copy selected text"))
        fix_vte_menu.append(fix_vte_menu_items)
        fix_vte_menu_items.connect("activate", self.fix_vte_menu_action, self.fix_vteterm)
        fix_vte_menu_items.show()
        self.fix_vteterm.connect_object("event", self.fix_vte_event, fix_vte_menu)
        self.ui_fixvte_sw.add(self.fix_vteterm)
        self.fix_vteterm.show_all()

        pty = Vte.Pty.new_sync(Vte.PtyFlags.DEFAULT)
        self.fix_vteterm.set_pty(pty)
        try:
            self.fix_vteterm.spawn_async(
                Vte.PtyFlags.DEFAULT,
                os.environ['HOME'],
                command,
                None,
                GLib.SpawnFlags.DO_NOT_REAP_CHILD,
                None,
                None,
                -1,
                None,
                self.fix_vte_create_spawn_callback,
                None
            )
        except Exception as e:
            # old version VTE doesn't have spawn_async so use spawn_sync
            print("{}".format(e))
            self.fix_vteterm.connect("child-exited", self.fix_vte_on_done)
            self.fix_vteterm.spawn_sync(
                Vte.PtyFlags.DEFAULT,
                os.environ['HOME'],
                command,
                [],
                GLib.SpawnFlags.DO_NOT_REAP_CHILD,
                None,
                None,
            )

    def fix_vte_create_spawn_callback(self, terminal, pid, error, userdata):
        self.fix_vteterm.connect("child-exited", self.fix_vte_on_done)

    def fix_vte_on_done(self, terminal, status):
        print("fix_vte_on_done status: {}".format(status))
        self.ui_fix_spinner.stop()
        self.ui_fix_button.set_sensitive(True)
        if status == 0:
            self.Package = Package()
            if self.Package.updatecache():
                self.ui_fix_stack.set_visible_child_name("done")
                self.isbroken = False
                self.indicator.set_icon(self.icon_normal)
            else:
                self.ui_fix_stack.set_visible_child_name("error")
                self.isbroken = True
                print("Error while updating cache on fix_vte_on_done")
        self.update_inprogress = False

    def distupgrade_vte_event(self, widget, event):
        if event.type == Gdk.EventType.BUTTON_PRESS:
            if event.button.button == 3:
                widget.popup_for_device(None, None, None, None, None,
                                        event.button.button, event.time)
                return True
        return False

    def distupgrade_vte_menu_action(self, widget, terminal):
        terminal.copy_clipboard()

    def distupgrade_vte_start_process(self, command):

        if self.distupgrade_vteterm:
            self.distupgrade_vteterm.get_parent().remove(self.distupgrade_vteterm)

        self.distupgrade_vteterm = Vte.Terminal()
        self.distupgrade_vteterm.set_scrollback_lines(-1)
        distupgrade_vte_menu = Gtk.Menu()
        distupgrade_vte_menu_items = Gtk.MenuItem(label=_("Copy selected text"))
        distupgrade_vte_menu.append(distupgrade_vte_menu_items)
        distupgrade_vte_menu_items.connect("activate", self.distupgrade_vte_menu_action, self.distupgrade_vteterm)
        distupgrade_vte_menu_items.show()
        self.distupgrade_vteterm.connect_object("event", self.distupgrade_vte_event, distupgrade_vte_menu)
        self.ui_distupgradevte_sw.add(self.distupgrade_vteterm)
        self.distupgrade_vteterm.show_all()

        pty = Vte.Pty.new_sync(Vte.PtyFlags.DEFAULT)
        self.distupgrade_vteterm.set_pty(pty)
        try:
            self.distupgrade_vteterm.spawn_async(
                Vte.PtyFlags.DEFAULT,
                os.environ['HOME'],
                command,
                None,
                GLib.SpawnFlags.DO_NOT_REAP_CHILD,
                None,
                None,
                -1,
                None,
                self.distupgrade_vte_create_spawn_callback,
                None
            )
        except Exception as e:
            # old version VTE doesn't have spawn_async so use spawn_sync
            print("{}".format(e))
            self.distupgrade_vteterm.connect("child-exited", self.distupgrade_vte_on_done)
            self.distupgrade_vteterm.spawn_sync(
                Vte.PtyFlags.DEFAULT,
                os.environ['HOME'],
                command,
                [],
                GLib.SpawnFlags.DO_NOT_REAP_CHILD,
                None,
                None,
            )

    def distupgrade_vte_create_spawn_callback(self, terminal, pid, error, userdata):
        self.distupgrade_vteterm.connect("child-exited", self.distupgrade_vte_on_done)

    def distupgrade_vte_on_done(self, terminal, status):
        print("distupgrade_vte_on_done status: {}".format(status))
        if status == 32256:  # operation cancelled | Request dismissed
            self.ui_distupgrade_stack.set_visible_child_name("distupdateinfo")
        elif status == 0:
            print("down ok")
            self.ui_distupdowninfo_label.set_markup(
                "<b>{}</b>".format(_("The download is complete. You can continue.")))
            self.ui_distupdowninfo_spinner.stop()
            self.ui_distupdowninfo_spinner.set_visible(False)

            self.ui_distuptoinstall_button.set_visible(True)
            self.ui_distuptoinstall_button.set_sensitive(True)

            self.ui_distuptodownretry_button.set_visible(False)
            self.ui_distuptodownretry_button.set_sensitive(False)

            self.on_ui_distuptoinstall_button_clicked(button=None)

        else:
            self.ui_distupdowninfo_label.set_markup("<b>{}</b>".format(_("The download is not completed. Try again.")))
            self.ui_distupdowninfo_spinner.stop()
            self.ui_distupdowninfo_spinner.set_visible(False)

            self.ui_distuptoinstall_button.set_visible(False)
            self.ui_distuptoinstall_button.set_sensitive(False)

            self.ui_distuptodownretry_button.set_visible(True)
            self.ui_distuptodownretry_button.set_sensitive(True)

        self.upgrade_inprogress = False
        self.distup_download_inprogress = False

    def dpkgconfigure_vte_event(self, widget, event):
        if event.type == Gdk.EventType.BUTTON_PRESS:
            if event.button.button == 3:
                widget.popup_for_device(None, None, None, None, None,
                                        event.button.button, event.time)
                return True
        return False

    def dpkgconfigure_vte_menu_action(self, widget, terminal):
        terminal.copy_clipboard()

    def dpkgconfigure_vte_start_process(self, command):
        if self.dpkgconfigure_vteterm:
            self.dpkgconfigure_vteterm.get_parent().remove(self.dpkgconfigure_vteterm)

        self.dpkgconfigure_vteterm = Vte.Terminal()
        self.dpkgconfigure_vteterm.set_scrollback_lines(-1)
        dpkgconfigure_vte_menu = Gtk.Menu()
        dpkgconfigure_vte_menu_items = Gtk.MenuItem(label=_("Copy selected text"))
        dpkgconfigure_vte_menu.append(dpkgconfigure_vte_menu_items)
        dpkgconfigure_vte_menu_items.connect("activate", self.dpkgconfigure_vte_menu_action, self.dpkgconfigure_vteterm)
        dpkgconfigure_vte_menu_items.show()
        self.dpkgconfigure_vteterm.connect_object("event", self.dpkgconfigure_vte_event, dpkgconfigure_vte_menu)
        self.ui_dpkgconfigurevte_sw.add(self.dpkgconfigure_vteterm)
        self.dpkgconfigure_vteterm.show_all()

        pty = Vte.Pty.new_sync(Vte.PtyFlags.DEFAULT)
        self.dpkgconfigure_vteterm.set_pty(pty)
        try:
            self.dpkgconfigure_vteterm.spawn_async(
                Vte.PtyFlags.DEFAULT,
                os.environ['HOME'],
                command,
                None,
                GLib.SpawnFlags.DO_NOT_REAP_CHILD,
                None,
                None,
                -1,
                None,
                self.dpkgconfigure_vte_create_spawn_callback,
                None
            )
        except Exception as e:
            # old version VTE doesn't have spawn_async so use spawn_sync
            print("{}".format(e))
            self.dpkgconfigure_vteterm.connect("child-exited", self.dpkgconfigure_vte_on_done)
            self.dpkgconfigure_vteterm.spawn_sync(
                Vte.PtyFlags.DEFAULT,
                os.environ['HOME'],
                command,
                [],
                GLib.SpawnFlags.DO_NOT_REAP_CHILD,
                None,
                None,
            )

    def dpkgconfigure_vte_create_spawn_callback(self, terminal, pid, error, userdata):
        self.dpkgconfigure_vteterm.connect("child-exited", self.dpkgconfigure_vte_on_done)

    def dpkgconfigure_vte_on_done(self, terminal, status):
        print("dpkgconfigure_vte_on_done status: {}".format(status))

        self.dpkgconfiguring = False

        self.ui_dpkgconfigurefix_button.set_sensitive(True)

        self.ui_dpkgconfigureinfo_spinner.set_visible(False)
        self.ui_dpkgconfigureinfo_spinner.stop()

        if status == 32256:  # operation cancelled | Request dismissed
            self.ui_dpkgconfigureinfo_label.set_markup("<b>{}</b>".format(_("Error.")))
        else:
            self.ui_dpkgconfigureinfo_label.set_markup("<b>{}</b>".format(_("Process completed.")))
            self.ui_dpkgconfigureok_button.set_visible(True)

            if status == 0:
                self.ui_dpkgconfigurefix_box.set_visible(False)
                self.Package.updatecache()

        self.update_inprogress = False


    def startAptUpgradeProcess(self, params):
        pid, stdin, stdout, stderr = GLib.spawn_async(params, flags=GLib.SpawnFlags.DO_NOT_REAP_CHILD,
                                                      standard_output=True, standard_error=True)
        GLib.io_add_watch(GLib.IOChannel(stdout), GLib.IO_IN | GLib.IO_HUP, self.onAptUpgradeProcessStdout)
        GLib.io_add_watch(GLib.IOChannel(stderr), GLib.IO_IN | GLib.IO_HUP, self.onAptUpgradeProcessStderr)
        GLib.child_watch_add(GLib.PRIORITY_DEFAULT, pid, self.onAptUpgradeProcessExit)

        return pid

    def onAptUpgradeProcessStdout(self, source, condition):
        if condition == GLib.IO_HUP:
            return False
        line = source.readline()
        print("onAptUpgradeProcessStdout: {}".format(line))
        return True

    def onAptUpgradeProcessStderr(self, source, condition):
        if condition == GLib.IO_HUP:
            return False
        line = source.readline()
        print("onAptUpgradeProcessStderr: {}".format(line))
        return True

    def onAptUpgradeProcessExit(self, pid, status):
        print("onAptUpgradeProcessExit: {}".format(status))
        try:
            timestamp = int(datetime.now().timestamp())
        except Exception as e:
            print("timestamp Error: {}".format(e))
            timestamp = 0

        command = ["/usr/bin/pkexec", os.path.dirname(os.path.abspath(__file__)) + "/SystemSettingsWrite.py",
                   "write", "lastupgrade", "{}".format(timestamp)]
        subprocess.run(command)
        print("SystemSettings.config_upgrade_lastupgrade writed")

        self.system_settings()
        self.Package.updatecache()
        self.create_autoupgrade_glibid()
        self.set_upgradable_page_and_notify()

        notification = Notification(summary=_("Pardus Update"),
                                    body=_("Automatic upgrade completed."),
                                    icon=self.icon_normal, appid=self.Application.get_application_id(),
                                    only_info=True)
        notification_state = self.UserSettings.config_notifications
        if self.SystemSettings.config_notifications is not None:
            notification_state = self.SystemSettings.config_notifications
        GLib.idle_add(notification.show, notification_state)

        self.auto_upgrade_inprogress = False

    def settings_vte_event(self, widget, event):
        if event.type == Gdk.EventType.BUTTON_PRESS:
            if event.button.button == 3:
                widget.popup_for_device(None, None, None, None, None,
                                        event.button.button, event.time)
                return True
        return False

    def settings_vte_menu_action(self, widget, terminal):
        terminal.copy_clipboard()

    def settings_vte_start_process(self, command):
        if self.settings_vteterm:
            self.settings_vteterm.get_parent().remove(self.settings_vteterm)

        self.settings_vteterm = Vte.Terminal()
        self.update_vte_color(self.settings_vteterm)
        self.settings_vteterm.set_scrollback_lines(-1)
        settings_vte_menu = Gtk.Menu()
        settings_vte_menu_items = Gtk.MenuItem(label=_("Copy selected text"))
        settings_vte_menu.append(settings_vte_menu_items)
        settings_vte_menu_items.connect("activate", self.settings_vte_menu_action, self.settings_vteterm)
        settings_vte_menu_items.show()
        self.settings_vteterm.connect_object("event", self.settings_vte_event, settings_vte_menu)
        self.ui_settingsvte_sw.add(self.settings_vteterm)
        self.settings_vteterm.show_all()

        pty = Vte.Pty.new_sync(Vte.PtyFlags.DEFAULT)
        self.settings_vteterm.set_pty(pty)
        try:
            self.settings_vteterm.spawn_async(
                Vte.PtyFlags.DEFAULT,
                os.environ['HOME'],
                command,
                None,
                GLib.SpawnFlags.DO_NOT_REAP_CHILD,
                None,
                None,
                -1,
                None,
                self.settings_vte_create_spawn_callback,
                None
            )
        except Exception as e:
            # old version VTE doesn't have spawn_async so use spawn_sync
            print("{}".format(e))
            self.settings_vteterm.connect("child-exited", self.settings_vte_on_done)
            self.settings_vteterm.spawn_sync(
                Vte.PtyFlags.DEFAULT,
                os.environ['HOME'],
                command,
                [],
                GLib.SpawnFlags.DO_NOT_REAP_CHILD,
                None,
                None,
            )

    def settings_vte_create_spawn_callback(self, terminal, pid, error, userdata):
        self.settings_vteterm.connect("child-exited", self.settings_vte_on_done)

    def settings_vte_on_done(self, terminal, status):
        print("settings_vte_on_done status: {}".format(status))
        self.ui_settings_aptclear_ok_button.set_visible(True)
        if status == 0:
            self.Package = Package()
            if self.Package.updatecache():
                self.isbroken = False
                self.indicator.set_icon(self.icon_normal)
            else:
                self.isbroken = True
                print("Error while updating cache on settings_vte_on_done")

            if self.source_switch_clicked:
                self.on_ui_fix_sources_button_clicked(button=None)
        self.update_inprogress = False
        self.source_switch_clicked = False

    def start_group_process(self, params):
        pid, stdin, stdout, stderr = GLib.spawn_async(params, flags=GLib.SpawnFlags.DO_NOT_REAP_CHILD,
                                                      standard_output=True, standard_error=True)
        GLib.io_add_watch(GLib.IOChannel(stdout), GLib.IO_IN | GLib.IO_HUP, self.on_group_process_stdout)
        GLib.io_add_watch(GLib.IOChannel(stderr), GLib.IO_IN | GLib.IO_HUP, self.on_group_process_stderr)
        GLib.child_watch_add(GLib.PRIORITY_DEFAULT, pid, self.on_group_process_exit)

        return pid

    def on_group_process_stdout(self, source, condition):
        if condition == GLib.IO_HUP:
            return False
        line = source.readline()
        print("on_group_process_stdout - line: {}".format(line))
        return True

    def on_group_process_stderr(self, source, condition):
        if condition == GLib.IO_HUP:
            return False
        line = source.readline()
        print("on_group_process_stderr - line: {}".format(line))
        self.grouperrormessage = line
        return True

    def on_group_process_exit(self, pid, status):
        print("on_group_process_exit - status: {}".format(status))
        self.control_groups()
        if status == 32256:  # operation cancelled | Request dismissed
            print("operation cancelled | Request dismissed")
        else:
            if self.grouperrormessage != "":
                ErrorDialog(_("Error"), "{}".format(self.grouperrormessage))


class Notification(GObject.GObject):
    __gsignals__ = {
        'notify-action': (GObject.SIGNAL_RUN_FIRST, None,
                          (str,))
    }

    def __init__(self, summary="", body="", icon="pardus-update", appid="tr.org.pardus-update", only_info=False):
        GObject.GObject.__init__(self)
        self.appid = appid
        if Notify.is_initted():
            Notify.uninit()
        Notify.init(appid)
        self.notification = Notify.Notification.new(summary, body, icon)
        if not only_info:
            self.notification.set_timeout(Notify.EXPIRES_NEVER)
            self.notification.add_action('update', _('Update'), self.update_callback)
            self.notification.add_action('close', _('Close'), self.close_callback)
        self.notification.connect('closed', self.on_closed)

    def show(self, user_show_state):
        if user_show_state:
            self.notification.show()

    def update_callback(self, widget, action):
        # subprocess.Popen(["/home/fatih/Desktop/pardus-update/src/Main.py", "--page", "updateinfo"])
        subprocess.Popen(["/usr/bin/pardus-update", "--page", "updateinfo"])
        # subprocess.Popen(["gtk-launch", self.appid])
        self.emit('notify-action', action)

    def close_callback(self, widget, action):
        self.emit('notify-action', 'closed')

    def on_closed(self, widget):
        self.emit('notify-action', 'closed')
