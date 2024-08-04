#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Feb 16 14:53:13 2022

@author: fatih
"""

from configparser import ConfigParser


class SystemSettings(object):
    def __init__(self):

        self.configdir = "/etc/pardus/"
        self.configfile = "pardus-update.conf"

        self.config = ConfigParser(strict=False)

        self.config_update_interval = None
        self.config_update_lastupdate = None
        self.config_update_selectable = None

        self.config_autostart = None
        self.config_notifications = None

        self.config_upgrade_enabled = None
        self.config_upgrade_interval = None
        self.config_upgrade_lastupgrade = None
        self.config_upgrade_fix = None
        self.config_upgrade_sources = None

    def readConfig(self):
        try:
            self.config.read(self.configdir + self.configfile)

            if self.config.has_option("Update", "interval"):
                self.config_update_interval = self.config.getint('Update', 'interval')
                if self.config_update_interval < 30 and self.config_update_interval != -1:
                    print("interval must be greeter than 30 seconds")
                    self.config_update_interval = 30
            if self.config.has_option("Update", "lastupdate"):
                self.config_update_lastupdate = self.config.getint('Update', 'lastupdate')

            if self.config.has_option("Update", "selectable"):
                self.config_update_selectable = self.config.getboolean('Update', 'selectable')

            if self.config.has_option("Main", "autostart"):
                self.config_autostart = self.config.getboolean('Main', 'autostart')
            if self.config.has_option("Main", "notifications"):
                self.config_notifications = self.config.getboolean('Main', 'notifications')

            if self.config.has_option("Upgrade", "enabled"):
                self.config_upgrade_enabled = self.config.getboolean('Upgrade', 'enabled')
            if self.config.has_option("Upgrade", "interval"):
                self.config_upgrade_interval = self.config.getint('Upgrade', 'interval')
            if self.config.has_option("Upgrade", "lastupgrade"):
                self.config_upgrade_lastupgrade = self.config.getint('Upgrade', 'lastupgrade')

        except Exception as e:
            print("{}".format(e))
            print("system config read error !")
