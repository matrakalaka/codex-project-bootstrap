import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import tool_discovery


class ToolDiscoveryTests(unittest.TestCase):
    def test_manifest_has_all_requested_tools_and_exact_upstreams(self):
        manifest = json.loads(tool_discovery.MANIFEST.read_text(encoding="utf-8"))
        tools = {item["id"]: item for item in manifest["tools"]}
        self.assertEqual(set(tools), {"agentterm", "open-terminal", "mirofish", "loadersz-core", "api-anything"})
        self.assertEqual(tools["mirofish"]["upstream"], "https://github.com/666ghj/MiroFish")
        self.assertEqual(tools["loadersz-core"]["upstream"], "https://github.com/lumberjacque/loadersz-core")
        self.assertEqual(tools["api-anything"]["upstream"], "https://github.com/goodnight000/api-anything")
        self.assertIsNone(tools["open-terminal"]["upstream"])
        self.assertEqual(tools["agentterm"]["archive_sha256"], "17b6784fe8a96e7667719131209fc44ecefd56010f69479ac1b6124690e5d500")

    def test_mcp_registration_is_structurally_valid(self):
        registration = tool_discovery._mcp_registration()
        self.assertTrue(registration["valid"])
        self.assertEqual(registration["servers"], ["api-anything"])

    def test_fresh_bootstrap_session_subprocess_emits_json(self):
        result = subprocess.run(
            [sys.executable, str(tool_discovery.ROOT / "scripts" / "tool_discovery.py"), "--json"],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema_version"], "bootstrap_tool_discovery.v1")
        self.assertEqual({item["id"] for item in payload["tools"]}, {
            "agentterm", "open-terminal", "mirofish", "loadersz-core", "api-anything"
        })

    def test_isolated_provisioning_root_is_reported_without_global_install(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api_bin = root / "install" / "api-anything" / "node_modules" / ".bin"
            api_bin.mkdir(parents=True)
            (api_bin / "api-anything").write_text("#!/bin/sh\nprintf '0.1.0\\n'\n", encoding="utf-8")
            (api_bin / "api-anything").chmod(0o755)
            loader_root = root / "src" / "loadersz-core"
            (loader_root / "node_modules").mkdir(parents=True)
            (loader_root / "dist").mkdir()
            result = tool_discovery.discover(root)
            statuses = {item["id"]: item["status"] for item in result["tools"]}
            self.assertEqual(statuses["agentterm"], "NOT_INSTALLED")
            self.assertEqual(statuses["api-anything"], "NOT_REGISTERED")
            self.assertEqual(statuses["loadersz-core"], "AVAILABLE")

    @patch.object(tool_discovery.Path, "exists", return_value=False)
    @patch.object(tool_discovery, "_command_version", return_value=None)
    def test_fresh_session_reports_missing_tools_explicitly(self, version, exists):
        result = tool_discovery.discover()
        statuses = {item["id"]: item["status"] for item in result["tools"]}
        self.assertEqual(statuses["open-terminal"], "BLOCKED")
        self.assertEqual(statuses["agentterm"], "NOT_INSTALLED")
        self.assertEqual(statuses["api-anything"], "NOT_INSTALLED")
        self.assertEqual(statuses["mirofish"], "NOT_INSTALLED")
        self.assertEqual(statuses["loadersz-core"], "NOT_INSTALLED")


if __name__ == "__main__":
    unittest.main()
