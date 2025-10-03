#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Sep 18 14:53:00 2020

@author: fatih
"""

import os
import subprocess
import tkinter as tk
from tkinter import messagebox
import subprocess


# import apt

def check_connection():

    try:
        result = subprocess.run(["ping", "-c", "1", "8.8.8.8"], check=True)
    except:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(title="Connection Error", message="There is no active network connection, please connect to network to continue.")
        root.destroy()

def main():
    # try:
    #     cache = apt.Cache()
    #     cache.open()
    #     cache.update()
    # except Exception as e:
    #     print(str(e))
    #     print("using subprocess for apt update")
    subprocess.call(["apt", "update"],
                    env={**os.environ, 'DEBIAN_FRONTEND': 'noninteractive'})


if __name__ == "__main__":
    cehck_connection()
    main()
