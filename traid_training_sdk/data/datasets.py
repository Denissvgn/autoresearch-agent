from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Split:
    train: object  # pandas.DataFrame at runtime
    val: object
    test: object


def time_split(df, *, train: float = 0.8, val: float = 0.1, test: float = 0.1) -> Split:
    assert abs((train + val + test) - 1.0) < 1e-6, "splits must sum to 1.0"
    n = len(df)
    n_train = int(n * train)
    n_val = int(n * val)
    # Ensure at least one row in each when possible
    n_train = max(n_train, 1)
    n_val = max(n_val, 1)
    n_test = max(n - n_train - n_val, 1)
    # Adjust in case of rounding overflow
    while n_train + n_val + n_test > n:
        n_test -= 1
    i1 = n_train
    i2 = n_train + n_val
    train_df = df.iloc[:i1]
    val_df = df.iloc[i1:i2]
    test_df = df.iloc[i2:]
    return Split(train=train_df, val=val_df, test=test_df)

