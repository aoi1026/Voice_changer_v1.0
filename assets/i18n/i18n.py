import os
import sys
import json
from pathlib import Path

now_dir = os.getcwd()
sys.path.append(now_dir)


class I18nAuto:
    """English only. Loads en_US.json for all UI strings."""
    LANGUAGE_PATH = os.path.join(now_dir, "assets", "i18n", "languages")
    DEFAULT_LANG = "en_US"

    def __init__(self, language=None):
        self.language = self.DEFAULT_LANG
        self.language_map = self._load_language_list()

    def _load_language_list(self):
        try:
            file_path = Path(self.LANGUAGE_PATH) / f"{self.DEFAULT_LANG}.json"
            with open(file_path, "r", encoding="utf-8") as file:
                return json.load(file)
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Failed to load language file for {self.DEFAULT_LANG}. Check if {self.DEFAULT_LANG}.json exists."
            )

    def _get_available_languages(self):
        return [self.DEFAULT_LANG]

    def __call__(self, key):
        return self.language_map.get(key, key)
