# Pardus Update

Pardus Update is a simple update application for debian based operating systems.

It is currently a work in progress. Maintenance is done by <a href="https://www.pardus.org.tr/">Pardus</a> team.

[![Packaging status](https://repology.org/badge/vertical-allrepos/pardus-update.svg)](https://repology.org/project/pardus-update/versions)

### **Dependencies**

This application is developed based on Python3 and GTK+ 3. Dependencies:
```bash
gir1.2-glib-2.0 gir1.2-gtk-3.0 gir1.2-notify-0.7 gir1.2-soup-2.4 gir1.2-vte-2.91 gir1.2-ayatanaappindicator3-0.1 python3-apt python3-distro
```

### **Run Application from Source**

Install dependencies
```bash
sudo apt gir1.2-glib-2.0 gir1.2-gtk-3.0 gir1.2-notify-0.7 gir1.2-soup-2.4 gir1.2-vte-2.91 gir1.2-ayatanaappindicator3-0.1 python3-apt python3-distro
```
Clone the repository
```bash
git clone https://github.com/pardus/pardus-update.git ~/pardus-update
```
Run application
```bash
python3 ~/pardus-update/src/Main.py
```

### **Build deb package**

```bash
sudo apt install devscripts git-buildpackage
sudo mk-build-deps -ir
gbp buildpackage --git-export-dir=/tmp/build/pardus-update -us -uc
```

### Running Tests
This project uses pytest for testing.

1.  **Install development dependencies:**
    Make sure you have Python 3 and pip installed. It's recommended to use a virtual environment.
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate  # On Windows use `.venv\Scriptsctivate`
    pip install -r requirements-dev.txt
    ```

2.  **Run tests:**
    From the root directory of the project, run:
    ```bash
    pytest
    ```
    Or, to ensure it uses the project's Python environment correctly:
    ```bash
    python -m pytest
    ```

### **Screenshots**

![Pardus Update 1](screenshots/pardus-update-1.png)

![Pardus Update 2](screenshots/pardus-update-2.png)
