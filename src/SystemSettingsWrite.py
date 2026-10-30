#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Feb 16 14:53:13 2022

@author: fatih
"""

import sys
import time
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

    def validate_timestamp(value):
        try:
            ts = int(value)
            # This runs without a password and the value overrides the user
            # settings, a time in the future would stop the update checks of
            # every user on the machine.
            if ts < 0 or ts > time.time() + 60:
                raise ValueError
            return str(ts)
        except ValueError:
            raise ValueError("Invalid timestamp")

    if len(sys.argv) > 2:
        if sys.argv[1] == "write":
            if sys.argv[2] == "lastupdate":
                write_lastupdate(validate_timestamp(sys.argv[3]))
        else:
            print("unknown argument error")
    else:
        print("no argument passed")


if __name__ == "__main__":
    main()
