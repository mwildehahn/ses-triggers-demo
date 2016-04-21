import base64
import json
from cryptography.hazmat.primitives.ciphers import (
    Cipher, algorithms, modes
)
from cryptography.hazmat.backends import default_backend


def decrypt_object(s3, kms, bucket, key):
    """Decrypt an object stored on s3 with KMS client side encryption.

    Args:
        s3: boto3 s3 client
        kms: boto3 kms client
        bucket (str): bucket name
        key (str): key name

    Returns:
        decrypted payload

    """

    # Fetch the encrypted payload
    encrypted = s3.get_object(Bucket=bucket, Key=key)
    metadata = encrypted['Metadata']

    # Unpack the encryption metadata
    envelope_key = base64.b64decode(metadata['x-amz-key-v2'])
    envelope_iv = base64.b64decode(metadata['x-amz-iv'])
    encrypt_ctx = json.loads(metadata['x-amz-matdesc'])
    encryption_key = kms.decrypt(CiphertextBlob=envelope_key, EncryptionContext=encrypt_ctx)
    original_size = int(metadata['x-amz-unencrypted-content-length'])

    # Decrypt the payload (AES/GCM/NoPadding)
    encrypted_payload = encrypted['Body'].read()
    auth_tag = encrypted_payload[original_size:]
    ciphertext = encrypted_payload[:original_size]
    decryptor = Cipher(
        algorithms.AES(encryption_key['Plaintext']),
        modes.GCM(envelope_iv, auth_tag),
        backend=default_backend(),
    ).decryptor()
    payload = decryptor.update(ciphertext) + decryptor.finalize()
    return payload
