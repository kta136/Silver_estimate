# Third-Party Notices

Silver Estimate is distributed under GPL-3.0-only. The complete corresponding
source for each release is published with that release. This notice summarizes
the principal redistributed runtime components; the release SBOM is the complete
machine-readable inventory.

## SQLCipher Community Edition 4.17.0

Copyright Zetetic LLC and contributors. Licensed under a BSD-style license.
Pinned tag object: `f9788efa8ac4dfed75c03e4756b1666a1d0845da`;
peeled commit: `810db22f575ee7cf94ea96a3e91622b5fcece3dc`.
Source and license: <https://github.com/sqlcipher/sqlcipher>.

## sqlcipher3 0.6.2

Copyright Charles Leifer and contributors. Licensed under the MIT License.
Pinned source revision: `14fc2632676b20011e0bba64fdda49763a2dd2ec`.
Source and license: <https://github.com/coleifer/sqlcipher3>.

## OpenSSL 3.6.0

Copyright The OpenSSL Project Authors. Licensed under Apache-2.0.
Pinned tag object: `f52b9f81a985dc1e45b28cd7b5671feb32815b83`;
peeled commit: `7b371d80d959ec9ab4139d09d78e83c090de9779`.
Source and license: <https://github.com/openssl/openssl>.

## PySide6 6.11.1, Shiboken6 6.11.1, and Qt 6.11.1

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

## Python, cryptography, argon2-cffi, keyring, and other packages

These components retain their respective upstream licenses and notices. Exact
versions and license identifiers are recorded in the release CycloneDX SBOM.
Qt/PySide redistribution must continue to satisfy the selected GPL/LGPL terms.
