"""Generic Windows Credential Manager entries through the Win32 API.

Windows keeps two stores for these entries: one that roams with the user's
profile and one that stays on this PC. A name may have a copy in each. Reading
or deleting a name acts on the copy in whichever store was written to last, by
any program, so a name must be kept in a single store to behave predictably.
"""

from __future__ import annotations

import ctypes
import sys
from dataclasses import dataclass
from typing import Protocol

LOCAL_MACHINE = 2
ROAMING = 3

_CRED_TYPE_GENERIC = 1
_ERROR_NOT_FOUND = 1168
_COMMENT = "Stored by Silver Estimate"


@dataclass(frozen=True)
class VaultEntry:
    """One copy of a stored credential."""

    user_name: str
    secret: str
    persist: int
    last_written: int


class Vault(Protocol):
    """The three operations the credential store needs."""

    def read(self, target: str) -> VaultEntry | None: ...

    def write(self, target: str, user_name: str, secret: str, persist: int) -> None: ...

    def delete(self, target: str) -> bool: ...


def _decode(blob: bytes) -> str:
    # Entries are UTF-16, as the keyring package wrote them before this module.
    try:
        return blob.decode("utf-16")
    except UnicodeDecodeError:
        return blob.decode("utf-8")


if sys.platform == "win32":
    from ctypes import wintypes

    class _Credential(ctypes.Structure):
        _fields_ = [
            ("Flags", wintypes.DWORD),
            ("Type", wintypes.DWORD),
            ("TargetName", wintypes.LPWSTR),
            ("Comment", wintypes.LPWSTR),
            ("LastWritten", wintypes.FILETIME),
            ("CredentialBlobSize", wintypes.DWORD),
            ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
            ("Persist", wintypes.DWORD),
            ("AttributeCount", wintypes.DWORD),
            ("Attributes", ctypes.c_void_p),
            ("TargetAlias", wintypes.LPWSTR),
            ("UserName", wintypes.LPWSTR),
        ]

    class _WindowsVault:
        def __init__(self) -> None:
            api = ctypes.WinDLL("advapi32", use_last_error=True)
            self._read = api.CredReadW
            self._read.argtypes = [
                wintypes.LPCWSTR,
                wintypes.DWORD,
                wintypes.DWORD,
                ctypes.POINTER(ctypes.POINTER(_Credential)),
            ]
            self._read.restype = wintypes.BOOL
            self._write = api.CredWriteW
            self._write.argtypes = [ctypes.POINTER(_Credential), wintypes.DWORD]
            self._write.restype = wintypes.BOOL
            self._delete = api.CredDeleteW
            self._delete.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
            self._delete.restype = wintypes.BOOL
            self._free = api.CredFree
            self._free.argtypes = [ctypes.c_void_p]
            self._free.restype = None

        def read(self, target: str) -> VaultEntry | None:
            found = ctypes.POINTER(_Credential)()
            if not self._read(target, _CRED_TYPE_GENERIC, 0, ctypes.byref(found)):
                if ctypes.get_last_error() == _ERROR_NOT_FOUND:
                    return None
                raise ctypes.WinError(ctypes.get_last_error())
            try:
                credential = found.contents
                blob = ctypes.string_at(
                    credential.CredentialBlob, credential.CredentialBlobSize
                )
                written = credential.LastWritten
                return VaultEntry(
                    user_name=credential.UserName or "",
                    secret=_decode(blob),
                    persist=int(credential.Persist),
                    last_written=(written.dwHighDateTime << 32) | written.dwLowDateTime,
                )
            finally:
                self._free(found)

        def write(self, target: str, user_name: str, secret: str, persist: int) -> None:
            blob = secret.encode("utf-16-le")
            buffer = (ctypes.c_ubyte * len(blob)).from_buffer_copy(blob)
            credential = _Credential()
            credential.Type = _CRED_TYPE_GENERIC
            credential.TargetName = target
            credential.Comment = _COMMENT
            credential.CredentialBlobSize = len(blob)
            credential.CredentialBlob = ctypes.cast(
                buffer, ctypes.POINTER(ctypes.c_ubyte)
            )
            credential.Persist = persist
            credential.UserName = user_name
            if not self._write(ctypes.byref(credential), 0):
                raise ctypes.WinError(ctypes.get_last_error())

        def delete(self, target: str) -> bool:
            if self._delete(target, _CRED_TYPE_GENERIC, 0):
                return True
            if ctypes.get_last_error() == _ERROR_NOT_FOUND:
                return False
            raise ctypes.WinError(ctypes.get_last_error())

    def load_vault() -> Vault | None:
        """Return the Windows vault."""
        return _WindowsVault()

else:

    def load_vault() -> Vault | None:
        """Return ``None``: this vault exists only on Windows."""
        return None
