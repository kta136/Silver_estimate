import sys

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from silverestimate.security import credential_store
from silverestimate.security.credential_store import CredentialStoreError
from silverestimate.security.windows_vault import (
    LOCAL_MACHINE,
    ROAMING,
    load_vault,
)
from tests.vault_support import KeyringLayout, TwinVault

SERVICE = credential_store.SERVICE_NAME
ENTRIES = credential_store._ENTRIES
DEVICE = ENTRIES["device_binding"]


def use(monkeypatch, vault):
    monkeypatch.setattr(credential_store, "vault", vault)
    return vault


@pytest.fixture()
def vault(monkeypatch):
    return use(monkeypatch, TwinVault())


def stored_values():
    return {
        kind: credential_store.get_password_hash(kind)
        for kind in credential_store.SUPPORTED_CREDENTIAL_KINDS
    }


CHECK = f"layout-check@{SERVICE}"
LAYOUT = f"layout@{SERVICE}"


def stored_entries(vault):
    """What each store holds, apart from the record that the layout was checked."""
    return {
        persist: {target: copy for target, copy in store.items() if target != LAYOUT}
        for persist, store in vault.stores.items()
    }


def assert_tidy(vault, *, check_entry_may_remain=False):
    """Every entry is one local copy under its own name, and nothing else is left."""
    ignored = {CHECK} if check_entry_may_remain else set()
    stored = stored_entries(vault)
    assert set(stored[ROAMING]) <= ignored
    for target, copy in stored[LOCAL_MACHINE].items():
        if target in ignored:
            continue
        assert target == f"{copy.user_name}@{SERVICE}"
        assert copy.user_name in ENTRIES.values()


def settle(vault, expected):
    """Read everything again with each store in view, as happens over time."""
    for in_view in (LOCAL_MACHINE, ROAMING):
        vault.other_program_writes(in_view)
        assert stored_values() == expected


def an_installation_with_a_changed_password(vault):
    """First run, a restart, then a password change, as the keyring layout stored it.

    The device secret is reasserted at each start while another program has
    brought the local store into view, the case that left a superseded hash.
    """
    old = KeyringLayout(vault)
    old.set(ENTRIES["main"], "main-1")
    old.set(ENTRIES["backup"], "backup-1")
    old.set(DEVICE, "v1:device")
    for entry, value in (
        ("pending_main", "main-2"),
        ("pending_backup", "backup-2"),
        ("recovery_main", "main-1"),
        ("recovery_backup", "backup-1"),
        ("main", "main-2"),
        ("backup", "backup-2"),
    ):
        old.set(ENTRIES[entry], value)
    for entry in ("pending_main", "pending_backup", "recovery_main", "recovery_backup"):
        old.delete(ENTRIES[entry])
    vault.other_program_writes(LOCAL_MACHINE)
    old.set(DEVICE, "v1:device")
    return {
        "main": "main-2",
        "backup": "backup-2",
        "pending_main": None,
        "pending_backup": None,
        "recovery_main": None,
        "recovery_backup": None,
        "device_binding": "v1:device",
    }


def test_backend_status_reports_missing_vault(monkeypatch):
    use(monkeypatch, None)

    status = credential_store.get_backend_status()

    assert status.available is False
    assert status.backend_name == "missing"


def test_backend_status_names_windows_credential_manager(vault):
    status = credential_store.get_backend_status()

    assert status.available is True
    assert status.backend_name == "Windows Credential Manager"


def test_backend_status_reports_a_vault_that_does_not_answer(vault):
    vault.fail_at = 1

    status = credential_store.get_backend_status()

    assert status.available is False
    assert "did not respond" in status.reason


def test_reads_and_writes_fail_fast_without_a_vault(monkeypatch):
    use(monkeypatch, None)

    with pytest.raises(CredentialStoreError):
        credential_store.get_password_hash("main")
    with pytest.raises(CredentialStoreError):
        credential_store.set_password_hash("main", "hash")
    credential_store.delete_password_hash("main")


@pytest.mark.parametrize("kind", credential_store.SUPPORTED_CREDENTIAL_KINDS)
def test_every_credential_kind_round_trips_through_the_vault(vault, kind):
    credential_store.set_password_hash(kind, "hash")
    assert credential_store.get_password_hash(kind) == "hash"

    credential_store.delete_password_hash(kind)

    assert credential_store.get_password_hash(kind) is None
    assert stored_entries(vault) == {LOCAL_MACHINE: {}, ROAMING: {}}


def test_each_entry_is_one_local_copy_under_its_own_name(vault):
    for kind in credential_store.SUPPORTED_CREDENTIAL_KINDS:
        credential_store.set_password_hash(kind, f"{kind}-hash")
        credential_store.set_password_hash(kind, f"{kind}-hash-2")

    assert_tidy(vault)
    assert set(stored_entries(vault)[LOCAL_MACHINE]) == {
        f"{entry}@{SERVICE}" for entry in ENTRIES.values()
    }
    for kind in credential_store.SUPPORTED_CREDENTIAL_KINDS:
        assert credential_store.get_password_hash(kind) == f"{kind}-hash-2"


def test_unknown_credential_kind_is_rejected_before_vault_access():
    with pytest.raises(ValueError, match="Unknown credential kind"):
        credential_store.get_password_hash("unknown")


def test_vault_failures_surface_as_credential_store_errors(vault):
    for call, message in (
        (credential_store.get_password_hash, "Failed to read credential"),
        (lambda kind: credential_store.set_password_hash(kind, "h"), "Failed to store"),
        (credential_store.delete_password_hash, "Failed to delete credential"),
    ):
        vault.fail_at = vault.calls + 1
        with pytest.raises(CredentialStoreError, match=message):
            call("main")


def test_device_binding_secret_is_stable_and_deletable(vault):
    first = credential_store.create_device_binding_secret()
    second = credential_store.create_device_binding_secret()

    assert first == second
    assert len(first) == 32
    assert vault.stores[LOCAL_MACHINE][f"{DEVICE}@{SERVICE}"].persist == LOCAL_MACHINE
    credential_store.delete_password_hash("device_binding")
    assert credential_store.get_device_binding_secret() is None


def test_the_keyring_layout_could_return_a_superseded_hash(vault):
    """The defect this store removes: the answer depended on other programs."""
    expected = an_installation_with_a_changed_password(vault)
    old = KeyringLayout(vault)

    vault.other_program_writes(ROAMING)
    assert old.get(ENTRIES["backup"]) == expected["backup"]
    vault.other_program_writes(LOCAL_MACHINE)
    assert old.get(ENTRIES["backup"]) == "backup-1"


@pytest.mark.parametrize("in_view", [LOCAL_MACHINE, ROAMING])
def test_an_existing_installation_keeps_its_current_values(vault, in_view):
    expected = an_installation_with_a_changed_password(vault)
    vault.other_program_writes(in_view)

    assert stored_values() == expected
    assert_tidy(vault)
    for switched in (ROAMING, LOCAL_MACHINE):
        vault.other_program_writes(switched)
        assert stored_values() == expected


def test_tidying_happens_once_per_installation(vault, monkeypatch):
    expected = an_installation_with_a_changed_password(vault)
    credential_store.get_password_hash("main")
    written = vault.clock

    stored_values()
    monkeypatch.setattr(credential_store, "_checked", None)  # the app starts again
    assert stored_values() == expected

    assert vault.clock == written


def test_versions_built_on_keyring_still_read_a_tidied_vault(vault):
    expected = an_installation_with_a_changed_password(vault)
    stored_values()
    old = KeyringLayout(vault)

    for kind, value in expected.items():
        assert old.get(ENTRIES[kind]) == value


def test_entries_written_by_an_older_version_afterwards_are_taken_over(vault):
    expected = an_installation_with_a_changed_password(vault)
    stored_values()

    KeyringLayout(vault).set(ENTRIES["main"], "main-3")
    KeyringLayout(vault).set(DEVICE, "v1:device")

    assert stored_values() == {**expected, "main": "main-3"}
    assert_tidy(vault)


def test_deleting_everything_leaves_nothing_to_come_back(vault):
    an_installation_with_a_changed_password(vault)

    for kind in credential_store.SUPPORTED_CREDENTIAL_KINDS:
        credential_store.delete_password_hash(kind)

    assert stored_entries(vault) == {LOCAL_MACHINE: {}, ROAMING: {}}


def _tidy_call_count():
    vault = TwinVault()
    an_installation_with_a_changed_password(vault)
    before = vault.calls
    credential_store._tidy(vault)
    return vault.calls - before


@pytest.mark.parametrize("first_in_view", [LOCAL_MACHINE, ROAMING])
def test_a_failure_at_any_step_of_tidying_loses_nothing(monkeypatch, first_in_view):
    second_in_view = ROAMING if first_in_view == LOCAL_MACHINE else LOCAL_MACHINE
    for step in range(1, _tidy_call_count() + 1):
        vault = use(monkeypatch, TwinVault())
        expected = an_installation_with_a_changed_password(vault)
        vault.fail_at = vault.calls + step

        with pytest.raises(CredentialStoreError):
            credential_store.get_password_hash("main")
        vault.restart(first_in_view, second_in_view)

        assert stored_values() == expected, step
        assert_tidy(vault)


@pytest.mark.parametrize("store_written", [LOCAL_MACHINE, ROAMING])
def test_another_program_writing_at_any_step_of_tidying_loses_nothing(
    monkeypatch, store_written
):
    for step in range(1, _tidy_call_count() + 1):
        vault = use(monkeypatch, TwinVault())
        expected = an_installation_with_a_changed_password(vault)
        vault.interfere_at = {vault.calls + step: store_written}

        assert stored_values() == expected, step
        # A copy the interruption hid is found once its store is next in view.
        settle(vault, expected)
        assert_tidy(vault)


_history = st.lists(
    st.one_of(
        st.tuples(st.just("set"), st.sampled_from(sorted(ENTRIES)), st.integers(0, 3)),
        st.tuples(st.just("delete"), st.sampled_from(sorted(ENTRIES)), st.none()),
        st.tuples(
            st.just("other"), st.sampled_from([LOCAL_MACHINE, ROAMING]), st.none()
        ),
    ),
    max_size=30,
)


@settings(max_examples=300, deadline=None)
@given(
    history=_history,
    interference=st.dictionaries(
        st.integers(1, 120), st.sampled_from([LOCAL_MACHINE, ROAMING]), max_size=4
    ),
)
def test_any_keyring_history_tidies_to_the_values_written_last(history, interference):
    vault = TwinVault()
    old = KeyringLayout(vault)
    for action, subject, number in history:
        if action == "set":
            old.set(ENTRIES[subject], f"{subject}-{number}")
        elif action == "delete":
            old.delete(ENTRIES[subject])
        else:
            vault.other_program_writes(subject)
    expected = {kind: vault.newest(entry) for kind, entry in ENTRIES.items()}
    vault.interfere_at = {
        vault.calls + step: store for step, store in interference.items()
    }
    original = credential_store.vault
    credential_store.vault = vault
    try:
        assert stored_values() == expected
        settle(vault, expected)
        # Only two writes by other programs inside one clean-up can leave the
        # empty check entry behind.
        assert_tidy(vault, check_entry_may_remain=True)
        assert {kind: old.get(entry) for kind, entry in ENTRIES.items()} == expected
    finally:
        credential_store.vault = original


# The tests below use the real Credential Manager under throwaway names and
# check both of its stores afterwards, so nothing is left behind.
windows_only = pytest.mark.skipif(
    sys.platform != "win32", reason="needs Windows Credential Manager"
)


def _real_copies(real, targets):
    return {
        persist: sorted(credential_store._stored_in(real, persist, targets))
        for persist in (LOCAL_MACHINE, ROAMING)
    }


@pytest.fixture()
def real_vault(monkeypatch):
    real = load_vault()
    monkeypatch.setattr(credential_store, "vault", real)
    monkeypatch.setattr(credential_store, "SERVICE_NAME", "SilverEstimateTestVault")
    service = credential_store.SERVICE_NAME
    targets = [service, *(f"{entry}@{service}" for entry in ENTRIES.values())]
    yield real, targets
    for target in (*targets, f"layout-check@{service}", f"layout@{service}"):
        for persist in (ROAMING, LOCAL_MACHINE):
            real.write(target, "", "", persist)
            real.delete(target)


@windows_only
def test_entries_round_trip_through_the_real_vault(real_vault):
    real, targets = real_vault
    for kind in credential_store.SUPPORTED_CREDENTIAL_KINDS:
        credential_store.set_password_hash(kind, f"{kind}-₹-hash")
    for kind in credential_store.SUPPORTED_CREDENTIAL_KINDS:
        assert credential_store.get_password_hash(kind) == f"{kind}-₹-hash"

    for kind in credential_store.SUPPORTED_CREDENTIAL_KINDS:
        credential_store.delete_password_hash(kind)

    assert stored_values() == dict.fromkeys(credential_store.SUPPORTED_CREDENTIAL_KINDS)
    assert _real_copies(real, targets) == {LOCAL_MACHINE: [], ROAMING: []}


@windows_only
def test_a_keyring_installation_is_tidied_in_the_real_vault(real_vault):
    real, targets = real_vault
    service = credential_store.SERVICE_NAME

    class RealKeyringLayout(KeyringLayout):
        def get(self, entry):
            found = self.vault.read(service)
            if found is None or found.user_name != entry:
                found = self.vault.read(f"{entry}@{service}")
            return found.secret if found else None

        def set(self, entry, value):
            persist = LOCAL_MACHINE if entry == DEVICE else ROAMING
            shared = self.vault.read(service)
            if shared is not None:
                self.vault.write(
                    f"{shared.user_name}@{service}",
                    shared.user_name,
                    shared.secret,
                    persist,
                )
            self.vault.write(service, entry, value, persist)

    old = RealKeyringLayout(real)
    old.set(ENTRIES["main"], "main-1")
    old.set(ENTRIES["backup"], "backup-1")
    old.set(DEVICE, "v1:device")
    old.set(ENTRIES["main"], "main-2")
    old.set(ENTRIES["backup"], "backup-2")
    # Another program's local-machine write brings the device copy into view,
    # so this start leaves the superseded backup hash under its own name.
    real.write(f"layout-check@{service}", "", "", LOCAL_MACHINE)
    old.set(DEVICE, "v1:device")
    assert old.get(ENTRIES["backup"]) == "backup-1"
    before = _real_copies(real, targets)
    assert service in before[LOCAL_MACHINE] and service in before[ROAMING]

    values = stored_values()

    assert values["main"] == "main-2"
    assert values["backup"] == "backup-2"
    assert values["device_binding"] == "v1:device"
    assert _real_copies(real, targets) == {
        LOCAL_MACHINE: sorted(
            f"{ENTRIES[kind]}@{service}"
            for kind in ("main", "backup", "device_binding")
        ),
        ROAMING: [],
    }
    assert old.get(ENTRIES["backup"]) == "backup-2"

    for kind in credential_store.SUPPORTED_CREDENTIAL_KINDS:
        credential_store.delete_password_hash(kind)
    assert _real_copies(real, targets) == {LOCAL_MACHINE: [], ROAMING: []}
