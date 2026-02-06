#!/bin/bash
sudo dnf install python3-pyside6 qt6-qtwebengine cmake gcc-c++
python -m venv --system-site-packages venv
source venv/bin/activate
pip install -r requirements.txt
