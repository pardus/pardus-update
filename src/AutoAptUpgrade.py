#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jun  1 14:53:13 2024

@author: fatih
"""

import os
import shutil
import subprocess
from configparser import ConfigParser
from datetime import datetime
from pathlib import Path
from shutil import rmtree

import distro


def main():
    def create_dir(dir_path):
        try:
            Path(dir_path).mkdir(parents=True, exist_ok=True)
            return True
        except:
            print("{} : {}".format("mkdir error", dir_path))
            print("pardus-update: mkdir error: {}".format(dir_path), file=logfile)
            return False

    logdir = "/usr/share/pardus/pardus-update/log"
    backupdir = "/usr/share/pardus/pardus-update/backup"

    configdir = "/etc/pardus/"
    configfile = "pardus-update.conf"
    config = ConfigParser(strict=False)

    now = datetime.now().strftime("%Y.%m.%d.%H.%M")
    logfile_path = os.path.join(logdir, "{}.log".format(now))
    create_dir(backupdir)
    create_dir(logdir)
    logfile = open(logfile_path, "a")

    def apt_clean():
        rmtree("/var/lib/apt/lists/", ignore_errors=True)
        subprocess.call(["apt", "clean"],
                        env={**os.environ, 'DEBIAN_FRONTEND': 'noninteractive'}, stderr=logfile, stdout=logfile)

    def fixbroken():
        subprocess.call(["apt", "install", "--fix-broken", "-yq"],
                        env={**os.environ, 'DEBIAN_FRONTEND': 'noninteractive'}, stderr=logfile, stdout=logfile)

    def dpkgconfigure():
        subprocess.call(["dpkg", "--configure", "-a"],
                        env={**os.environ, 'DEBIAN_FRONTEND': 'noninteractive'}, stderr=logfile, stdout=logfile)

    def update():
        subprocess.call(["apt", "update"],
                        env={**os.environ, 'DEBIAN_FRONTEND': 'noninteractive'}, stderr=logfile, stdout=logfile)

    def set_real_sources():
        found = True
        source = ""
        major = distro.major_version()
        codename = distro.codename().lower()

        print("pardus-update: DISTRO: {} {}".format(codename, major), file=logfile)

        if codename == "ondokuz":
            source = "### The Official Pardus Package Repositories ###\n\n" \
                     "deb http://depo.pardus.org.tr/pardus ondokuz main contrib non-free\n" \
                     "# deb-src http://depo.pardus.org.tr/pardus ondokuz main contrib non-free\n\n" \
                     "deb http://depo.pardus.org.tr/guvenlik ondokuz main contrib non-free\n" \
                     "# deb-src http://depo.pardus.org.tr/guvenlik ondokuz main contrib non-free\n\n" \
                     "### This section generated by Pardus Auto Upgrade at " + str(now) + " ###\n"
        elif codename == "yirmibir":
            source = "### The Official Pardus Package Repositories ###\n\n" \
                     "deb http://depo.pardus.org.tr/pardus yirmibir main contrib non-free\n" \
                     "# deb-src http://depo.pardus.org.tr/pardus yirmibir main contrib non-free\n\n" \
                     "deb http://depo.pardus.org.tr/guvenlik yirmibir main contrib non-free\n" \
                     "# deb-src http://depo.pardus.org.tr/guvenlik yirmibir main contrib non-free\n\n" \
                     "### This section generated by Pardus Auto Upgrade at " + str(now) + " ###\n"
        elif codename == "yirmiuc":
            source = "### The Official Pardus Package Repositories ###\n\n" \
                     "## Pardus\n" \
                     "deb http://depo.pardus.org.tr/pardus yirmiuc main contrib non-free non-free-firmware\n" \
                     "# deb-src http://depo.pardus.org.tr/pardus yirmiuc main contrib non-free non-free-firmware\n\n" \
                     "## Pardus Deb\n" \
                     "deb http://depo.pardus.org.tr/pardus yirmiuc-deb main contrib non-free non-free-firmware\n" \
                     "# deb-src http://depo.pardus.org.tr/pardus yirmiuc-deb main contrib non-free non-free-firmware\n\n" \
                     "## Pardus Security Deb\n" \
                     "deb http://depo.pardus.org.tr/guvenlik yirmiuc-deb main contrib non-free non-free-firmware\n" \
                     "# deb-src http://depo.pardus.org.tr/guvenlik yirmiuc-deb main contrib non-free non-free-firmware\n\n" \
                     "### This section generated by Pardus Auto Upgrade at " + str(now) + " ###\n"
        elif codename == "etap":
            if major == "19":
                source = "### The Official Pardus Package Repositories ###\n\n" \
                         "deb http://19.depo.pardus.org.tr/etap ondokuz main contrib non-free\n" \
                         "# deb-src http://19.depo.pardus.org.tr/etap ondokuz main contrib non-free\n\n" \
                         "deb http://19.depo.pardus.org.tr/etap-guvenlik ondokuz main contrib non-free\n" \
                         "# deb-src http://19.depo.pardus.org.tr/etap-guvenlik ondokuz main contrib non-free\n\n" \
                         "### This section generated by Pardus Auto Upgrade at " + str(now) + " ###\n"
            else:
                found = False
        elif codename == "bookworm":
            source = "### The Official Debian Package Repositories ###\n\n" \
                     "deb http://deb.debian.org/debian bookworm main contrib non-free non-free-firmware\n" \
                     "# deb-src http://deb.debian.org/debian bookworm main contrib non-free non-free-firmware\n\n" \
                     "deb http://deb.debian.org/debian-security bookworm-security main contrib non-free non-free-firmware\n" \
                     "# deb-src http://deb.debian.org/debian-security bookworm-security main contrib non-free non-free-firmware\n\n" \
                     "### This section generated by Pardus Auto Upgrade at " + str(now) + " ###\n"
        elif codename == "bullseye":
            source = "### The Official Debian Package Repositories ###\n\n" \
                     "deb http://deb.debian.org/debian bullseye main contrib non-free\n" \
                     "# deb-src http://deb.debian.org/debian bullseye main contrib non-free\n\n" \
                     "deb http://deb.debian.org/debian-security bullseye-security main contrib non-free\n" \
                     "# deb-src http://deb.debian.org/debian-security bullseye-security main contrib non-free\n\n" \
                     "### This section generated by Pardus Auto Upgrade at " + str(now) + " ###\n"
        elif codename == "buster":
            source = "### The Official Debian Package Repositories ###\n\n" \
                     "deb http://deb.debian.org/debian buster main contrib non-free\n" \
                     "# deb-src http://deb.debian.org/debian buster main contrib non-free\n\n" \
                     "deb http://deb.debian.org/debian-security buster/updates main contrib non-free\n" \
                     "# deb-src http://deb.debian.org/debian-security buster/updates main contrib non-free\n\n" \
                     "### This section generated by Pardus Auto Upgrade at " + str(now) + " ###\n"
        else:
            found = False

        if found:
            # backup original sources.list and log
            shutil.copy2("/etc/apt/sources.list", os.path.join(backupdir, "{}-sources.list".format(now)))
            with open("/etc/apt/sources.list", "r") as sources_list_file:
                print("### {} (old) ###".format("/etc/apt/sources.list"), file=logfile)
                print(sources_list_file.read() + "\n", file=logfile)

            # write real sources to sources.list file
            sfile = open("/etc/apt/sources.list", "w")
            sfile.write(source)
            sfile.flush()
            sfile.close()

            # log new sources.list file
            with open("/etc/apt/sources.list", "r") as new_sources_list_file:
                print("### {} (new) ###".format("/etc/apt/sources.list"), file=logfile)
                print(new_sources_list_file.read() + "\n", file=logfile)

    def set_custom_sources(sources_path):
        if sources_path is not None:

            # use new sources for /etc/apt/sources.list
            if os.path.isfile(sources_path):
                with open("/etc/apt/sources.list", "r") as sources_list_file:
                    print("### {} (old) ###".format("/etc/apt/sources.list"), file=logfile)
                    print(sources_list_file.read() + "\n", file=logfile)

                with open(sources_path, "r") as sources_file:
                    print("### {} (new) ###".format(sources_path), file=logfile)
                    print(sources_file.read() + "\n", file=logfile)

                shutil.copy2("/etc/apt/sources.list", os.path.join(backupdir, "{}-sources.list".format(now)))
                shutil.copy2(sources_path, "/etc/apt/sources.list")
            else:
                print("{} file not exists!".format(sources_path), file=logfile)

    def add_sourcesd(sourcesd_path):
        if sourcesd_path is not None:

            # add new sources to /etc/apt/sources.list.d/
            if os.path.isfile(sourcesd_path):

                with open(sourcesd_path, "r") as sourcesd_file:
                    print("### {} (new) ###".format(sourcesd_path), file=logfile)
                    print(sourcesd_file.read() + "\n", file=logfile)
                shutil.copy2(sourcesd_path, "/etc/apt/sources.list.d/")
            else:
                print("{} file not exists!".format(sourcesd_path), file=logfile)

    def disable_sourcesd_list():
        # comment line /etc/apt/sources.list.d/*.list
        sdir = "/etc/apt/sources.list.d"
        if os.path.isdir(sdir):
            slistd = os.listdir(sdir)
            for slist in slistd:
                commented = ""
                if slist.endswith(".list"):
                    try:
                        shutil.copy2(os.path.join(sdir, slist),
                                     os.path.join(backupdir, "{}-{}".format(now, slist)))
                        with open(os.path.join(sdir, slist), "r") as sread:
                            print("### {} ###".format(slist), file=logfile)
                            for line in sread.readlines():
                                print(line, file=logfile)
                                if line.strip().startswith("deb"):
                                    comment = line.replace("deb ", "#deb ")
                                else:
                                    comment = line
                                commented += comment
                            print("\n", file=logfile)
                        with open(os.path.join(sdir, slist), "w") as swrite:
                            swrite.writelines(commented)
                            swrite.flush()
                            swrite.close()
                    except Exception as e:
                        print("{}".format(e))
                        print("pardus-update: {}".format(e), file=logfile)

    def control_fixes():
        if fix is not None and fix:
            dpkgconfigure()
            fixbroken()

    def upgrade(dpkg_conf_string):
        dpkg_conf_list = dpkg_conf_string.split(" ")

        subprocess.call(["apt", "full-upgrade", "-yq"] + dpkg_conf_list,
                        env={**os.environ, 'DEBIAN_FRONTEND': 'noninteractive'}, stderr=logfile, stdout=logfile)

    config.read(configdir + configfile)
    fix = False
    dpkg_conf = "-o Dpkg::Options::=--force-confnew"
    use_real_sources = False
    custom_sources_path = None
    custom_sourcesd_path = None
    disable_sourcesd = False

    if config.has_option("Upgrade", "use_real_sources"):
        try:
            use_real_sources = config.getboolean('Upgrade', 'use_real_sources')
        except Exception as e:
            print("{}".format(e))
            print("pardus-update: {}".format(e), file=logfile)

    if config.has_option("Upgrade", "custom_sources_path"):
        try:
            custom_sources_path = config.get('Upgrade', 'custom_sources_path').strip('"')
        except Exception as e:
            print("{}".format(e))
            print("pardus-update: {}".format(e), file=logfile)

    if config.has_option("Upgrade", "custom_sourcesd_path"):
        try:
            custom_sourcesd_path = config.get('Upgrade', 'custom_sourcesd_path').strip('"')
        except Exception as e:
            print("{}".format(e))
            print("pardus-update: {}".format(e), file=logfile)

    if config.has_option("Upgrade", "disable_sourcesd"):
        try:
            disable_sourcesd = config.getboolean('Upgrade', 'disable_sourcesd')
        except Exception as e:
            print("{}".format(e))
            print("pardus-update: {}".format(e), file=logfile)

    if config.has_option("Upgrade", "dpkg_conf"):
        try:
            dpkgconf = config.get('Upgrade', 'dpkg_conf').strip('"')
            if dpkgconf == "old":
                dpkg_conf = "-o Dpkg::Options::=--force-confold"
        except Exception as e:
            print("{}".format(e))
            print("pardus-update: {}".format(e), file=logfile)

    if config.has_option("Upgrade", "fix"):
        try:
            fix = config.getboolean('Upgrade', 'fix')
        except Exception as e:
            print("{}".format(e))
            print("pardus-update: {}".format(e), file=logfile)

    if use_real_sources:
        set_real_sources()
    else:
        if custom_sources_path is not None:
            set_custom_sources(custom_sources_path)

    if disable_sourcesd:
        disable_sourcesd_list()

    if custom_sourcesd_path is not None:
        add_sourcesd(custom_sourcesd_path)

    # apt_clean()
    update()
    control_fixes()
    upgrade(dpkg_conf)
    logfile.flush()
    logfile.close()


if __name__ == "__main__":
    main()