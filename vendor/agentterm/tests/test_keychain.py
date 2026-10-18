import pytest

from agentterm.platform import MacOSKeychainStorage, PlatformError


def test_keychain_requires_native_helper_and_supports_mock_contract():
    with pytest.raises(PlatformError): MacOSKeychainStorage()
    calls = []
    values = {}
    def runner(command, key, value=None):
        calls.append(command)
        if command == "put": values[key] = value
        elif command == "get": return values[key]
        else: values.pop(key, None)
    storage = MacOSKeychainStorage(runner=runner)
    storage.put("synthetic", b"secret"); assert storage.get("synthetic") == b"secret"; storage.delete("synthetic")
    assert calls == ["put", "get", "delete"]
