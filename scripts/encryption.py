#!/usr/bin/env python3
"""
Sicheres Verschlüsseln und Entschlüsseln von Zugangsdaten
Verwendet Fernet (symmetrische Verschlüsselung)
"""

import os
import base64
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
import logging

logger = logging.getLogger(__name__)


class CredentialEncryption:
    """Klasse für sichere Verschlüsselung von Zugangsdaten"""
    
    def __init__(self, encryption_key: str = None):
        """
        Initialisiert die Verschlüsselung
        
        Args:
            encryption_key: Encryption Key aus .env oder generiert
        """
        if encryption_key is None:
            encryption_key = os.getenv('ENCRYPTION_KEY')
        
        if not encryption_key:
            raise ValueError("ENCRYPTION_KEY nicht gesetzt! Bitte in .env definieren.")
        
        # Key aus String ableiten (PBKDF2)
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'finanzen_app_salt_v1',  # Fester Salt für Reproduzierbarkeit
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(encryption_key.encode()))
        
        self.cipher = Fernet(key)
    
    def encrypt(self, plaintext: str) -> str:
        """
        Verschlüsselt einen Text
        
        Args:
            plaintext: Klartextstring
        
        Returns:
            Verschlüsselter String (Base64-kodiert)
        """
        if not plaintext:
            return ""
        
        encrypted = self.cipher.encrypt(plaintext.encode())
        return base64.urlsafe_b64encode(encrypted).decode()
    
    def decrypt(self, encrypted_text: str) -> str:
        """
        Entschlüsselt einen Text
        
        Args:
            encrypted_text: Verschlüsselter String (Base64-kodiert)
        
        Returns:
            Entschlüsselter Klartextstring
        """
        if not encrypted_text:
            return ""
        
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_text.encode())
            decrypted = self.cipher.decrypt(encrypted_bytes)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Fehler beim Entschlüsseln: {e}")
            raise ValueError("Entschlüsselung fehlgeschlagen - falscher Key?")
    
    @staticmethod
    def generate_key() -> str:
        """
        Generiert einen neuen Encryption Key
        
        Returns:
            Hex-String (64 Zeichen)
        """
        return base64.urlsafe_b64encode(os.urandom(32)).decode()


def encrypt_credential(credential: str, key: str = None) -> str:
    """
    Helper-Funktion zum Verschlüsseln einer Credential
    
    Args:
        credential: Zu verschlüsselnde Credential
        key: Optional - Encryption Key (sonst aus .env)
    
    Returns:
        Verschlüsselter String
    """
    enc = CredentialEncryption(key)
    return enc.encrypt(credential)


def decrypt_credential(encrypted: str, key: str = None) -> str:
    """
    Helper-Funktion zum Entschlüsseln einer Credential
    
    Args:
        encrypted: Verschlüsselte Credential
        key: Optional - Encryption Key (sonst aus .env)
    
    Returns:
        Entschlüsselter String
    """
    enc = CredentialEncryption(key)
    return enc.decrypt(encrypted)


def main():
    """CLI für Verschlüsselung/Entschlüsselung"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Credentials verschlüsseln/entschlüsseln')
    parser.add_argument('--generate-key', action='store_true',
                       help='Neuen Encryption Key generieren')
    parser.add_argument('--encrypt', type=str,
                       help='Text verschlüsseln')
    parser.add_argument('--decrypt', type=str,
                       help='Text entschlüsseln')
    
    args = parser.parse_args()
    
    if args.generate_key:
        key = CredentialEncryption.generate_key()
        print(f"Neuer Encryption Key generiert:")
        print(f"ENCRYPTION_KEY={key}")
        print()
        print("⚠️ WICHTIG: Diesen Key in .env eintragen und SICHER aufbewahren!")
        print("Bei Verlust des Keys sind verschlüsselte Daten NICHT wiederherstellbar!")
        return
    
    if args.encrypt:
        try:
            enc = CredentialEncryption()
            encrypted = enc.encrypt(args.encrypt)
            print(f"Verschlüsselt: {encrypted}")
        except Exception as e:
            print(f"❌ Fehler: {e}")
            return
    
    if args.decrypt:
        try:
            enc = CredentialEncryption()
            decrypted = enc.decrypt(args.decrypt)
            print(f"Entschlüsselt: {decrypted}")
        except Exception as e:
            print(f"❌ Fehler: {e}")
            return


if __name__ == "__main__":
    main()
