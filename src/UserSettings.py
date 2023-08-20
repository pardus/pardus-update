#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Feb 16 14:53:13 2022

@author: fatih
"""

import os
from configparser import ConfigParser
from pathlib import Path


class UserSettings(object):
    def __init__(self):
        self.userhome = str(Path.home())

        self.default_interval = 86400  # daily
        self.default_lastupdate = 0
        self.default_autostart = True

        self.configdir = self.userhome + "/.config/pardus/pardus-update/"
        self.configfile = "settings.ini"

        self.autostartdir = self.userhome + "/.config/autostart/"
        self.autostartfile = "tr.org.pardus.update-autostart.desktop"

        self.config = ConfigParser(strict=False)

        self.config_interval = self.default_interval
        self.config_lastupdate = self.default_lastupdate
        self.config_autostart = self.default_autostart

    def createDefaultConfig(self, force=False):
        self.config['Update'] = {"interval": self.default_interval,
                                 "lastupdate": self.default_lastupdate}

        self.config['Main'] = {"autostart": self.default_autostart}

        if not Path.is_file(Path(self.configdir + self.configfile)) or force:
            if self.createDir(self.configdir):
                with open(self.configdir + self.configfile, "w") as cf:
                    self.config.write(cf)

    def readConfig(self):
        try:
            self.config.read(self.configdir + self.configfile)
            self.config_interval = self.config.getint('Update', 'interval')
            if self.config_interval < 30 and self.config_interval != -1:
                print("interval must be greeter than 30 seconds")
                self.config_interval = 30
            self.config_lastupdate = self.config.getint('Update', 'lastupdate')
            self.config_autostart = self.config.getboolean('Main', 'autostart')

        except Exception as e:
            print("{}".format(e))
            print("user config read error ! Trying create defaults")
            # if not read; try to create defaults
            self.config_interval = self.default_interval
            self.config_lastupdate = self.default_lastupdate
            self.config_autostart = self.default_autostart
            try:
                self.createDefaultConfig(force=True)
            except Exception as e:
                print("self.createDefaultConfig(force=True) : {}".format(e))

    def writeConfig(self, interval, lastupdate, autostart):
        if interval < 30 and interval != -1:
            print("interval must be greeter than 30 seconds")
            interval = 30
        self.config['Update'] = {"interval": interval, "lastupdate": lastupdate}
        self.config['Main'] = {"autostart": autostart}
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
