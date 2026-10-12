# Third-Party Notices

Silver Estimate is distributed under GPL-3.0-only. The complete corresponding
source for each release is published with that release. This notice summarizes
the principal redistributed runtime components; `uv.lock` is the complete
machine-readable inventory of the Python packages.

## apsw-sqlite3mc: APSW, SQLite3 Multiple Ciphers, and SQLite

The encrypted database engine is the `apsw-sqlite3mc` wheel from PyPI.
APSW: copyright Roger Binns, licensed under the zlib license.
SQLite3 Multiple Ciphers: copyright Ulrich Telle, licensed under the MIT
License. SQLite is in the public domain.
Sources and licenses: <https://github.com/utelle/apsw-sqlite3mc>,
<https://github.com/rogerbinns/apsw>, and
<https://github.com/utelle/SQLite3MultipleCiphers>.

## PySide6 6.11.2, Shiboken6 6.11.2, and Qt 6.11.2

Copyright The Qt Company Ltd. and contributors. PySide6 and Shiboken6 are
available under LGPL-3.0-only, GPL-2.0-only, GPL-3.0-only, and commercial
terms; Qt modules retain their applicable GPL/LGPL/commercial terms.
Source and license: <https://code.qt.io/cgit/pyside/pyside-setup.git/> and
<https://doc.qt.io/qt-6/licensing.html>.

## Build tooling: Nuitka 4.1.3 and zstandard 0.25.0

Nuitka is the build compiler used through `pyside6-deploy` and is licensed
under AGPL-3.0-or-later. Its generated target code is covered by the additional
Nuitka Runtime Library Exception. The zstandard Python package is licensed
under BSD-3-Clause. These build packages are not shipped as importable runtime
packages; their applicable generated/runtime code remains governed by the
upstream terms.
Sources and licenses:
<https://github.com/Nuitka/Nuitka/blob/develop/LICENSE.txt>,
<https://github.com/Nuitka/Nuitka/blob/develop/LICENSE-RUNTIME.txt>, and
<https://github.com/indygreg/python-zstandard/blob/main/LICENSE>.

## Python, argon2-cffi, and other packages

These components retain their respective upstream licenses and notices. Exact
versions are recorded in `uv.lock`.
Qt/PySide redistribution must continue to satisfy the selected GPL/LGPL terms.
