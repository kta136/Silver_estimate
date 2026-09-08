"""Application inputs stay detached from UI state and import without Qt."""

import os
import subprocess
import sys
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from silverestimate.domain.estimate_entry import EstimateEntryRowState
from silverestimate.services.estimate_entry_persistence import (
    EstimateEntryPersistenceService,
)
from silverestimate.ui.view_models import EstimateEntryViewModel


def test_save_snapshot_retains_original_rows_rates_and_line_identity():
    model = EstimateEntryViewModel()
    model.set_rows(
        [
            EstimateEntryRowState(
                code="REG",
                name="Original",
                gross=10,
                net_weight=10,
                fine_weight=9,
                purity=90,
                wage_amount=100,
                wage_rate=10,
            )
        ]
    )
    model.set_totals_inputs(
        silver_rate=100, last_balance_silver=2, last_balance_amount=50
    )
    snapshot = model.as_save_snapshot()
    key = snapshot.rows[0].line_key
    assert key
    assert model.as_save_snapshot().rows[0].line_key == key
    model.set_rows([replace(snapshot.rows[0], name="Later edit", gross=20)])
    model.set_totals_inputs(
        silver_rate=999, last_balance_silver=9, last_balance_amount=999
    )
    model.clear_rows()
    prepared = EstimateEntryPersistenceService(snapshot).prepare_save_payload(
        voucher_no="1", date="2026-09-06", note="Captured"
    )
    assert prepared.payload.items[0].name == "Original"
    assert prepared.payload.items[0].line_key == key
    assert prepared.payload.items[0].gross == 10
    assert prepared.payload.silver_rate == 100
    assert prepared.payload.last_balance_silver == 2
    assert prepared.payload.last_balance_amount == 50
    with pytest.raises(FrozenInstanceError):
        snapshot.silver_rate = 200
    with pytest.raises(FrozenInstanceError):
        snapshot.rows[0].gross = 20


def test_save_service_runs_with_ui_and_presenter_imports_blocked():
    script = """
import importlib.abc
import sys
class RejectPresentation(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith(('PySide6', 'silverestimate.ui', 'silverestimate.presenter')):
            raise AssertionError('Application imported presentation: ' + fullname)
sys.meta_path.insert(0, RejectPresentation())
from silverestimate.domain.estimate_entry import EstimateEntryRowState, EstimateEntrySnapshot, SaveOutcome
from silverestimate.services.estimate_entry_persistence import EstimateEntryPersistenceService
row = EstimateEntryRowState(code='REG', name='Regular', gross=10, net_weight=10, purity=90, fine_weight=9, wage_amount=100, wage_rate=10, line_key='stable')
class Saver:
    def __init__(self):
        self.calls = []
    def save_estimate(self, payload):
        self.calls.append(payload)
        return SaveOutcome(True, 'saved')
saver = Saver()
service = EstimateEntryPersistenceService(EstimateEntrySnapshot((row,), 100))
outcome, prepared = service.execute_save(voucher_no='1', date='2026-09-06', note='', presenter=saver)
assert outcome.success
assert saver.calls == [prepared.payload]
assert prepared.payload.totals['net_fine'] == 9
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[2],
        env=dict(os.environ),
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
