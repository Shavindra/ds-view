"""Exercise the bundled reader against a live DataLad store and a YAML catalogue."""
import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from datalad.api import create, meta_add

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/catalogue"


class Client:
    def __init__(self, binary):
        self.binary = binary

    def __enter__(self):
        self.process = subprocess.Popen([self.binary], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        text=True, encoding="utf-8")
        return self

    def call(self, **message):
        self.process.stdin.write(json.dumps(message) + "\n")
        self.process.stdin.flush()
        line = self.process.stdout.readline()
        if not line:
            raise RuntimeError(f"reader exited ({self.process.poll()})")
        response = json.loads(line)
        if "error" in response:
            raise ValueError(response["error"])
        return response["value"]

    def __exit__(self, *_):
        self.process.stdin.close()
        self.process.stdout.close()
        self.process.wait(timeout=30)


def check_store(binary, workspace):
    config = workspace / "gitconfig"
    config.write_text("[user]\nname = DS View test\nemail = test@example.org\n", encoding="utf-8")
    with patch.dict(os.environ, {"GIT_CONFIG_GLOBAL": str(config)}):
        root = workspace / "data set å"
        dataset = create(path=str(root), annex=False, result_renderer="disabled")
        filename = "measurements.tsv"
        (root / filename).write_text("value\n5\n", encoding="utf-8")
        dataset.save(result_renderer="disabled")
        record = {"type": "dataset", "dataset_id": dataset.id,
                  "dataset_version": dataset.repo.get_hexsha(), "extractor_name": "example",
                  "extractor_version": "1", "extraction_parameter": {}, "extraction_time": 1700000000.0,
                  "agent_name": "DS View test", "agent_email": "test@example.org",
                  "extracted_metadata": {"@type": "Dataset", "name": "Stored observations"}}
        meta_add(record, dataset=dataset, result_renderer="disabled")
        meta_add({**record, "type": "file", "path": filename, "extracted_metadata": {"unit": "metre"}},
                 dataset=dataset, result_renderer="disabled")
        def fingerprint():
            return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).digest()
                    for p in root.rglob("*") if p.is_file()}
        before = fingerprint()
        with Client(binary) as reader:
            model = reader.call(op="open", root=str(root))
            assert not model["warnings"], model["warnings"]
            entry = next(r for r in model["records"] if r["title"] == "Stored observations")
            params = {"id": entry["id"], "session": model["session"], "folder": "."}
            rows = reader.call(op="files", **params)["rows"]
            assert any(r["path"] == filename and r["local"] for r in rows), rows
            detail = reader.call(op="file", path=filename, preview=True, **params)
            assert detail["metadata"][0]["extracted_metadata"]["unit"] == "metre", detail
            assert detail["preview"].splitlines() == ["value", "5"], detail
        assert fingerprint() == before, "Browsing modified the DataLad project"


class ReaderTests(unittest.TestCase):
    def setUp(self):
        self.binary = next((ROOT / "src-tauri/binaries").glob("ds-reader-*"))

    def test_real_metalad_store(self):
        with tempfile.TemporaryDirectory() as work:
            check_store(self.binary, Path(work))

    def test_catalogue_links_and_selection(self):
        with Client(self.binary) as reader:
            model = reader.call(op="open", root=str(FIXTURE))
            self.assertEqual(model["warnings"], [])
            entries = {r["title"]: r for r in model["records"]}
            paper = entries["Shoreline survey"]
            for title in ("Station readings", "Station means"):
                self.assertIn(entries[title]["id"], paper["links"])
            session = model["session"]
            self.assertIn(paper["id"], reader.call(op="search", session=session, term="readings.csv"))
            with self.assertRaisesRegex(ValueError, "outside"):
                reader.call(op="file", session=session, id=entries["Station means"]["id"],
                            folder=".", path="../raw/readings.csv", preview=True)
            with self.assertRaises(ValueError):
                reader.call(op="open", root=str(FIXTURE / "missing"))
            self.assertTrue(reader.call(op="source", session=session, id=paper["id"]))
            refreshed = reader.call(op="refresh", session=session)
            self.assertNotEqual(refreshed["session"], session)


if __name__ == "__main__":
    unittest.main()
