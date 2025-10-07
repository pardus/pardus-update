#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Sep 18 14:53:00 2020

@author: fatih
"""

import os
import subprocess


# import apt

def main():
    # try:
    #     cache = apt.Cache()
    #     cache.open()
    #     cache.update()
    # except Exception as e:
    #     print(str(e))
    #     print("using subprocess for apt update")
    subprocess.call(["apt", "update"],
                    env={**os.environ,
                         'DEBIAN_FRONTEND': 'noninteractive',
                         'LC_ALL': 'C'})


if __name__ == "__main__":
    main()
