#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Feb 16 14:53:13 2022

@author: fatih
"""

import os
from configparser import ConfigParser
from pathlib import Path

import gi

gi.require_version("GLib", "2.0")
from gi.repository import GLib


class UserSettings(object):
    def __init__(self):
        self.default_update_interval = 86400  # daily
        self.default_update_lastupdate = 0
        self.default_update_selectable = False

        self.default_autostart = True
        self.default_notifications = True

        self.user_name = GLib.get_user_name()

        self.configdir = "{}/pardus/pardus-update/".format(GLib.get_user_config_dir())
        self.configfile = "settings.ini"

        self.autostartdir = "{}/autostart/".format(GLib.get_user_config_dir())
        self.autostartfile = "tr.org.pardus.update-autostart.desktop"

        self.user_keeps_file = "{}/user_keeps".format(self.configdir)

        self.config = ConfigParser(strict=False)

        self.config_update_interval = self.default_update_interval
        self.config_update_lastupdate = self.default_update_lastupdate
        self.config_update_selectable = self.default_update_selectable

        self.config_autostart = self.default_autostart
        self.config_notifications = self.default_notifications

    def createDefaultConfig(self, force=False):
        self.config['Update'] = {"interval": self.default_update_interval,
                                 "lastupdate": self.default_update_lastupdate,
                                 "selectable": self.default_update_selectable}

        self.config['Main'] = {"autostart": self.default_autostart,
                               "notifications": self.default_notifications}

        if not Path.is_file(Path(self.configdir + self.configfile)) or force:
            if self.createDir(self.configdir):
                with open(self.configdir + self.configfile, "w") as cf:
                    self.config.write(cf)

    def readConfig(self):
        try:
            self.config.read(self.configdir + self.configfile)
            self.config_update_interval = self.config.getint('Update', 'interval')
            if self.config_update_interval < 30 and self.config_update_interval != -1:
                print("interval must be greeter than 30 seconds")
                self.config_update_interval = 30
            self.config_update_lastupdate = self.config.getint('Update', 'lastupdate')
            self.config_update_selectable = self.config.getboolean('Update', 'selectable')
            self.config_autostart = self.config.getboolean('Main', 'autostart')
            self.config_notifications = self.config.getboolean('Main', 'notifications')

        except Exception as e:
            print("{}".format(e))
            print("user config read error ! Trying create defaults")
            # if not read; try to create defaults
            self.config_update_interval = self.default_update_interval
            self.config_update_lastupdate = self.default_update_lastupdate
            self.config_update_selectable = self.default_update_selectable
            self.config_autostart = self.default_autostart
            self.config_notifications = self.default_notifications
            try:
                self.createDefaultConfig(force=True)
            except Exception as e:
                print("self.createDefaultConfig(force=True) : {}".format(e))

    def writeConfig(self, interval, lastupdate, selectable, autostart, notifications):
        if interval < 30 and interval != -1:
            print("interval must be greeter than 30 seconds")
            interval = 30
        self.config['Update'] = {"interval": interval, "lastupdate": lastupdate, "selectable": selectable}
        self.config['Main'] = {"autostart": autostart, "notifications": notifications}
        if self.createDir(self.configdir):
            with open(self.configdir + self.configfile, "w") as cf:
                self.config.write(cf)
                return True
        return False

    def createDir(self, dir):
        try:
            Path(dir).mkdir(parents=True, exist_ok=True)
            return True
        except:
            print("{} : {}".format("mkdir error", dir))
            return False

    def set_autostart(self, state):
        self.createDir(self.autostartdir)
        p = Path(self.autostartdir + self.autostartfile)
        if state:
            if not p.exists():
                p.symlink_to(os.path.dirname(os.path.abspath(__file__)) + "/../data/" + self.autostartfile)
        else:
            if p.exists():
                p.unlink(missing_ok=True)

    def set_user_keeps_file(self, keep_list):
        with open(self.user_keeps_file, "w") as keep_file:
            for keep_package in keep_list:
                keep_file.writelines("{}\n".format(keep_package))

    def get_user_keeps_from_file(self):
        keep_list = []
        try:
            if os.path.isfile(self.user_keeps_file):
                with open(self.user_keeps_file, "r") as keep_file:
                    for line in keep_file:
                        keep_list.append(line.strip())
        except Exception as e:
            print("Error in get_user_keeps_from_file: {}".format(e))
        return keep_list
