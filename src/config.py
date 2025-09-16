import yaml
import os
from typing import Any, Dict
import logging

logger = logging.getLogger(__name__)

class Config:
    def __init__(self, config_path: str = None):
        self.config_path = config_path or 'configs/config.yaml'
        self.config = {}
        self.env_vars = {}
        self.load()
        
    def load(self):
        """Load configuration from file and environment"""
        # Load from YAML
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                self.config = yaml.safe_load(f)
                
        # Load from environment variables
        self.env_vars = {
            'discord_token': os.getenv('DISCORD_TOKEN'),
            'openai_api_key': os.getenv('OPENAI_API_KEY'),
            'anthropic_api_key': os.getenv('ANTHROPIC_API_KEY'),
            'search_api_key': os.getenv('SEARCH_API_KEY'),
            'local_model': os.getenv('LOCAL_MODEL')
        }
        
    def get(self, key: str, default: Any = None) -> Any:
        """Get config value using dot notation"""
        # Check environment variables first
        env_key = key.replace('.', '_')
        if env_key in self.env_vars and self.env_vars[env_key]:
            return self.env_vars[env_key]
            
        # Navigate through nested config
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
                
        return value
