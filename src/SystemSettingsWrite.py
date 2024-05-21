#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Feb 16 14:53:13 2022

@author: fatih
"""

import sys
from configparser import ConfigParser


def main():
    configdir = "/etc/pardus/"
    configfile = "pardus-update.conf"
    config = ConfigParser(strict=False)

    def write_lastupdate(timestamp):
        config.read(configdir + configfile)

        if config.has_section("Update"):
            config.set("Update", "lastupdate", timestamp)
        else:
            config['Update'] = {"lastupdate": timestamp}

        with open(configdir + configfile, "w") as cf:
            config.write(cf)

    def write_lastupgrade(timestamp):
        config.read(configdir + configfile)

        if config.has_section("Upgrade"):
            config.set("Upgrade", "lastupgrade", timestamp)
        else:
            config['Upgrade'] = {"lastupgrade": timestamp}

        with open(configdir + configfile, "w") as cf:
            config.write(cf)

    if len(sys.argv) > 2:
        if sys.argv[1] == "write":
            if sys.argv[2] == "lastupdate":
                write_lastupdate(sys.argv[3])
            if sys.argv[2] == "lastupgrade":
                write_lastupgrade(sys.argv[3])
        else:
            print("unknown argument error")
    else:
        print("no argument passed")


if __name__ == "__main__":
    main()
