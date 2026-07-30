# Developers readme

Developed on windows 11

## Things recommended to install

1. git (https://git-scm.com/install/windows)
1. python (https://www.python.org/downloads/release/pymanager-262/)
1. vscode (https://code.visualstudio.com/download?_exp_download=fb315fc982)
1. vscode extensions: "Python"
1. vscode extensions: "GitLens"
1. vscode extensions: "Black Formatter"

# Configure git
In a terminal:
  git config --global user.email "you@example.com"
  git config --global user.name "Your Name"

## Required python extensions

(just run install-python-stuff.bat from the support folder)

1. pyinstaller (py -m pip install pyinstaller)
1. psutil (py -m pip install psutil)
1. customtkinter (py -m pip install customtkinter)
1. ttkbootstrap (py -m pip install ttkbootstrap)

## Things nice to install

1. vscode extensions: "Markdown Preview"

## Support scripts, in folder support

### build-all.bat

Builds sgsl.exe for release and for test. sgsl is developed in python and converted into an .exe file by [pyInstaller](https://pyinstaller.org/en/stable/)

### build-for-test.bat, build-for-release.bat

Just helpers, don't run directly, run build-all.bat instead.

### install-python-stuff.bat

Installs all the python dependencies

### sgsl-show-what-failed.bat

A wrapper running sgsl-for-test.exe (if found) or sgsl.exe (if not running sgsl-for-test.exe) adding a pause at the end allowing the developer to see any python output.