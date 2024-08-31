#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Sep 18 14:53:00 2020

@author: fatih
"""

import locale
import os
import re
import subprocess
import time

import apt
import apt_pkg
from aptsources import sourceslist as aptsourceslist
from gi.repository import Gio, GLib


class Package(object):
    def __init__(self):
        self.apps = []
        self.secs = []
        self.sections = []
        self.update_cache_error_msg = ""

    def updatecache(self):
        try:
            self.cache = apt.Cache()
            self.cache.open()
        except:
            return False
        if self.cache.broken_count > 0:
            return False
        return True

    def getApps(self):
        for mypkg in self.cache:
            name = mypkg.name
            try:
                section = mypkg.candidate.section.lower()
            except:
                section = mypkg.versions[0].section.lower()
            self.apps.append({"name": name, "category": section})

    def control_dpkg_interrupt(self):
        return self.cache.dpkg_journal_dirty

    def controlPackageCache(self, packagename):
        try:
            self.cache[packagename]
        except:
            return False
        return True

    def isinstalled(self, packagename):
        try:
            package = self.cache[packagename]
        except:
            return None
        return package.is_installed

    def missingdeps(self, packagename):
        package = self.cache[packagename]
        for rd in package.candidate.get_dependencies("Depends"):
            if not rd.installed_target_versions:
                return True
                break
        return False

    def get_depends(self, packagename):
        dependencies = []
        try:
            package = self.cache[packagename]
            for dependency in package.candidate.dependencies:
                for dep in dependency:
                    if dep.relation in ["=", ">=", ">"]:
                        dep_require_version = dep.version
                        dep_installed_version = dep.installed_target_versions[0].version if dep.installed_target_versions else ""
                        if dep_require_version != "" and dep_installed_version != "":
                            compare = apt_pkg.version_compare(dep_installed_version, dep_require_version)
                            print("depend:{} | u:{} | r:{} | c:{}".format(
                                dep.name, dep_installed_version, dep_require_version, compare))
                            if compare >= 0:
                                print("skip depend", dep.name)
                                continue
                    dependencies.append(dep.name)
        except Exception as e:
            print("Error in get_depends: {}".format(e))
        return dependencies

    def get_rdepends(self, packagename, only_upgradable=False):
        rdependencies = []
        try:
            for pkg in self.cache:
                if only_upgradable:
                    if pkg.marked_upgrade or pkg.marked_install:
                        for depend in pkg.candidate.get_dependencies("Depends"):
                            for dep in depend:
                                if packagename == dep.name:
                                    if dep.relation in ["=", ">=", ">"]:
                                        dep_require_version = dep.version
                                        pkg_installed_version = pkg.installed.version if pkg.is_installed else ""
                                        if dep_require_version != "" and pkg_installed_version != "":
                                            compare = apt_pkg.version_compare(pkg_installed_version, dep_require_version)
                                            print("rdepend:{} | u:{} | r:{} | c:{}".format(
                                                pkg.name, pkg_installed_version, dep_require_version, compare))
                                            if compare >= 0:
                                                print("skip rdepend", pkg.name)
                                                continue
                                    rdependencies.append(pkg.name)
                else:
                    for depend in pkg.candidate.get_dependencies("Depends"):
                        for dep in depend:
                            if packagename == dep.name:
                                if dep.relation in ["=", ">=", ">"]:
                                    dep_require_version = dep.version
                                    pkg_installed_version = pkg.installed.version if pkg.is_installed else ""
                                    if dep_require_version != "" and pkg_installed_version != "":
                                        compare = apt_pkg.version_compare(pkg_installed_version, dep_require_version)
                                        print("rdepend:{} | u:{} | r:{} | c:{}".format(
                                            pkg.name, pkg_installed_version, dep_require_version, compare))
                                        if compare >= 0:
                                            print("skip rdepend", pkg.name)
                                            continue
                                rdependencies.append(pkg.name)
        except Exception as e:
            print("Error in get_depends: {}".format(e))
        return rdependencies

    def description(self, packagename, israw):
        try:
            package = self.cache[packagename]
        except:
            return ""
        try:
            if israw:
                desc = package.candidate.raw_description.replace("\n", "")
            else:
                desc = package.candidate.raw_description
        except:
            try:
                if israw:
                    desc = package.versions[0].raw_description.replace("\n", "")
                else:
                    desc = package.versions[0].raw_description
            except:
                desc = "Description is not found"
        return desc

    def adv_description(self, packagename):
        try:
            long_desc = ""
            raw_desc = self.description(packagename, False).split("\n")
            # append a newline to the summary in the first line
            summary = raw_desc[0]
            raw_desc[0] = ""
            long_desc = "%s\n" % summary
            for line in raw_desc:
                tmp = line.strip()
                if tmp == ".":
                    long_desc += "\n"
                else:
                    long_desc += tmp + "\n"
            # do some regular expression magic on the description
            # Add a newline before each bullet
            p = re.compile(r'^(\s|\t)*(\*|0|-)', re.MULTILINE)
            long_desc = p.sub('\n*', long_desc)
            # replace all newlines by spaces
            p = re.compile(r'\n', re.MULTILINE)
            long_desc = p.sub(" ", long_desc)
            # replace all multiple spaces by newlines
            p = re.compile(r'\s\s+', re.MULTILINE)
            long_desc = p.sub("\n", long_desc)
            long_desc = long_desc.rstrip("\n")
            return long_desc
        except:
            return self.description(packagename, False)

    def summary(self, packagename):
        # Return the short description (one line summary)
        package = self.cache.get(packagename)
        if package is None: return ""
        try:
            return package.candidate.summary
        except AttributeError:
            sum = package.versions.get(0)
        return sum.summary if hasattr(sum, "summary") else "Summary is not found"

    def candidate_version(self, packagename):
        package = self.cache[packagename]
        try:
            version = package.candidate.version
        except:
            try:
                version = package.versions[0].version
            except:
                version = ""
        return version

    def installed_version(self, packagename):
        try:
            package = self.cache[packagename]
        except:
            return None
        try:
            version = package.installed.version
        except:
            version = ""
        return version

    def size(self, packagename):
        package = self.cache[packagename]
        try:
            size = package.candidate.size
        except:
            try:
                size = package.versions[0].size
            except:
                size = ""
        return self.beauty_size(size)

    def get_records(self, packagename):
        try:
            package = self.cache[packagename]
        except:
            return "", "", ""
        try:
            maintainer = package.candidate.record["Maintainer"]
        except:
            try:
                maintainer = package.versions[0].record["Maintainer"]
            except:
                maintainer = ""
        try:
            homepage = package.candidate.record["Homepage"]
        except:
            try:
                homepage = package.versions[0].record["Homepage"]
            except:
                homepage = ""
        try:
            arch = package.candidate.record["Architecture"]
        except:
            try:
                arch = package.versions[0].record["Architecture"]
            except:
                arch = ""
        try:
            maintainer_name = maintainer.split(" <")[0]
        except:
            maintainer_name = ""
        try:
            maintainer_mail = maintainer.split(" <")[1].replace(">", "")
        except:
            maintainer_mail = ""

        return maintainer_name, maintainer_mail, homepage, arch

    def get_uri(self, packagename):
        package = self.cache[packagename]
        try:
            package_uri = package.candidate.uri
            package_downloadable = package.candidate.downloadable
        except:
            try:
                package_uri = package.versions[0].uri
                package_downloadable = package.versions[0].downloadable
            except:
                package_uri = ""
                package_downloadable = False
        return package_downloadable, package_uri

    def get_section(self, packagename):
        section = ""
        try:
            package = self.cache[packagename]
        except:
            return section
        try:
            section = package.candidate.section.lower()
        except:
            section = package.versions[0].section.lower()
        return section

    def required_changes_upgrade(self, sleep=True, keep_list=None):
        if sleep:
            time.sleep(0.25)
        self.cache.clear()
        to_upgrade = []
        to_install = []
        to_delete = []
        to_keep = []
        user_keep_list_depends = []
        changes_available = None
        rcu = {"download_size": None, "freed_size": None, "install_size": None, "to_upgrade": None, "to_install": None,
               "to_delete": None, "to_keep": None, "changes_available": None, "cache_error": True,
               "user_keep_list_depends": None}

        try:
            self.cache.upgrade(True)
            cache_error = False
            self.update_cache_error_msg = ""
        except Exception as error:
            print("cache.upgrade Error: {}".format(error))
            self.update_cache_error_msg = "{}".format(error)
            return rcu

        if keep_list:
            for kp in keep_list:
                try:
                    self.cache[kp].mark_keep()
                    print("keeping: {}".format(kp))
                    depends = self.get_depends(kp)
                    rdepends = self.get_rdepends(kp, True)
                    keep_depends = depends + rdepends
                    print("keep_depends_list: {}".format(depends))
                    print("keep_rdepends_list: {}".format(rdepends))
                    for kd in keep_depends:
                        try:
                            if self.cache[kd].marked_upgrade or self.cache[kd].marked_install:
                                self.cache[kd].mark_keep()
                                user_keep_list_depends.append(kd)
                                print("keeping from depends: {}".format(kd))
                        except:
                            continue
                except Exception as e:
                    print("{} not found".format(kp))
                    print("{}".format(e))


        # to_keep = self.cache.keep_count
        changes = self.cache.get_changes()
        # print(changes)
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

        download_size = self.cache.required_download
        space = self.cache.required_space
        if space < 0:
            freed_size = space * -1
            install_size = 0
        else:
            freed_size = 0
            install_size = space

        if self.cache.keep_count > 0:
            upgradable_cache_packages = [pkg.name for pkg in self.cache if pkg.is_upgradable]
            upgradable_changes_packages = [pkg.name for pkg in changes if pkg.is_upgradable]
            to_keep = list(set(upgradable_cache_packages).difference(set(upgradable_changes_packages)))

        to_upgrade = sorted(to_upgrade)
        to_install = sorted(to_install)
        to_delete = sorted(to_delete)
        to_keep = sorted(to_keep)

        rcu["download_size"] = download_size
        rcu["freed_size"] = freed_size
        rcu["install_size"] = install_size
        rcu["to_upgrade"] = to_upgrade
        rcu["to_install"] = to_install
        rcu["to_delete"] = to_delete
        rcu["to_keep"] = to_keep
        rcu["changes_available"] = changes_available
        rcu["cache_error"] = cache_error
        rcu["user_keep_list_depends"] = user_keep_list_depends

        # print("freed_size {}".format(rcu["freed_size"]))
        # print("download_size {}".format(rcu["download_size"]))
        # print("install_size {}".format(rcu["install_size"]))
        print("to_upgrade {}".format(rcu["to_upgrade"]))
        print("to_install {}".format(rcu["to_install"]))
        print("to_delete {}".format(rcu["to_delete"]))
        print("to_keep {}".format(rcu["to_keep"]))
        print("changes_available {}".format(rcu["changes_available"]))
        print("cache_error {}".format(rcu["cache_error"]))
        print("user_keep_list_depends {}".format(rcu["user_keep_list_depends"]))
        return rcu

    def required_changes_autoremove(self, packages, sleep=True):
        if sleep:
            time.sleep(0.25)
        self.cache.clear()
        to_install = []
        to_delete = []
        broken = []
        package_broken = None
        ret = {"download_size": 0, "freed_size": 0, "install_size": 0, "to_install": None, "to_delete": None,
               "broken": None, "package_broken": None}

        for packagename in packages:
            try:
                package = self.cache[packagename]
            except Exception as e:
                print("{}".format(e))
                return ret
            try:
                if package.is_installed:
                    package.mark_delete(True, True)
                else:
                    package.mark_install(True, True)

            except:
                if packagename not in broken:
                    broken.append(packagename)
            changes = self.cache.get_changes()
            if changes:
                package_broken = False
                for package in changes:
                    if package.marked_install:
                        if package.name not in to_install:
                            to_install.append(package.name)
                    elif package.marked_delete:
                        if package.name not in to_delete:
                            to_delete.append(package.name)
            else:
                package_broken = True

        download_size = self.cache.required_download
        space = self.cache.required_space
        if space < 0:
            freed_size = space * -1
            install_size = 0
        else:
            freed_size = 0
            install_size = space

        ret["download_size"] = download_size
        ret["freed_size"] = freed_size
        ret["install_size"] = install_size
        ret["to_install"] = to_install
        ret["to_delete"] = to_delete
        ret["broken"] = broken
        ret["package_broken"] = package_broken

        # print("freed_size {}".format(ret["freed_size"]))
        # print("download_size {}".format(ret["download_size"]))
        # print("install_size {}".format(ret["install_size"]))
        # print("to_install {}".format(ret["to_install"]))
        # print("to_delete {}".format(ret["to_delete"]))

        return ret

    def myapps_remove_details(self, desktopname):
        # self.updatecache()
        try:
            process = subprocess.run(["dpkg", "-S", desktopname], stdout=subprocess.PIPE)
            output = process.stdout.decode("utf-8")
            package = output[:output.find(":")].split(",")[0]
            if package:
                return True, self.required_changes(package, sleep=False), package
            else:
                # try get package name from basename
                process = subprocess.run(["dpkg", "-S", os.path.basename(desktopname)], stdout=subprocess.PIPE)
                output = process.stdout.decode("utf-8")
                package = output[:output.find(":")].split(",")[0]
                if package:
                    return True, self.required_changes(package, sleep=False), package
                else:
                    return False, None, ""
        except Exception as e:
            print("Error on myapps_remove_details: {}".format(e))
            return False, None, ""

    def get_appname_from_desktopfile(self, desktopname):
        try:
            process = subprocess.run(["dpkg", "-S", desktopname], stdout=subprocess.PIPE)
            output = process.stdout.decode("utf-8")
            package = output[:output.find(":")].split(",")[0]
            if package:
                return True, package
            else:
                # try get package name from basename
                process = subprocess.run(["dpkg", "-S", os.path.basename(desktopname)], stdout=subprocess.PIPE)
                output = process.stdout.decode("utf-8")
                package = output[:output.find(":")].split(",")[0]
                if package:
                    return True, package
                else:
                    return False, ""
        except Exception as e:
            print("Error on get_appname_from_desktopfile: {}".format(e))
            return False, ""

    def beauty_size(self, size):
        # apt uses MB rather than MiB, so let's stay consistent
        if not isinstance(size, int):
            return "size not found"
        return GLib.format_size(size)

    def get_installed_apps(self):
        apps = []
        for app in Gio.DesktopAppInfo.get_all():

            id = app.get_id()
            name = app.get_name()
            executable = app.get_executable()
            nodisplay = app.get_nodisplay()
            icon = app.get_string('Icon')
            description = app.get_description() or app.get_generic_name() or app.get_name()
            filename = app.get_filename()
            keywords = " ".join(app.get_keywords())

            if executable and not nodisplay:
                apps.append({"id": id, "name": name, "icon": icon, "description": description, "filename": filename,
                             "keywords": keywords, "executable": executable})

        apps = sorted(dict((v['name'], v) for v in apps).values(), key=lambda x: locale.strxfrm(x["name"]))

        return apps

    def parse_desktopfile(self, desktopfilename):
        try:
            app = Gio.DesktopAppInfo.new(desktopfilename)
            if app:
                id = app.get_id()
                name = app.get_name()
                executable = app.get_executable()
                # nodisplay = app.get_nodisplay()
                icon = app.get_string('Icon')
                description = app.get_description() or app.get_generic_name() or app.get_name()
                filename = app.get_filename()
                keywords = " ".join(app.get_keywords())
                return True, {"id": id, "name": name, "icon": icon, "description": description,
                              "filename": filename, "keywords": keywords, "executable": executable}
            else:
                print("parse_desktopfile: {} app not exists".format(desktopfilename))
                return False, None
        except Exception as e:
            print("{}".format(e))
            print("parse_desktopfile: {} app not exists".format(desktopfilename))
            return False, None

    def origins(self, packagename):
        package = self.cache[packagename]
        try:
            component = package.candidate.origins[0]
        except:
            try:
                component = package.versions[0].origins[0]
            except:
                component = None
        return component

    def residual(self):
        residual = []
        try:
            for pkg in self.cache:
                if self.cache[pkg.name].has_config_files and not self.cache[pkg.name].is_installed:
                    residual.append(pkg.name)
        except Exception as e:
            print("Package residual Error: {}".format(e))

        return residual

    def autoremovable(self):
        autoremovable = []
        try:
            for pkg in self.cache:
                if self.cache[pkg.name].is_auto_removable:
                    autoremovable.append(pkg.name)
        except Exception as e:
            print("Package autoremovable Error: {}".format(e))
        return autoremovable

    def upgradable(self):
        upgradable = []
        try:
            for pkg in self.cache:
                if self.cache[pkg.name].is_upgradable:
                    upgradable.append(pkg.name)
            upgradable = sorted(upgradable)
        except Exception as e:
            print("Package upgradable Error: {}".format(e))
        return upgradable

    def upgradable_full(self):
        upgradable = []
        try:
            for pkg in self.cache:
                if self.cache[pkg.name].is_upgradable:
                    upgradable.append({"name": pkg.name, "summary": self.summary(pkg.name)})
            upgradable = sorted(upgradable, key=lambda x: x["name"])
        except Exception as e:
            print("Package upgradable Error: {}".format(e))
        return upgradable

    def get_sources(self):
        repos = {}
        sources = aptsourceslist.SourcesList()
        for source in sources.list:
            if source.invalid:
                continue
            repo = {}
            repo['file'] = source.file
            repo['comps'] = getattr(source, 'comps', [])
            repo['disabled'] = source.disabled
            repo['dist'] = source.dist
            repo['type'] = source.type
            repo['uri'] = source.uri
            repo['line'] = source.line.strip()
            repo['architectures'] = getattr(source, 'architectures', [])
            repos.setdefault(source.uri, []).append(repo)

        return repos

    def versionCompare(self, version1, version2):
        if version2 == "None" or version2 == "" or version2 is None:
            print("user version: {} , server version: {}".format(version1, version2))
            return False
        vc = apt_pkg.version_compare(version1, version2)
        if vc > 0:
            print("user version: {} > server version: {}".format(version1, version2))
        elif vc == 0:
            print("user version: {} == server version: {}".format(version1, version2))
        elif vc < 0:
            print("user version: {} < server version: {}".format(version1, version2))
        return vc
