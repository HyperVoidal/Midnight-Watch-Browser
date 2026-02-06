#!/bin/bash
sudo pacman -S --needed pyside6 qt6-webengine cmake base-devel
python -m venv --system-site-packages venv
source venv/bin/activate
pip install -r requirements.txt