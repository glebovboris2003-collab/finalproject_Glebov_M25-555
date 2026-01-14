import threading
from typing import Dict, Any
import json
import os

class SettingsLoader:
    _instance = None
    _lock = threading.Lock()  # Для потокобезопасности

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config_path='config.json'):
        if hasattr(self, '_initialized') and self._initialized:
            return  # Чтобы не перезаписывать при повторных вызовах
        self.config_path = config_path
        self._config = {}
        self.reload()
        self._initialized = True

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)

    def reload(self):
        """Загружает конфигурацию из файла."""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                self._config = json.load(f)
        else:
            self._config = {}  # Или задать дефолтные значения


