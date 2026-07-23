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
packages = Nuitka==4.1.3,zstandard==0.25.0

# buildozer = for deploying Android application
android_packages = buildozer==1.5.0,cython==0.29.33

[qt]

# paths to required qml files. comma separated
# normally all the qml files required by the project are added automatically
# design studio projects include the qml files using qt resources
qml_files =

# excluded qml plugin binaries
excluded_qml_plugins =

# qt modules used. comma separated
modules = Core,Gui,PrintSupport,Widgets

# qt plugins used by the application. only relevant for desktop deployment
# for qt plugins used in android application see [android][plugins]
plugins = iconengines,imageformats,platforms,printsupport,styles

[android]

# path to pyside wheel
wheel_pyside =

# path to shiboken wheel
wheel_shiboken =

# plugins to be copied to libs folder of the packaged application. comma separated
plugins =

[nuitka]

# usage description for permissions requested by the app as found in the info.plist file
# of the app bundle. comma separated
# eg = extra_args = --show-modules --follow-stdlib
macos.permissions =

# mode of using nuitka. accepts standalone or onefile. default = onefile
mode = onefile

# specify any extra nuitka arguments
extra_args = --quiet --noinclude-qt-translations --zig --assume-yes-for-downloads --windows-console-mode=disable --include-data-dir=assets=assets --include-data-files=LICENSE=LICENSE --include-data-files=THIRD_PARTY_NOTICES.md=THIRD_PARTY_NOTICES.md --include-data-files=vendor/sqlcipher/PROVENANCE.json=vendor/sqlcipher/PROVENANCE.json --include-module=passlib.handlers.argon2 --include-module=keyring.backends.Windows --include-module=keyring.backends.fail --include-module=keyring.backends.null --include-module=sqlcipher3.dbapi2 --include-module=sqlcipher3._sqlite3 --noinclude-dlls=*/qicns.dll --noinclude-dlls=*/qpdf.dll --noinclude-dlls=*/qtga.dll --noinclude-dlls=*/qtiff.dll --noinclude-dlls=*/qwbmp.dll --noinclude-dlls=*/qwebp.dll --noinclude-dlls=*/qdirect2d.dll --noinclude-dlls=*/qminimal.dll --noinclude-dlls=*/qoffscreen.dll --noinclude-dlls=*/qcertonlybackend.dll --noinclude-dlls=*/qopensslbackend.dll --noinclude-dlls=*/qschannelbackend.dll --report=artifacts/pyside6-deploy/nuitka-report.xml

[buildozer]

# build mode
# possible values = ["aarch64", "armv7a", "i686", "x86_64"]
# release creates a .aab, while debug creates a .apk
mode = debug

# path to pyside6 and shiboken6 recipe dir
recipe_dir =

# path to extra qt android .jar files to be loaded by the application
jars_dir =

# if empty, uses default ndk path downloaded by buildozer
ndk_path =

# if empty, uses default sdk path downloaded by buildozer
sdk_path =

# other libraries to be loaded at app startup. comma separated.
local_libs =

# architecture of deployed platform
arch =
