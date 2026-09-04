"""Example service configuration demonstrating ML training framework usage."""

from typing import Any

from pydantic import Field, field_validator

# Import the shared framework
from config.ml_training_config import BaseMLTrainingConfig


class EnsembleTrainerConfig(BaseMLTrainingConfig):
    """Example configuration for ensemble trainer service."""
    
    def __init__(self, service_name: str = "ensemble-trainer", **data: Any):
        """Initialize ensemble trainer configuration.
        
        Args:
            service_name: Name of the service (defaults to 'ensemble-trainer')
            **data: Additional configuration data
        """
        super().__init__(service_name, **data)
    
    @property
    def service_name(self) -> str:
        """Get the service name."""
        return self._svc
    
    # Ensemble-specific configuration
    n_estimators: int = Field(default=100)
    max_depth: int = Field(default=10)
    learning_rate: float = Field(default=0.1)
    min_samples_leaf: int = Field(default=5)
    feature_selection_k: int = Field(default=20)
    
    # Training configuration
    training_data_path: str = Field(default="data/enriched_training_data.parquet")
    output_dir: str = Field(default="models/")
    model_filename: str = Field(default="ensemble_model.joblib")
    validation_split: float = Field(default=0.2)
    cross_validation_folds: int = Field(default=5)
    random_state: int = Field(default=42)
    
    # Performance configuration
    model_accuracy_threshold: float = Field(default=0.7)
    early_stopping_patience: int = Field(default=10)
    hyperparameter_optimization_trials: int = Field(default=50)
    
    @field_validator("learning_rate")
    @classmethod
    def validate_learning_rate(cls, v: float) -> float:
        if v <= 0 or v > 1:
            raise ValueError("learning_rate must be between 0 and 1")
        return v
    
    @field_validator("validation_split")
    @classmethod
    def validate_validation_split(cls, v: float) -> float:
        if v <= 0 or v >= 1:
            raise ValueError("validation_split must be between 0 and 1")
        return v
    
    def get_training_params(self) -> dict[str, Any]:
        """Get ensemble-specific training parameters."""
        return {
            "n_estimators": self.n_estimators,
            "max_depth": self.max_depth,
            "learning_rate": self.learning_rate,
            "min_samples_leaf": self.min_samples_leaf,
            "random_state": self.random_state,
        }
    
    def get_hyperparameter_space(self) -> dict[str, Any]:
        """Get hyperparameter optimization space for Optuna."""
        return {
            "n_estimators": (50, 200),
            "max_depth": (5, 20),
            "learning_rate": (0.01, 0.3),
            "min_samples_leaf": (1, 10),
        }


def get_ensemble_config() -> EnsembleTrainerConfig:
    """Get ensemble trainer configuration with Vault integration."""
    config = EnsembleTrainerConfig("ensemble-trainer")
    
    # Override with Vault values if available
    config.n_estimators = config.get_config_value("ENSEMBLE_N_ESTIMATORS", config.n_estimators)
    config.max_depth = config.get_config_value("ENSEMBLE_MAX_DEPTH", config.max_depth)
    config.learning_rate = config.get_config_value("ENSEMBLE_LEARNING_RATE", config.learning_rate)
    config.training_data_path = config.get_config_value("TRAINING_DATA_PATH", config.training_data_path)
    config.model_accuracy_threshold = config.get_config_value("MODEL_ACCURACY_THRESHOLD", config.model_accuracy_threshold)
    
    return config


if __name__ == "__main__":
    # Example usage
    config = get_ensemble_config()
