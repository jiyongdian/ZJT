import os
import sys
import unittest
from unittest.mock import patch


current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)


class TestAgentImagePreferences(unittest.TestCase):
    def test_sync_agent_image_preferences_persists_ratio_and_resolution(self):
        from api.script_writer import sync_agent_image_preferences

        saved = {}

        with patch("api.script_writer.get_image_preferences", return_value={"ratio": "1:1"}), \
             patch("api.script_writer.set_image_preferences") as mock_set:
            parts = sync_agent_image_preferences(
                user_id="42",
                world_id="1",
                prefs={
                    "ratio": "9:16",
                    "resolution": "2K",
                    "model_name": "Seedream 5.0",
                },
            )

            saved.update(mock_set.call_args.args[2])

        self.assertEqual(saved["ratio"], "9:16")
        self.assertEqual(saved["resolution"], "2K")
        self.assertIn("9:16", ", ".join(parts))
        self.assertIn("2K", ", ".join(parts))

    def test_sync_agent_image_preferences_persists_auto_ratio_to_clear_old_value(self):
        from api.script_writer import sync_agent_image_preferences

        with patch("api.script_writer.get_image_preferences", return_value={"ratio": "9:16"}), \
             patch("api.script_writer.set_image_preferences") as mock_set:
            sync_agent_image_preferences(
                user_id="42",
                world_id="1",
                prefs={"ratio": "auto"},
            )

        self.assertEqual(mock_set.call_args.args[2]["ratio"], "auto")


if __name__ == "__main__":
    unittest.main()
