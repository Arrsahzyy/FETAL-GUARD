from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Literal

from .contracts import ModelValidationStatus


DeploymentMode = Literal["research", "shadow", "clinician", "patient"]


@dataclass(frozen=True)
class ModelArtifactManifest:
    model_name: str
    model_version: str
    architecture: str
    preprocessing_version: str
    artifact_file: str
    artifact_sha256: str
    validation_status: ModelValidationStatus
    input_schema_version: int
    created_at: str

    @classmethod
    def load(cls, path: str | Path) -> "ModelArtifactManifest":
        manifest_path = Path(path)
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        return cls(
            model_name=str(data["model_name"]).strip(),
            model_version=str(data["model_version"]).strip(),
            architecture=str(data["architecture"]).strip(),
            preprocessing_version=str(data["preprocessing_version"]).strip(),
            artifact_file=str(data["artifact_file"]).strip(),
            artifact_sha256=str(data["artifact_sha256"]).strip().lower(),
            validation_status=ModelValidationStatus(data["validation_status"]),
            input_schema_version=int(data["input_schema_version"]),
            created_at=str(data["created_at"]).strip(),
        )

    def artifact_path(self, manifest_path: str | Path) -> Path:
        base = Path(manifest_path).resolve().parent
        candidate = (base / self.artifact_file).resolve()
        if candidate.parent != base:
            raise ValueError("Model artifact must be stored beside its manifest")
        return candidate

    def verify(self, manifest_path: str | Path) -> Path:
        if not all((self.model_name, self.model_version, self.preprocessing_version, self.created_at)):
            raise ValueError("Model manifest contains empty required fields")
        if self.architecture != "cnn_lstm_multitask":
            raise ValueError("Unsupported model architecture")
        if self.input_schema_version < 1:
            raise ValueError("Input schema version must be positive")
        if len(self.artifact_sha256) != 64 or any(
            character not in "0123456789abcdef" for character in self.artifact_sha256
        ):
            raise ValueError("artifact_sha256 must be a lowercase SHA-256 digest")
        artifact_path = self.artifact_path(manifest_path)
        if not artifact_path.is_file():
            raise FileNotFoundError(f"Model artifact not found: {artifact_path}")
        digest = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
        if digest != self.artifact_sha256:
            raise ValueError("Model artifact hash does not match its manifest")
        return artifact_path

    def assert_allowed_for(self, mode: DeploymentMode) -> None:
        allowed = {
            "research": {ModelValidationStatus.experimental, ModelValidationStatus.analytical_validated, ModelValidationStatus.clinical_validated},
            "shadow": {ModelValidationStatus.analytical_validated, ModelValidationStatus.clinical_validated},
            "clinician": {ModelValidationStatus.clinical_validated},
            "patient": {ModelValidationStatus.clinical_validated},
        }
        if self.validation_status not in allowed[mode]:
            raise RuntimeError(
                f"Model validation status {self.validation_status.value} is not allowed in {mode} mode"
            )
