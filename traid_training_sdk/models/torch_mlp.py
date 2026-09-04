from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np

from .base import ModelProtocol
from ..core.errors import ConfigurationError, NotAvailableSDK
from ..core.device import get_device


@dataclass
class TorchMLPModel(ModelProtocol):
    """Lightweight PyTorch MLP for regression and classification tasks."""
    
    hidden_sizes: list[int] = field(default_factory=lambda: [64, 32])
    learning_rate: float = 0.001
    epochs: int = 100
    batch_size: int = 32
    task: str = "regression"  # "regression" or "classification"
    random_state: Optional[int] = None
    early_stopping: bool = True
    patience: int = 10
    
    # Internal state
    _model: Any = field(default=None, init=False, repr=False)
    _scaler_X: Any = field(default=None, init=False, repr=False)
    _scaler_y: Any = field(default=None, init=False, repr=False)
    _n_features: Optional[int] = field(default=None, init=False, repr=False)
    _n_classes: Optional[int] = field(default=None, init=False, repr=False)
    
    def __post_init__(self) -> None:
        """Validate parameters and check torch availability."""
        try:
            import torch  # noqa: F401
        except ImportError as exc:
            raise NotAvailableSDK(
                "PyTorch is not available. Install with: pip install torch"
            ) from exc
            
        if self.task not in {"regression", "classification"}:
            raise ConfigurationError(f"Task must be 'regression' or 'classification', got: {self.task}")
            
        if not self.hidden_sizes:
            raise ConfigurationError("hidden_sizes must not be empty")
            
        if self.learning_rate <= 0:
            raise ConfigurationError("learning_rate must be positive")
            
        if self.epochs <= 0:
            raise ConfigurationError("epochs must be positive")

    def _create_model(self, n_features: int, n_outputs: int) -> Any:
        """Create the PyTorch model architecture."""
        import torch
        import torch.nn as nn
        
        if self.random_state is not None:
            torch.manual_seed(self.random_state)
            np.random.seed(self.random_state)
        
        layers = []
        
        # Input layer
        prev_size = n_features
        
        # Hidden layers
        for hidden_size in self.hidden_sizes:
            layers.extend([
                nn.Linear(prev_size, hidden_size),
                nn.ReLU(),
                nn.Dropout(0.1)
            ])
            prev_size = hidden_size
        
        # Output layer
        layers.append(nn.Linear(prev_size, n_outputs))
        
        # Add final activation for classification
        if self.task == "classification" and n_outputs > 1:
            layers.append(nn.LogSoftmax(dim=1))
        
        return nn.Sequential(*layers)

    def _prepare_data(self, X: Any, y: Any = None) -> Any:
        """Prepare and scale input data."""
        if hasattr(X, "select_dtypes"):
            X = X.select_dtypes(include=[np.number])

        X = np.asarray(X, dtype=np.float32)
        
        if X.ndim == 1:
            X = X.reshape(-1, 1)
            
        # Fit scaler on training data
        if self._scaler_X is None:
            from sklearn.preprocessing import StandardScaler
            self._scaler_X = StandardScaler()
            X_scaled = self._scaler_X.fit_transform(X)
        else:
            X_scaled = self._scaler_X.transform(X)
        
        if y is None:
            return X_scaled
            
        y = np.asarray(y)
        
        # Handle target scaling/encoding
        if self.task == "regression":
            if self._scaler_y is None:
                from sklearn.preprocessing import StandardScaler
                self._scaler_y = StandardScaler()
                y_processed = self._scaler_y.fit_transform(y.reshape(-1, 1)).ravel()
            else:
                y_processed = self._scaler_y.transform(y.reshape(-1, 1)).ravel()
        else:  # classification
            if self._n_classes is None:
                unique_classes = np.unique(y)
                self._n_classes = len(unique_classes)
            y_processed = y.astype(np.int64)
            
        return X_scaled, y_processed

    def fit(self, X: Any, y: Any, **kwargs: Any) -> "TorchMLPModel":
        """Fit the PyTorch MLP model."""
        import torch
        import torch.nn as nn
        import torch.optim as optim
        from torch.utils.data import DataLoader, TensorDataset
        
        # Prepare data
        X_scaled, y_processed = self._prepare_data(X, y)
        self._n_features = X_scaled.shape[1]
        
        # Determine output size
        if self.task == "regression":
            n_outputs = 1
        else:
            if self._n_classes is None:
                raise ValueError("n_classes not set for classification task")
            n_outputs = self._n_classes
            
        # Create model
        if self._n_features is None:
            raise ValueError("n_features not set")
        self._model = self._create_model(self._n_features, n_outputs)
        
        # Device selection
        device = get_device()
        self._model.to(device)

        # Convert to tensors
        X_tensor = torch.FloatTensor(X_scaled).to(device)
        y_tensor: Any
        criterion: Any
        if self.task == "regression":
            y_tensor = torch.FloatTensor(y_processed).to(device)
            criterion = nn.MSELoss()
        else:
            y_tensor = torch.LongTensor(y_processed).to(device)
            criterion = nn.NLLLoss()
            
        # Create data loader
        dataset = TensorDataset(X_tensor, y_tensor)
        dataloader = DataLoader(dataset, batch_size=self.batch_size, shuffle=True)
        
        # Setup training
        optimizer = optim.Adam(self._model.parameters(), lr=self.learning_rate)
        
        # Training loop with early stopping
        best_loss = float('inf')
        patience_counter = 0
        
        self._model.train()
        for epoch in range(self.epochs):
            epoch_loss = 0.0
            
            for batch_X, batch_y in dataloader:
                optimizer.zero_grad()
                
                outputs = self._model(batch_X)
                if self.task == "regression":
                    outputs = outputs.squeeze()
                    
                loss = criterion(outputs, batch_y)
                loss.backward()
                optimizer.step()
                
                epoch_loss += loss.item()
            
            avg_loss = epoch_loss / len(dataloader)
            
            # Early stopping
            if self.early_stopping:
                if avg_loss < best_loss:
                    best_loss = avg_loss
                    patience_counter = 0
                else:
                    patience_counter += 1
                    if patience_counter >= self.patience:
                        break
        
        self._model.eval()
        return self

    def predict(self, X: Any) -> np.ndarray:
        """Make predictions."""
        if self._model is None:
            raise RuntimeError("Model must be fitted before making predictions")
            
        import torch
        
        device = get_device()
        self._model.to(device)
        
        X_scaled = self._prepare_data(X)
        X_tensor = torch.FloatTensor(X_scaled).to(device)
        
        self._model.eval()
        with torch.no_grad():
            outputs = self._model(X_tensor)
            
            predictions: np.ndarray
            if self.task == "regression":
                predictions = outputs.squeeze().cpu().numpy()
                # Inverse transform if scaler was used
                if self._scaler_y is not None:
                    predictions = self._scaler_y.inverse_transform(predictions.reshape(-1, 1)).ravel()
            else:  # classification
                # Convert log probabilities to class predictions
                predictions = torch.argmax(outputs, dim=1).cpu().numpy()
                
        return predictions

    def predict_proba(self, X: Any) -> np.ndarray:
        """Predict class probabilities for classification tasks."""
        if self.task != "classification":
            raise NotAvailableSDK("predict_proba is only available for classification tasks")
            
        if self._model is None:
            raise RuntimeError("Model must be fitted before making predictions")
            
        import torch
        
        device = get_device()
        self._model.to(device)
        
        X_scaled = self._prepare_data(X)
        X_tensor = torch.FloatTensor(X_scaled).to(device)
        
        self._model.eval()
        with torch.no_grad():
            log_probs = self._model(X_tensor)
            # Convert log probabilities to probabilities
            probs = torch.exp(log_probs).cpu().numpy()
            
        return probs

    def save(self, path: str | Path) -> None:
        """Save the model to disk."""
        if self._model is None:
            raise RuntimeError("Cannot save unfitted model")
            
        import torch
        
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save model state and metadata
        state = {
            'model_state_dict': self._model.state_dict(),
            'params': {
                'hidden_sizes': self.hidden_sizes,
                'learning_rate': self.learning_rate,
                'epochs': self.epochs,
                'batch_size': self.batch_size,
                'task': self.task,
                'random_state': self.random_state,
                'early_stopping': self.early_stopping,
                'patience': self.patience,
            },
            'metadata': {
                'n_features': self._n_features,
                'n_classes': self._n_classes,
            }
        }
        
        torch.save(state, path)
        
        # Save scalers separately using joblib
        from .base import joblib_save
        if self._scaler_X is not None:
            joblib_save(self._scaler_X, path.with_suffix('.scaler_X.joblib'))
        if self._scaler_y is not None:
            joblib_save(self._scaler_y, path.with_suffix('.scaler_y.joblib'))

    @classmethod
    def load(cls, path: str | Path) -> "TorchMLPModel":
        """Load a saved model from disk."""
        import torch
        
        path = Path(path)
        
        # Load model state
        state = torch.load(path, map_location='cpu')
        params = state['params']
        metadata = state['metadata']
        
        # Create model instance
        model = cls(**params)
        model._n_features = metadata['n_features']
        model._n_classes = metadata['n_classes']
        
        # Recreate and load model
        if model.task == "regression":
            n_outputs = 1
        else:
            if model._n_classes is None:
                raise ValueError("n_classes not set for classification task")
            n_outputs = model._n_classes
            
        if model._n_features is None:
            raise ValueError("n_features not set")
        model._model = model._create_model(model._n_features, n_outputs)
        model._model.load_state_dict(state['model_state_dict'])
        model._model.eval()
        
        # Load scalers
        from .base import joblib_load
        scaler_X_path = path.with_suffix('.scaler_X.joblib')
        if scaler_X_path.exists():
            model._scaler_X = joblib_load(scaler_X_path)
            
        scaler_y_path = path.with_suffix('.scaler_y.joblib')
        if scaler_y_path.exists():
            model._scaler_y = joblib_load(scaler_y_path)
        
        return model


__all__ = ["TorchMLPModel"]