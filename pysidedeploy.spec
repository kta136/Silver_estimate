[app]

# title of your application
title = SilverEstimate

# project root directory. default = The parent directory of input_file
project_dir = .

# source file entry point path. default = main.py
input_file = main.py

# directory where the executable output is generated
exec_directory = dist

# path to the project file relative to project_dir
project_file =

# application icon
icon = assets/icons/silverestimate.ico

[python]

# python path
python_path = .venv/Scripts/python.exe

# python packages to install
packages = Nuitka==4.2.1,zstandard==0.25.0

[qt]

# paths to required qml files. comma separated
# normally all the qml files required by the project are added automatically
# design studio projects include the qml files using qt resources
qml_files =

# excluded qml plugin binaries
excluded_qml_plugins =

# qt modules used. comma separated
modules = Core,Gui,Network,PrintSupport,Widgets

# qt plugins used by the application
plugins = iconengines,imageformats,platforms,printsupport,styles,tls

[nuitka]

# usage description for permissions requested by the app as found in the info.plist file
# of the app bundle. comma separated
# eg = extra_args = --show-modules --follow-stdlib
macos.permissions =

# mode of using nuitka. accepts standalone or onefile. default = onefile
mode = onefile

# specify any extra nuitka arguments
extra_args = --quiet --noinclude-qt-translations --msvc=latest --assume-yes-for-downloads --windows-console-mode=attach --include-data-dir=assets=assets --include-data-files=LICENSE=LICENSE --include-data-files=THIRD_PARTY_NOTICES.md=THIRD_PARTY_NOTICES.md --include-data-files=vendor/sqlcipher/PROVENANCE.json=vendor/sqlcipher/PROVENANCE.json --include-module=sqlcipher3.dbapi2 --include-module=sqlcipher3._sqlite3 --noinclude-dlls=*/qicns.dll --noinclude-dlls=*/qpdf.dll --noinclude-dlls=*/qtga.dll --noinclude-dlls=*/qtiff.dll --noinclude-dlls=*/qwbmp.dll --noinclude-dlls=*/qwebp.dll --noinclude-dlls=*/qdirect2d.dll --noinclude-dlls=*/qminimal.dll --noinclude-dlls=*/qoffscreen.dll --noinclude-dlls=*/qcertonlybackend.dll --noinclude-dlls=*/qopensslbackend.dll
