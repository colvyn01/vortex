import os
import shutil
import tempfile
import unittest
from pathlib import Path
from src.server import VortexHandler
from src.styles import CSS_STYLESHEET
from src.ui import _build_file_table_rows


class MockVortexHandler(VortexHandler):
    """Test helper inheriting from VortexHandler with captured responses."""

    def __init__(self, directory: str):
        self.base_directory = str(Path(directory).resolve())
        self.directory = self.base_directory
        self.status = 200
        self.json_data = {}

    def _send_json(self, data, status=200):
        self.status = status
        self.json_data = data


class DirectorySizeBackendTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.base_path = Path(self.temp_dir).resolve()

        # Root file: 100 bytes
        (self.base_path / "root.txt").write_bytes(b"a" * 100)

        # Subdirectory with two files: 200 + 300 = 500 bytes
        self.sub_dir = self.base_path / "subdir"
        self.sub_dir.mkdir()
        (self.sub_dir / "file1.txt").write_bytes(b"b" * 200)
        (self.sub_dir / "file2.txt").write_bytes(b"c" * 300)

        # Empty directory: 0 bytes, 0 files
        self.empty_dir = self.base_path / "empty_dir"
        self.empty_dir.mkdir()

        # Directory with spaces: 50 bytes
        self.space_dir = self.base_path / "space dir"
        self.space_dir.mkdir()
        (self.space_dir / "item.txt").write_bytes(b"d" * 50)

        # Directory with Unicode: 60 bytes
        self.unicode_dir = self.base_path / "café"
        self.unicode_dir.mkdir()
        (self.unicode_dir / "item.txt").write_bytes(b"e" * 60)

        # Directory with literal #: 70 bytes
        self.hash_dir = self.base_path / "c#_dir"
        self.hash_dir.mkdir()
        (self.hash_dir / "item.txt").write_bytes(b"f" * 70)

        # Directory with literal %: 80 bytes
        self.percent_dir = self.base_path / "100%_dir"
        self.percent_dir.mkdir()
        (self.percent_dir / "item.txt").write_bytes(b"g" * 80)

        # Directory with literal text '%2F' in name: 90 bytes
        self.lit_2f_dir = self.base_path / "literal%2Fdir"
        self.lit_2f_dir.mkdir()
        (self.lit_2f_dir / "item.txt").write_bytes(b"h" * 90)

        # Out-of-root directory and symlink
        self.outside_temp = tempfile.mkdtemp()
        self.outside_dir = Path(self.outside_temp).resolve()
        (self.outside_dir / "secret.txt").write_bytes(b"s" * 500)
        os.symlink(self.outside_dir, self.base_path / "sym_outside")

        # In-root symlink pointing to subdir
        os.symlink(self.sub_dir, self.base_path / "sym_inside")

        self.handler = MockVortexHandler(str(self.base_path))

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        shutil.rmtree(self.outside_temp, ignore_errors=True)

    def test_missing_session_parameter(self):
        self.handler._handle_api_directory_size({})
        self.assertEqual(self.handler.status, 400)
        self.assertIn("Missing session parameter", self.handler.json_data.get("error", ""))

    def test_shared_root_totals(self):
        # Default "/"
        self.handler._handle_api_directory_size({"session": ["test-session"], "path": ["/"]})
        self.assertEqual(self.handler.status, 200)
        size = self.handler.json_data["size"]
        # Total files: root.txt(1) + subdir(2) + space(1) + unicode(1) + hash(1) + percent(1) + lit2f(1) = 8 files
        self.assertEqual(size["file_count"], 8)
        self.assertEqual(size["total_bytes"], 100 + 500 + 50 + 60 + 70 + 80 + 90)

    def test_omitted_path_backwards_compatibility(self):
        # Older clients omit path parameter
        self.handler._handle_api_directory_size({"session": ["test-session"]})
        self.assertEqual(self.handler.status, 200)
        size = self.handler.json_data["size"]
        self.assertEqual(size["file_count"], 8)

    def test_subdirectory_totals(self):
        self.handler._handle_api_directory_size({"session": ["test-session"], "path": ["/subdir/"]})
        self.assertEqual(self.handler.status, 200)
        size = self.handler.json_data["size"]
        self.assertEqual(size["file_count"], 2)
        self.assertEqual(size["total_bytes"], 500)

    def test_empty_directory_totals(self):
        self.handler._handle_api_directory_size({"session": ["test-session"], "path": ["/empty_dir/"]})
        self.assertEqual(self.handler.status, 200)
        size = self.handler.json_data["size"]
        self.assertEqual(size["file_count"], 0)
        self.assertEqual(size["total_bytes"], 0)
        self.assertEqual(size["total_formatted"], "0.0 B")

    def test_encoded_spaces_directory(self):
        self.handler._handle_api_directory_size({"session": ["test-session"], "path": ["/space%20dir/"]})
        self.assertEqual(self.handler.status, 200)
        size = self.handler.json_data["size"]
        self.assertEqual(size["file_count"], 1)
        self.assertEqual(size["total_bytes"], 50)

    def test_encoded_unicode_directory(self):
        self.handler._handle_api_directory_size({"session": ["test-session"], "path": ["/caf%C3%A9/"]})
        self.assertEqual(self.handler.status, 200)
        size = self.handler.json_data["size"]
        self.assertEqual(size["file_count"], 1)
        self.assertEqual(size["total_bytes"], 60)

    def test_encoded_hash_directory(self):
        self.handler._handle_api_directory_size({"session": ["test-session"], "path": ["/c%23_dir/"]})
        self.assertEqual(self.handler.status, 200)
        size = self.handler.json_data["size"]
        self.assertEqual(size["file_count"], 1)
        self.assertEqual(size["total_bytes"], 70)

    def test_encoded_percent_directory(self):
        self.handler._handle_api_directory_size({"session": ["test-session"], "path": ["/100%25_dir/"]})
        self.assertEqual(self.handler.status, 200)
        size = self.handler.json_data["size"]
        self.assertEqual(size["file_count"], 1)
        self.assertEqual(size["total_bytes"], 80)

    def test_encoded_literal_2f_directory(self):
        self.handler._handle_api_directory_size({"session": ["test-session"], "path": ["/literal%252Fdir/"]})
        self.assertEqual(self.handler.status, 200)
        size = self.handler.json_data["size"]
        self.assertEqual(size["file_count"], 1)
        self.assertEqual(size["total_bytes"], 90)

    def test_out_of_root_symlink_rejection(self):
        self.handler._handle_api_directory_size({"session": ["test-session"], "path": ["/sym_outside/"]})
        self.assertEqual(self.handler.status, 403)
        self.assertEqual(self.handler.json_data.get("error"), "Access denied")

    def test_in_root_symlink_acceptance(self):
        self.handler._handle_api_directory_size({"session": ["test-session"], "path": ["/sym_inside/"]})
        self.assertEqual(self.handler.status, 200)
        size = self.handler.json_data["size"]
        self.assertEqual(size["file_count"], 2)
        self.assertEqual(size["total_bytes"], 500)

    def test_nonexistent_directory(self):
        self.handler._handle_api_directory_size({"session": ["test-session"], "path": ["/nonexistent_folder/"]})
        self.assertEqual(self.handler.status, 404)
        self.assertEqual(self.handler.json_data.get("error"), "Directory not found")

    def test_file_target_rejected(self):
        # Targeting a file instead of a directory
        self.handler._handle_api_directory_size({"session": ["test-session"], "path": ["/root.txt"]})
        self.assertEqual(self.handler.status, 404)
        self.assertEqual(self.handler.json_data.get("error"), "Directory not found")

    def test_traversal_outside_root(self):
        # Traversal sequence should never inspect outside root
        self.handler._handle_api_directory_size({"session": ["test-session"], "path": ["/../../../../etc/passwd"]})
        self.assertEqual(self.handler.status, 404)

    def test_ui_link_encoding(self):
        rows = _build_file_table_rows(self.base_path, str(self.base_path))
        rows_str = "".join(rows)

        # Check href destinations are URL-encoded
        self.assertIn('href="space%20dir/"', rows_str)
        self.assertIn('href="caf%C3%A9/"', rows_str)
        self.assertIn('href="c%23_dir/"', rows_str)
        self.assertIn('href="100%25_dir/"', rows_str)
        self.assertIn('href="literal%252Fdir/"', rows_str)

        # Check visible text display names remain unencoded
        self.assertIn('>space dir/<', rows_str)
        self.assertIn('>café/<', rows_str)
        self.assertIn('>c#_dir/<', rows_str)
        self.assertIn('>100%_dir/<', rows_str)
        self.assertIn('>literal%2Fdir/<', rows_str)

        # Parent link in subdirectory
        sub_rows = _build_file_table_rows(self.sub_dir, str(self.base_path))
        self.assertIn('<tr data-parent="1"><td><a href="../">[..]</a></td><td></td><td></td></tr>', sub_rows)

    def test_ui_data_attributes_and_timestamps(self):
        rows = _build_file_table_rows(self.base_path, str(self.base_path))
        rows_str = "".join(rows)

        # File data attributes (root.txt is 100 bytes)
        self.assertIn('data-name="root.txt"', rows_str)
        self.assertIn('data-size="100"', rows_str)
        self.assertIn('data-isdir="0"', rows_str)
        self.assertIn('data-mtime="', rows_str)

        # Directory data attributes (subdir is a folder)
        self.assertIn('data-name="subdir"', rows_str)
        self.assertIn('data-size=""', rows_str)
        self.assertIn('data-isdir="1"', rows_str)
        self.assertIn('<td>-</td>', rows_str)

    def test_ui_special_character_escaping(self):
        # Create a file with quotes, ampersand, angle brackets in filename
        special_name = 'test "quotes" & <angles>.txt'
        (self.base_path / special_name).write_bytes(b"hello")

        rows = _build_file_table_rows(self.base_path, str(self.base_path))
        rows_str = "".join(rows)

        # In data-name attribute, quotes and HTML special chars must be HTML entity escaped
        self.assertIn('data-name="test &quot;quotes&quot; &amp; &lt;angles&gt;.txt"', rows_str)
        # Visible link text should also escape HTML
        self.assertIn('>test &quot;quotes&quot; &amp; &lt;angles&gt;.txt<', rows_str)

    def test_desktop_panel_equal_height_styles(self):
        # Desktop chat panel should stretch to row height without hardcoded max-height
        self.assertIn(".panel-chat {", CSS_STYLESHEET)
        self.assertIn("height: 100%;", CSS_STYLESHEET)
        self.assertNotIn("max-height: 550px;", CSS_STYLESHEET)
        self.assertNotIn("max-height: 450px;", CSS_STYLESHEET)

        # Chat messages absorbs height and enables internal scrolling
        self.assertIn(".chat-messages {", CSS_STYLESHEET)
        self.assertIn("flex: 1;", CSS_STYLESHEET)
        self.assertIn("min-height: 0;", CSS_STYLESHEET)
        self.assertIn("overflow-y: auto;", CSS_STYLESHEET)

        # Mobile layout maintains its natural height constraints
        self.assertIn("@media (max-width: 900px)", CSS_STYLESHEET)
        self.assertIn("max-height: 500px;", CSS_STYLESHEET)


if __name__ == "__main__":
    unittest.main()
