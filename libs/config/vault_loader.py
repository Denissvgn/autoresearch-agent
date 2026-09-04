"""Shim module exposing Vault loader under `config.vault_loader`.

This bridges the historical import path `config.vault_loader` to the
implementation located in `config/config/vault_loader.py` within this
package. It allows services that import `config.vault_loader` to find
Vault helpers after the package layout change.
"""

from config.config.vault_loader import *  # re-export public API
