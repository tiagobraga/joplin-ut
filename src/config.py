"""
Gerenciamento de Configuração e Credenciais do Joplin UT
"""

import os
import json
from pathlib import Path
from typing import Dict, Any

APP_NAME = "joplin-ut.braga"

def get_config_dir() -> Path:
    """
    Retorna o diretório de configurações do aplicativo.
    O AppArmor exige estritamente a escrita dentro de:
    ~/.config/joplin-ut.braga/
    """
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        base_dir = Path(xdg_config)
        if base_dir.name != APP_NAME:
            base_dir = base_dir / APP_NAME
    else:
        base_dir = Path.home() / ".config" / APP_NAME
    
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir

def get_data_dir() -> Path:
    """
    Retorna o diretório de dados do aplicativo.
    O AppArmor exige estritamente a escrita dentro de:
    ~/.local/share/joplin-ut.braga/
    """
    xdg_data = os.environ.get("XDG_DATA_HOME")
    if xdg_data:
        base_dir = Path(xdg_data)
        if base_dir.name != APP_NAME:
            base_dir = base_dir / APP_NAME
    else:
        base_dir = Path.home() / ".local" / "share" / APP_NAME
    
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir

def get_config_file_path() -> Path:
    return get_config_dir() / "settings.json"

DEFAULT_SETTINGS = {
    "server_url": "",
    "username": "",
    "password": "",
    "joplin_dir": "Joplin",
    "last_sync": "",
    "sync_on_startup": True,
    "sort_by": "updated_time",   # "updated_time", "created_time", "title"
    "sort_order": "DESC"         # "DESC", "ASC"
}

def load_settings() -> Dict[str, Any]:
    """Carrega as configurações salvas ou retorna as padrões."""
    cfg_file = get_config_file_path()
    if not cfg_file.exists():
        return DEFAULT_SETTINGS.copy()
    try:
        with open(cfg_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            merged = DEFAULT_SETTINGS.copy()
            merged.update(data)
            return merged
    except Exception as e:
        print(f"[Config] Erro ao carregar configurações de {cfg_file}: {e}")
        return DEFAULT_SETTINGS.copy()

def save_settings(settings: Dict[str, Any]) -> bool:
    """Salva o dicionário de configurações no disco."""
    try:
        cfg_file = get_config_file_path()
        current = load_settings()
        current.update(settings)
        with open(cfg_file, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=2, ensure_ascii=False)
        print(f"[Config] Configurações salvas com sucesso em: {cfg_file}")
        return True
    except Exception as e:
        print(f"[Config] Erro crítico ao salvar configurações em {cfg_file}: {e}")
        return False
