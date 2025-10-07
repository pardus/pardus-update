#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Sep 18 14:53:00 2020

@author: fatih
"""
import json
import os
import random
import string
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from shutil import copy2
from shutil import rmtree

import apt
import apt_pkg
from aptsources import sourceslist as aptsourceslist
import distro

import locale
from locale import gettext as _

locale.bindtextdomain('pardus-update', '/usr/share/locale')
locale.textdomain('pardus-update')

def main():

    keep_list = ["firmware-b43-installer", "firmware-b43legacy-installer", "ttf-mscorefonts-installer"]

    def control_lock():
        msg = ""
        apt_pkg.init_system()
        try:
            apt_pkg.pkgsystem_lock()
        except SystemError as e:
            msg = "{}".format(e)
            print("pardus-update: {}".format(msg), file=sys.stderr)
            return False, msg
        apt_pkg.pkgsystem_unlock()
        return True, msg

    def update():
        try:
            cache = apt.Cache()
            cache.open()
            cache.update()
        except Exception as e:
            print(str(e))
            subupdate()

    def subupdate():
        subprocess.call(["apt", "update"],
                        env={**os.environ, 'DEBIAN_FRONTEND': 'noninteractive'})

    def subupgrade(yq, dpkg_conf, keeps=None):
        lock, msg = control_lock()
        if not lock:
            if "E:" in msg and "/var/lib/dpkg/lock-frontend" in msg:
                print("dpkg lock error", file=sys.stderr)
                sys.exit(11)
            elif "E:" in msg and "dpkg --configure -a" in msg:
                print("dpkg interrupt error", file=sys.stderr)
                sys.exit(12)

        if keeps:
            keep_list = keeps.split(" ")
            for kp in keep_list:
                subprocess.call(["apt-mark", "hold", kp])

        dpkg_conf_list = dpkg_conf.split(" ")
        yq_list = yq.split(" ")
        subprocess.call(["apt", "full-upgrade"] + yq_list + dpkg_conf_list,
                        env={**os.environ, 'DEBIAN_FRONTEND': 'noninteractive'})

        if keeps:
            keep_list = keeps.split(" ")
            for kp in keep_list:
                subprocess.call(["apt-mark", "unhold", kp])

    def fixbroken():
        subprocess.call(["apt", "install", "--fix-broken", "-yq"],
                        env={**os.environ, 'DEBIAN_FRONTEND': 'noninteractive'})

    def dpkgconfigure():
        subprocess.call(["dpkg", "--configure", "-a"],
                        env={**os.environ, 'DEBIAN_FRONTEND': 'noninteractive'})

    def aptclean():
        subprocess.call(["apt", "clean"],
                        env={**os.environ, 'DEBIAN_FRONTEND': 'noninteractive'})

    def removeresidual(packages):
        packagelist = packages.split(" ")
        subprocess.call(["apt", "remove", "--purge", "-yq"] + packagelist,
                        env={**os.environ, 'DEBIAN_FRONTEND': 'noninteractive'})

    def removeauto():
        subprocess.call(["apt", "autoremove", "-yq"],
                        env={**os.environ, 'DEBIAN_FRONTEND': 'noninteractive'})

    def controldistupgrade(sourceslist):
        sfile = open("/tmp/tmp-sources.list", "w")
        sfile.write(sourceslist)
        sfile.flush()
        sfile.close()

        rc_file = os.path.dirname(os.path.abspath(__file__)) + "/../required_changes_for_upgrade.json"

        if os.path.isfile(rc_file):
            os.remove(rc_file)

        to_upgrade = []
        to_install = []
        to_delete = []
        to_keep = []
        changes_available = None
        cache_error = True

        rcu = {"download_size": None, "freed_size": None, "install_size": None, "to_upgrade": None, "to_install": None,
               "to_delete": None, "to_keep": None, "changes_available": changes_available, "cache_error": cache_error,
               "cache_error_msg": None}

        old_sources_list = apt_pkg.config.find("Dir::Etc::sourcelist")
        old_sources_list_d = apt_pkg.config.find("Dir::Etc::sourceparts")
        old_cleanup = apt_pkg.config.find("APT::List-Cleanup")
        apt_pkg.init_config()
        apt_pkg.config.set("Dir::Etc::sourcelist", os.path.abspath("/tmp/tmp-sources.list"))
        apt_pkg.config.set("Dir::Etc::sourceparts", "xxx")
        apt_pkg.config.set("APT::List-Cleanup", "0")
        apt_pkg.init_system()
        cache = apt.Cache()
        cache.update()
        cache.open()

        try:
            cache.upgrade(True)
            cache_error = False
        except Exception as error:
            print("cache.upgrade Error: {}".format(error))
            update_cache_error_msg = "{}".format(error)
            rcu["cache_error_msg"] = update_cache_error_msg

        for kp in keep_list:
            try:
                cache[kp].mark_keep()
            except Exception as e:
                print("{} not found".format(kp))
                print("{}".format(e))

        changes = cache.get_changes()
        print(changes)
        if changes:
            changes_available = True
            for package in changes:
                if package.is_installed:
                    if package.marked_upgrade:
                        to_upgrade.append(package.name)
                    elif package.marked_delete:
                        to_delete.append(package.name)
                elif package.marked_install:
                    to_install.append(package.name)
        else:
            changes_available = False

        download_size = cache.required_download
        space = cache.required_space
        if space < 0:
            freed_size = space * -1
            install_size = 0
        else:
            freed_size = 0
            install_size = space

        if cache.keep_count > 0:
            upgradable_cache_packages = [pkg.name for pkg in cache if pkg.is_upgradable]
            upgradable_changes_packages = [pkg.name for pkg in changes if pkg.is_upgradable]
            to_keep = list(set(upgradable_cache_packages).difference(set(upgradable_changes_packages)))

        to_upgrade = sorted(to_upgrade)
        to_install = sorted(to_install)
        to_delete = sorted(to_delete)
        to_keep = sorted(to_keep)

        rcu["download_size"] = download_size
        rcu["freed_size"] = freed_size
        rcu["install_size"] = install_size
        # rcu["to_upgrade"] = to_upgrade
        # rcu["to_install"] = to_install
        # rcu["to_delete"] = to_delete
        # rcu["to_keep"] = to_keep
        rcu["changes_available"] = changes_available
        rcu["cache_error"] = cache_error

        def summary(packagename):
            package = cache.get(packagename)
            if package is None: return ""
            try:
                return package.candidate.summary
            except AttributeError:
                sum = package.versions.get(0)
            return sum.summary if hasattr(sum, "summary") else "Summary is not found"

        def candidate_version(packagename):
            package = cache[packagename]
            if package is None: return ""
            try:
                version = package.candidate.version
            except:
                try:
                    version = package.versions[0].version
                except:
                    version = ""
            return version

        def installed_version(packagename):
            package = cache[packagename]
            if package is None: return ""
            try:
                version = package.installed.version
            except:
                version = ""
            return version

        to_install_list = []
        for package in to_install:
            to_install_list.append({"name": package, "oldversion": installed_version(package),
                                    "newversion": candidate_version(package), "summary": summary(package)})

        to_upgrade_list = []
        for package in to_upgrade:
            to_upgrade_list.append({"name": package, "oldversion": installed_version(package),
                                    "newversion": candidate_version(package), "summary": summary(package)})

        to_delete_list = []
        for package in to_delete:
            to_delete_list.append({"name": package, "oldversion": installed_version(package),
                                   "newversion": candidate_version(package), "summary": summary(package)})

        to_keep_list = []
        for package in to_keep:
            to_keep_list.append({"name": package, "oldversion": installed_version(package),
                                 "newversion": candidate_version(package), "summary": summary(package)})

        rcu["to_upgrade"] = to_upgrade_list
        rcu["to_install"] = to_install_list
        rcu["to_delete"] = to_delete_list
        rcu["to_keep"] = to_keep_list

        # print("freed_size {}".format(rcu["freed_size"]))
        # print("download_size {}".format(rcu["download_size"]))
        # print("install_size {}".format(rcu["install_size"]))
        # print("to_upgrade {}".format(rcu["to_upgrade"]))
        # print("to_install {}".format(rcu["to_install"]))
        # print("to_delete {}".format(rcu["to_delete"]))
        # print("to_keep {}".format(rcu["to_keep"]))
        # print("changes_available {}".format(rcu["changes_available"]))
        # print("cache_error {}".format(rcu["cache_error"]))

        print(rcu)

        changes_file = open(rc_file, "w")
        json.dump(rcu, changes_file, indent=2)
        changes_file.flush()
        changes_file.close()

        apt_pkg.config.set("Dir::Etc::sourcelist", old_sources_list)
        apt_pkg.config.set("Dir::Etc::sourceparts", old_sources_list_d)
        apt_pkg.config.set("APT::List-Cleanup", old_cleanup)

    def downupgrade(sourceslist):

        aptclean()

        sfile = open("/tmp/tmp-sources.list", "w")
        sfile.write(sourceslist)
        sfile.flush()
        sfile.close()

        apt_pkg.init_config()
        apt_pkg.config.set("Dir::Etc::sourcelist", os.path.abspath("/tmp/tmp-sources.list"))
        apt_pkg.config.set("Dir::Etc::sourceparts", "xxx")
        apt_pkg.config.set("APT::List-Cleanup", "0")
        apt_pkg.init_system()
        cache = apt.Cache()
        cache.update()
        cache.open()

        try:
            cache.upgrade(True)
        except Exception as error:
            print("cache.upgrade Error: {}".format(error))

        for kp in keep_list:
            try:
                cache[kp].mark_keep()
            except Exception as e:
                print("{} not found".format(kp))
                print("{}".format(e))

        cache.fetch_archives()

        # subprocess.call(["apt", "full-upgrade", "-yqd"],
        #                 env={**os.environ, 'DEBIAN_FRONTEND': 'noninteractive'})

    def distupgradeoffline(sourceslist, askconf):

        # aptlists_folder = "/var/lib/apt/lists/"
        # for filename in os.listdir(aptlists_folder):
        #     file_path = os.path.join(aptlists_folder, filename)
        #     try:
        #         if os.path.isfile(file_path) or os.path.islink(file_path):
        #             os.unlink(file_path)
        #     except Exception as e:
        #         print("Failed to delete {}. Reason: {}".format(file_path, e))

        app_safeupgrade_path = os.path.dirname(os.path.abspath(__file__)) + "/../data/pardus-safeupgrade-template.sh"
        safeupgrade_path = os.path.dirname(os.path.abspath(__file__)) + "/../data/pardus-safeupgrade.sh"

        app_service_path = os.path.dirname(os.path.abspath(__file__)) + "/../data/pardus-safeupgrade.service"
        service_path = "/usr/lib/systemd/system/pardus-safeupgrade.service"
        service_symlink_path = "/usr/lib/systemd/system/system-update.target.wants/pardus-safeupgrade.service"
        service_symlink_dir = "/usr/lib/systemd/system/system-update.target.wants"

        if os.path.isfile(app_safeupgrade_path) and os.path.isfile(app_service_path):

            with open(app_safeupgrade_path, "r") as app_safeupgrade_file:
                contents = app_safeupgrade_file.read()
                new_contents = contents.replace("@@askconf@@", askconf)

            # create new safe upgrade script from template
            usp = open(safeupgrade_path, "w")
            usp.write(new_contents)
            usp.flush()
            usp.close()
            os.chmod(safeupgrade_path, 0o0755)

            # service file with new execpath and symlink
            with open(app_service_path, "r") as app_service_file:
                scontents = app_service_file.read()
                new_scontents = scontents.replace("@@execpath@@", os.path.abspath(safeupgrade_path))

            user_service_file = open(service_path, "w")
            user_service_file.write(new_scontents)
            user_service_file.flush()
            user_service_file.close()

            if not os.path.exists(service_symlink_dir):
                os.makedirs(service_symlink_dir, exist_ok=True)
            service_symlink_file = Path(service_symlink_path)
            if service_symlink_file.exists():
                service_symlink_file.unlink(missing_ok=True)
            service_symlink_file.symlink_to(service_path)

            # sources.list.d
            sdir = "/etc/apt/sources.list.d"
            if os.path.isdir(sdir):
                slistd = os.listdir(sdir)
                for slist in slistd:
                    commented = ""
                    if slist.endswith(".list"):
                        try:
                            with open(os.path.join(sdir, slist), "r") as sread:
                                for line in sread.readlines():
                                    commented += "#{}".format(line)
                            with open(os.path.join(sdir, slist), "w") as swrite:
                                swrite.writelines(commented)
                                swrite.flush()
                                swrite.close()
                        except Exception as e:
                            print("{}".format(e))

            # sources.list
            sfile = open("/etc/apt/sources.list", "w")
            sfile.write(sourceslist)
            sfile.flush()
            sfile.close()

            # apt lists clean
            rmtree("/var/lib/apt/lists/", ignore_errors=True)
            subupdate()

            # set plymouth
            current_theme = ""
            try:
                with open("/etc/plymouth/plymouthd.conf", "r") as f:
                    for line in f:
                        if line.strip().startswith("Theme="):
                            current_theme = line.strip().split("=", 1)[1]
                            break
            except Exception as e:
                print("{}".format(e))
                current_theme = ""
            if current_theme != "bgrt":
                subprocess.run(["plymouth-set-default-theme", "bgrt"])
                subprocess.run(["update-initramfs", "-u"])

            # system-update file
            sup_path = "/system-update"
            if os.path.exists(sup_path):
                os.remove(sup_path)
            sub_path_file = open(sup_path, "w")
            sub_path_file.flush()
            sub_path_file.close()

            # sync
            syncp = subprocess.Popen(["/usr/bin/sync"])
            syncp.wait()

            if os.path.exists(safeupgrade_path) and os.path.exists(service_path) and os.path.exists(sup_path):

                # reboot
                os.system('dbus-send --system --print-reply --dest=org.freedesktop.login1 /org/freedesktop/login1 '
                          '"org.freedesktop.login1.Manager.Reboot" boolean:true')
            else:
                print("safeupgrade_path: {}, exists: {}".format(safeupgrade_path, os.path.exists(safeupgrade_path)), file=sys.stderr)
                print("service_path: {}, exists: {}".format(service_path, os.path.exists(service_path)), file=sys.stderr)
                print("systemupdate_path: {}, exists: {}".format(sup_path, os.path.exists(sup_path)), file=sys.stderr)
                if os.path.exists(sup_path):
                    os.remove(sup_path)
        else:
            print("{} file not exists.".format(app_safeupgrade_path))

    def distupgrade(sourceslist):
        sdir = "/etc/apt/sources.list.d"
        if os.path.isdir(sdir):
            slistd = os.listdir(sdir)
            for slist in slistd:
                commented = ""
                if slist.endswith(".list"):
                    try:
                        with open(os.path.join(sdir, slist), "r") as sread:
                            for line in sread.readlines():
                                commented += "#{}".format(line)
                        with open(os.path.join(sdir, slist), "w") as swrite:
                            swrite.writelines(commented)
                            swrite.flush()
                            swrite.close()
                    except Exception as e:
                        print("{}".format(e))

        sfile = open("/etc/apt/sources.list", "w")
        sfile.write(sourceslist)
        sfile.flush()
        sfile.close()

        rmtree("/var/lib/apt/lists/", ignore_errors=True)
        subupdate()

        subprocess.call(["apt", "full-upgrade", "-fuyq", "--no-download"],
                        env={**os.environ, 'DEBIAN_FRONTEND': 'noninteractive'})

    def aptclear(clean, autoremove, aptlists):
        print(clean)
        print(autoremove)
        print(aptlists)
        if clean == "1":
            aptclean()
            print("apt cache files cleared", file=sys.stdout)
        if autoremove == "1":
            removeauto()
        if aptlists == "1":
            rmtree("/var/lib/apt/lists/", ignore_errors=True)
            subupdate()

    def set_source_state(state, line, file_path):
        print("{}\n\nold: {}\n".format(file_path, line))
        sources = aptsourceslist.SourcesList()
        for source in sources.list:
            try:
                if source.line.strip() == line and source.file == file_path:
                    source.set_enabled(state == "1")
                    print("new: {}\n".format(source.line.strip()))
                    break
            except Exception as e:
                print("{}".format(e))
                continue
        sources.save()

        print(_("Package Manager Cache is updating, please wait..."))
        print("")
        subupdate()

    def fix_sources(slist_content, fix_slistd, slistd_remove, configure_state, fixbroken_state):
        print("{}:\n\n{}".format(_("New Sources List"), slist_content))
        print("{}: {}\n".format(_("Fix sources.list.d"), fix_slistd))
        if fix_slistd == "1":
            print("{}: {}\n".format(_("Sources List Dir Remove"), slistd_remove))
        print("{}: {}\n".format(_("DPKG Configure State"), configure_state))
        print("{}: {}\n".format(_("Fix Broken State"), fixbroken_state))

        if fix_slistd == "1":
            sourceslistd_dir = "/etc/apt/sources.list.d"
            if os.path.isdir(sourceslistd_dir):
                if slistd_remove == "0":
                    sources = aptsourceslist.SourcesList()
                    for source in sources.list:
                        try:
                            source.set_enabled(False)
                        except Exception as e:
                            print("{}".format(e))
                            continue
                    sources.save()
                elif slistd_remove == "1":
                    try:
                        rmtree(sourceslistd_dir, ignore_errors=True)
                        Path(sourceslistd_dir).mkdir(parents=True, exist_ok=True)
                    except Exception as e:
                        print("{}".format(e))
        else:
            print(_("sources.list.d fix skipped per user request."))


        sources_list_file = open("/etc/apt/sources.list", "w")
        sources_list_file.write("{}\n### This section generated by Pardus Update at {} ###\n".format(
            slist_content, str(datetime.now())))
        sources_list_file.flush()
        sources_list_file.close()

        rmtree("/var/lib/apt/lists/", ignore_errors=True)
        aptclean()
        print(_("Package Manager Cache is updating, please wait..."))
        print("")
        subupdate()

        if configure_state == "1":
            dpkgconfigure()
        else:
            print(_("dpkgconfigure skipped per user request."))

        if fixbroken_state == "1":
            fixbroken()
        else:
            print(_("fixbroken skipped per user request."))


    if len(sys.argv) > 1:
        if sys.argv[1] == "upgrade":
            subupdate()
            subupgrade(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None)
        elif sys.argv[1] == "removeresidual":
            removeresidual(sys.argv[2])
        elif sys.argv[1] == "removeauto":
            removeauto()
        elif sys.argv[1] == "controldistupgrade":
            aptclean()
            controldistupgrade(sys.argv[2])
        elif sys.argv[1] == "downupgrade":
            downupgrade(sys.argv[2])
        elif sys.argv[1] == "distupgrade":
            distupgrade(sys.argv[2])
        elif sys.argv[1] == "distupgradeoffline":
            distupgradeoffline(sys.argv[2], sys.argv[3])
        elif sys.argv[1] == "dpkgconfigure":
            dpkgconfigure()
        elif sys.argv[1] == "aptclear":
            aptclear(sys.argv[2], sys.argv[3], sys.argv[4])
        elif sys.argv[1] == "setsourcestate":
            set_source_state(sys.argv[2], sys.argv[3], sys.argv[4])
        elif sys.argv[1] == "fixsources":
            fix_sources(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6])
        else:
            print("unknown argument error")
    else:
        print("no argument passed")


if __name__ == "__main__":
    main()
