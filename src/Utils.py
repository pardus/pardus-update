#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Mar 20 23:59:23 2024

@author: fatih
"""
import os
import subprocess
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gio, GLib

import locale
from locale import gettext as _

locale.bindtextdomain('pardus-update', '/usr/share/locale')
locale.textdomain('pardus-update')

class Utils(object):
    def __init__(self):

        self.de_version_command = {"xfce": ["xfce4-session", "--version"],
                                   "gnome": ["gnome-shell", "--version"],
                                   "cinnamon": ["cinnamon", "--version"],
                                   "mate": ["mate-about", "--version"],
                                   "kde": ["plasmashell", "--version"],
                                   "lxqt": ["lxqt-about", "--version"],
                                   "budgie": ["budgie-desktop", "--version"]}

    def get_desktop_env(self):
        current_desktop = "{}".format(os.environ.get('XDG_CURRENT_DESKTOP'))
        return current_desktop

    def get_desktop_env_version(self, desktop):
        version = ""
        desktop = "{}".format(desktop.lower())
        try:
            if "xfce" in desktop:
                output = (subprocess.run(self.de_version_command["xfce"], shell=False, stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE)).stdout.decode().strip()
                for line in output.split("\n"):
                    if line.startswith("xfce4-session "):
                        version = line.split(" ")[-1].strip("()")
                        break

            elif "gnome" in desktop:
                output = (subprocess.run(self.de_version_command["gnome"], shell=False, stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE)).stdout.decode().strip()
                for line in output.split("\n"):
                    if "GNOME Shell" in line:
                        version = line.split(" ")[-1]

            elif "cinnamon" in desktop:
                output = (subprocess.run(self.de_version_command["cinnamon"], shell=False, stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE)).stdout.decode().strip()
                version = output.split(" ")[-1]

            elif "mate" in desktop:
                output = (subprocess.run(self.de_version_command["mate"], shell=False, stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE)).stdout.decode().strip()
                version = output.split(" ")[-1]

            elif "kde" in desktop:
                output = (subprocess.run(self.de_version_command["kde"], shell=False, stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE)).stdout.decode().strip()
                version = output.split(" ")[-1]

            elif "lxqt" in desktop:
                output = (subprocess.run(self.de_version_command["lxqt"], shell=False, stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE)).stdout.decode().strip()
                for line in output:
                    if "liblxqt" in line:
                        version = line.split()[1].strip()

            elif "budgie" in desktop:
                output = (subprocess.run(self.de_version_command["budgie"], shell=False, stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE)).stdout.decode().strip()
                version = output.split("\n")[0].strip().split(" ")[-1]
        except Exception as e:
            self.Logger.warning("Error on get_desktop_env_version")
            self.Logger.exception("{}".format(e))

        return version

    def get_session_type(self):
        session = "{}".format(os.environ.get('XDG_SESSION_TYPE')).capitalize()
        return session

    def get_path_size(self, path):
        total = 0
        if os.access(path, os.R_OK):
            with os.scandir(path) as it:
                for entry in it:
                    if entry.is_file():
                        total += entry.stat().st_size
                    elif entry.is_dir():
                        if os.access(entry, os.R_OK):
                            total += self.get_path_size(entry.path)
                        else:
                            print("{} is not readable.".format(entry.path))
        else:
            print("{} is not readable.".format(path))
        return total

    def get_path_files(self, path):
        path_files = []
        if os.access(path, os.R_OK):
            with os.scandir(path) as it:
                for entry in it:
                    if entry.is_file() and os.access(entry.path, os.R_OK):
                        path_files.append(entry.path)
                    elif entry.is_dir():
                        if os.access(entry, os.R_OK):
                            path_files += self.get_path_files(entry.path)
                        # else:
                        #     print("{} is not readable.".format(entry.path))
        # else:
        #     print("{} is not readable.".format(path))
        return path_files

class Dialog(Gtk.MessageDialog):
    def __init__(self, style, buttons, title, text, text2=None, parent=None):
        Gtk.MessageDialog.__init__(self, parent, 0, style, buttons)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_title(title)
        self.set_markup(text)

    def show(self):
        try:
            response = self.run()
        finally:
            self.destroy()

def ErrorDialog(*args):
    dialog = Dialog(Gtk.MessageType.ERROR, Gtk.ButtonsType.NONE, *args)
    dialog.add_button(_("OK"), Gtk.ResponseType.OK)
    return dialog.show()
