#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages
import os, subprocess

def create_mo_files():
    podir = "po"
    mo = []
    for po in os.listdir(podir):
        if po.endswith(".po"):
            os.makedirs("{}/{}/LC_MESSAGES".format(podir, po.split(".po")[0]), exist_ok=True)
            mo_file = "{}/{}/LC_MESSAGES/{}".format(podir, po.split(".po")[0], "pardus-update.mo")
            msgfmt_cmd = 'msgfmt {} -o {}'.format(podir + "/" + po, mo_file)
            subprocess.call(msgfmt_cmd, shell=True)
            mo.append(("/usr/share/locale/" + po.split(".po")[0] + "/LC_MESSAGES",
                       ["po/" + po.split(".po")[0] + "/LC_MESSAGES/pardus-update.mo"]))
    return mo


changelog = "debian/changelog"
if os.path.exists(changelog):
    head = open(changelog).readline()
    try:
        version = head.split("(")[1].split(")")[0]
    except:
        print("debian/changelog format is wrong for get version")
        version = "0.0.0"
    f = open("src/__version__", "w")
    f.write(version)
    f.close()

data_files = [
    ("/usr/bin", ["pardus-update"]),
    ("/usr/share/applications",
     ["data/tr.org.pardus.update.desktop"]),
    ("/usr/share/pardus/pardus-update/ui",
     ["ui/MainWindow.glade"]),
    ("/usr/share/pardus/pardus-update/src",
     ["src/AutoAptUpdate.py",
      "src/Main.py",
      "src/MainWindow.py",
      "src/Package.py",
      "src/SysActions.py",
      "src/UserSettings.py",
      "src/__version__"]),
    ("/usr/share/pardus/pardus-update/data",
     ["data/tr.org.pardus.update-autostart.desktop",
      "data/pardus-update.svg",
      "data/pardus-update-available-symbolic.svg",
      "data/pardus-update-error-symbolic.svg",
      "data/pardus-update-inprogress-symbolic.svg",
      "data/pardus-update-symbolic.svg",
      "data/pardus-update-uptodate.svg"]),
    ("/usr/share/polkit-1/actions",
      ["data/tr.org.pardus.pkexec.pardus-update.policy"]),
    ("/etc/skel/.config/autostart",
     ["data/tr.org.pardus.update-autostart.desktop"]),
    ("/usr/share/icons/hicolor/scalable/apps/",
     ["data/pardus-update.svg",
      "data/pardus-update-available-symbolic.svg",
      "data/pardus-update-error-symbolic.svg",
      "data/pardus-update-inprogress-symbolic.svg",
      "data/pardus-update-symbolic.svg",
      "data/pardus-update-uptodate.svg"])
] + create_mo_files()

setup(
    name="pardus-update",
    version=version,
    packages=find_packages(),
    scripts=["pardus-update"],
    install_requires=["PyGObject"],
    data_files=data_files,
    author="Fatih Altun",
    author_email="fatih.altun@pardus.org.tr",
    description="Pardus Update application",
    license="GPLv3",
    keywords="pardus-update, update, upgrade, apt",
    url="https://github.com/pardus/pardus-update",
)
