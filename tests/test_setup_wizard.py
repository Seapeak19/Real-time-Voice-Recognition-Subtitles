from __future__ import annotations

from subloom.config import AppConfig
from subloom.ui.setup_wizard import SetupWizard


def test_setup_wizard_builds_and_applies(qtbot):
    config = AppConfig()
    config.first_run = True
    wizard = SetupWizard(config)
    qtbot.addWidget(wizard)
    assert len(wizard.pageIds()) == 5

    wizard._source_combo.setCurrentIndex(
        wizard._source_combo.findData("microphone")
    )
    wizard._target_combo.setCurrentIndex(wizard._target_combo.findData("ja"))
    wizard._provider_combo.setCurrentIndex(
        wizard._provider_combo.findData("cloud")
    )
    wizard._device_combo_asr.setCurrentIndex(
        wizard._device_combo_asr.findData("cpu")
    )
    wizard._model_combo.setCurrentIndex(wizard._model_combo.findData("small"))
    assert wizard._apply() is True
    assert wizard.config.audio.source == "microphone"
    assert wizard.config.translation.target_lang == "ja"
    assert wizard.config.translation.provider == "cloud"
    assert wizard.config.asr.device == "cpu"
    assert wizard.config.asr.model == "small"
    assert wizard.config.first_run is False
