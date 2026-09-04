from __future__ import annotations

import pytest

from ml_artifacts.ensemble.tsfm_adapter import TsfmAdapterConfig
from ml_artifacts.ensemble.tsfm_oof_artifacts import (
    TSFM_PROVENANCE_OOF,
    TsfmProbabilityArtifactMetadata,
    build_tsfm_probability_artifact_frame,
    read_tsfm_probability_artifact,
    write_tsfm_probability_artifact,
)


def test_tsfm_probability_artifact_round_trips(tmp_path):
    pytest.importorskip("pyarrow")

    config = TsfmAdapterConfig(
        model_family="timesfm",
        forecast_type="point",
        context_length=32,
        horizon=1,
    )
    frame = build_tsfm_probability_artifact_frame(
        probabilities=[0.2, 0.8],
        provenance=TSFM_PROVENANCE_OOF,
    )
    metadata = TsfmProbabilityArtifactMetadata.from_adapter_config(
        config,
        provenance=TSFM_PROVENANCE_OOF,
    )

    path = write_tsfm_probability_artifact(frame, tmp_path / "tsfm.parquet", metadata)
    loaded = read_tsfm_probability_artifact(path, require_oof_for_training=True)

    assert loaded.probability_column == "oof_proba"
    assert loaded.metadata["model_family"] == "timesfm"
    assert loaded.frame["oof_proba"].tolist() == [0.2, 0.8]
