#!/usr/bin/env python3
"""Run the real native Keychain lifecycle against one disposable item."""
from __future__ import annotations

import argparse
import secrets

from agentterm.keychain import KeychainError, NativeKeychainStorage


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--helper", required=True)
    args = parser.parse_args()
    service = "com.agentterm.test." + secrets.token_hex(16)
    account = "qualification-" + secrets.token_hex(16)
    storage = NativeKeychainStorage(args.helper, service=service)
    try:
        storage.put(account, b"agentterm-keychain-v1")
        assert storage.get(account) == b"agentterm-keychain-v1"
        storage.put(account, b"agentterm-keychain-v2")
        assert storage.get(account) == b"agentterm-keychain-v2"
        storage.delete(account)
        try:
            storage.get(account)
        except KeychainError:
            pass
        else:
            raise AssertionError("deleted Keychain item remained readable")
        try:
            storage.get("invalid account")
        except KeychainError:
            pass
        else:
            raise AssertionError("invalid account was accepted")
        print("native_keychain_lifecycle=PASS")
        return 0
    finally:
        # Delete is idempotent in the helper; this is best-effort cleanup for
        # failures after creation and is scoped to this random test account.
        try:
            storage.delete(account)
        except KeychainError:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
