"""Stand-ins for Windows Credential Manager used by the credential tests."""

from __future__ import annotations

from silverestimate.security import credential_store
from silverestimate.security.windows_vault import LOCAL_MACHINE, ROAMING, VaultEntry

SERVICE = credential_store.SERVICE_NAME
DEVICE = credential_store._ENTRIES["device_binding"]


class TwinVault:
    """Credential Manager's two stores, as measured on Windows 11.

    A name can hold one copy in each store. Writing or deleting in a store
    brings that store's copies into view for every name, and a read or delete
    acts on the copy in view. Other programs' writes switch the view too.
    """

    def __init__(self):
        self.stores = {LOCAL_MACHINE: {}, ROAMING: {}}
        self.view = {}
        self.clock = 0
        self.calls = 0
        self.fail_at = None
        self.interfere_at = {}

    def _call(self):
        self.calls += 1
        if self.calls == self.fail_at:
            raise OSError("simulated failure")
        if self.calls in self.interfere_at:
            self.other_program_writes(self.interfere_at[self.calls])

    def other_program_writes(self, persist):
        for target in self.stores[persist]:
            self.view[target] = persist

    def restart(self, first, second):
        """Forget what was in view, as after signing in again."""
        self.view = {}
        self.other_program_writes(first)
        self.other_program_writes(second)

    def read(self, target):
        self._call()
        persist = self.view.get(target)
        return self.stores[persist][target] if persist else None

    def write(self, target, user_name, secret, persist):
        self._call()
        self.clock += 1
        self.stores[persist][target] = VaultEntry(
            user_name, secret, persist, self.clock
        )
        self.other_program_writes(persist)

    def delete(self, target):
        self._call()
        persist = self.view.pop(target, None)
        if persist is None:
            return False
        del self.stores[persist][target]
        self.other_program_writes(persist)
        return True

    def copies(self, target):
        return [store[target] for store in self.stores.values() if target in store]

    def newest(self, entry):
        """The value written last for ``entry`` among every copy still stored."""
        found = [
            copy
            for target in (SERVICE, f"{entry}@{SERVICE}")
            for copy in self.copies(target)
            if copy.user_name == entry
        ]
        return max(found, key=lambda copy: copy.last_written).secret if found else None


class KeyringLayout:
    """How versions built on the keyring package read and wrote the vault."""

    def __init__(self, vault):
        self.vault = vault

    def get(self, entry):
        found = self.vault.read(SERVICE)
        if found is None or found.user_name != entry:
            found = self.vault.read(f"{entry}@{SERVICE}")
        return found.secret if found else None

    def set(self, entry, value):
        persist = LOCAL_MACHINE if entry == DEVICE else ROAMING
        shared = self.vault.read(SERVICE)
        if shared is not None:
            self.vault.write(
                f"{shared.user_name}@{SERVICE}",
                shared.user_name,
                shared.secret,
                persist,
            )
        self.vault.write(SERVICE, entry, value, persist)

    def delete(self, entry):
        for target in (SERVICE, f"{entry}@{SERVICE}"):
            found = self.vault.read(target)
            if found is not None and found.user_name == entry:
                self.vault.delete(target)
