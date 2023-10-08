from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.fernet import Fernet
import base64
import os
from dotenv import load_dotenv

load_dotenv()


SALT = os.getenv("SALT")

def generate_key(password):
    salt = SALT.encode()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key

def encrypt(message, key):
    encrypted_key = generate_key(key)
    f = Fernet(encrypted_key)
    encrypted_message = f.encrypt(message.encode())
    return encrypted_message

def decrypt(encrypted_message, key):
    encrypted_key = generate_key(key)
    f = Fernet(encrypted_key)
    decrypted_message = f.decrypt(encrypted_message)
    return decrypted_message.decode()



