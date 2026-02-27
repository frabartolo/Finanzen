#!/usr/bin/env python3
"""
Management-Tool für verschlüsselte Bankzugangsdaten
"""

import sys
import os
from pathlib import Path
import json
import logging

# Pfad zum Projekt-Root hinzufügen
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.encryption import CredentialEncryption
from scripts.utils import load_config

# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

CREDENTIALS_FILE = Path(__file__).parent.parent / "data" / "credentials.enc"


class CredentialManager:
    """Manager für verschlüsselte Zugangsdaten"""
    
    def __init__(self):
        self.encryption = CredentialEncryption()
        self.credentials = {}
        self._load_credentials()
    
    def _load_credentials(self):
        """Lädt verschlüsselte Credentials aus Datei"""
        if CREDENTIALS_FILE.exists():
            try:
                with open(CREDENTIALS_FILE, 'r') as f:
                    encrypted_data = f.read()
                
                decrypted_json = self.encryption.decrypt(encrypted_data)
                self.credentials = json.loads(decrypted_json)
                
                logger.info(f"✅ {len(self.credentials)} Credentials geladen")
            except Exception as e:
                logger.error(f"❌ Fehler beim Laden der Credentials: {e}")
                self.credentials = {}
        else:
            logger.info("ℹ️ Keine gespeicherten Credentials gefunden")
    
    def _save_credentials(self):
        """Speichert verschlüsselte Credentials in Datei"""
        try:
            # Stelle sicher, dass Verzeichnis existiert
            CREDENTIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
            
            json_data = json.dumps(self.credentials, indent=2)
            encrypted_data = self.encryption.encrypt(json_data)
            
            with open(CREDENTIALS_FILE, 'w') as f:
                f.write(encrypted_data)
            
            # Datei nur für Owner lesbar machen
            os.chmod(CREDENTIALS_FILE, 0o600)
            
            logger.info("✅ Credentials sicher gespeichert")
        except Exception as e:
            logger.error(f"❌ Fehler beim Speichern: {e}")
    
    def store_credential(self, key: str, value: str):
        """
        Speichert eine Credential verschlüsselt
        
        Args:
            key: Identifier (z.B. "POSTBANK_PIN")
            value: Wert (wird verschlüsselt gespeichert)
        """
        self.credentials[key] = value
        self._save_credentials()
        logger.info(f"✅ Credential '{key}' gespeichert")
    
    def get_credential(self, key: str, default: str = None) -> str:
        """
        Holt eine entschlüsselte Credential
        
        Args:
            key: Identifier
            default: Fallback-Wert
        
        Returns:
            Entschlüsselte Credential oder default
        """
        return self.credentials.get(key, default)
    
    def delete_credential(self, key: str):
        """Löscht eine Credential"""
        if key in self.credentials:
            del self.credentials[key]
            self._save_credentials()
            logger.info(f"✅ Credential '{key}' gelöscht")
        else:
            logger.warning(f"⚠️ Credential '{key}' nicht gefunden")
    
    def list_credentials(self):
        """Listet alle gespeicherten Credential-Keys auf"""
        if not self.credentials:
            logger.info("📭 Keine Credentials gespeichert")
            return []
        
        logger.info(f"📋 {len(self.credentials)} gespeicherte Credentials:")
        for key in self.credentials.keys():
            print(f"  - {key}")
        
        return list(self.credentials.keys())
    
    def migrate_from_env(self):
        """
        Migriert Credentials aus .env in verschlüsselte Datei
        """
        logger.info("🔄 Starte Migration aus .env...")
        
        credentials_to_migrate = [
            'POSTBANK_LOGIN',
            'POSTBANK_PIN',
            'DIBA_LOGIN',
            'DIBA_PIN',
        ]
        
        migrated = 0
        for cred_key in credentials_to_migrate:
            value = os.getenv(cred_key)
            if value and value not in ['Ihr_Postbank_Login', 'Ihre_Postbank_PIN', '']:
                self.store_credential(cred_key, value)
                migrated += 1
                logger.info(f"  ✅ {cred_key} migriert")
        
        if migrated > 0:
            logger.info(f"✅ {migrated} Credentials erfolgreich migriert")
            logger.info("⚠️ WICHTIG: Entfernen Sie nun die Credentials aus der .env Datei!")
        else:
            logger.info("ℹ️ Keine Credentials zum Migrieren gefunden")


def main():
    """CLI für Credential-Management"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Verschlüsselte Credentials verwalten')
    subparsers = parser.add_subparsers(dest='command', help='Verfügbare Befehle')
    
    # Store
    store_parser = subparsers.add_parser('store', help='Credential speichern')
    store_parser.add_argument('key', help='Credential-Key (z.B. POSTBANK_PIN)')
    store_parser.add_argument('value', help='Credential-Wert')
    
    # Get
    get_parser = subparsers.add_parser('get', help='Credential abrufen')
    get_parser.add_argument('key', help='Credential-Key')
    
    # Delete
    delete_parser = subparsers.add_parser('delete', help='Credential löschen')
    delete_parser.add_argument('key', help='Credential-Key')
    
    # List
    list_parser = subparsers.add_parser('list', help='Alle Credentials auflisten')
    
    # Migrate
    migrate_parser = subparsers.add_parser('migrate', help='Aus .env migrieren')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        manager = CredentialManager()
        
        if args.command == 'store':
            manager.store_credential(args.key, args.value)
        
        elif args.command == 'get':
            value = manager.get_credential(args.key)
            if value:
                print(f"{args.key}: {value}")
            else:
                print(f"❌ Credential '{args.key}' nicht gefunden")
        
        elif args.command == 'delete':
            manager.delete_credential(args.key)
        
        elif args.command == 'list':
            manager.list_credentials()
        
        elif args.command == 'migrate':
            manager.migrate_from_env()
    
    except Exception as e:
        logger.error(f"❌ Fehler: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
