import pytest

from dstack._internal.server.services.encryption import (
    EncryptionError,
    decrypt,
    encrypt,
    encryption_keys_context,
    get_identity_encryption_key,
)
from dstack._internal.server.services.encryption.keys.aes import (
    AESEncryptionKey,
    AESEncryptionKeyConfig,
)


class TestEncrypt:
    def test_encrypts_with_identity_when_no_keys_set(self):
        text = "some text"
        assert encrypt(text) == f"enc:identity:{text}"

    def test_encrypts_with_first_key(self):
        text = "some text"
        with encryption_keys_context(
            [
                AESEncryptionKey(
                    AESEncryptionKeyConfig(secret="cR2r1JmkPyL6edBQeHKz6ZBjCfS2oWk87Gc2G3wHVoA=")
                ),
                get_identity_encryption_key(),
            ]
        ):
            assert encrypt(plaintext=text).startswith("enc:aes:")


class TestDecrypt:
    def test_tries_all_keys(self):
        ciphertext = "enc:identity:encrypted text"
        with pytest.raises(EncryptionError):
            with encryption_keys_context(
                [
                    AESEncryptionKey(
                        AESEncryptionKeyConfig(
                            secret="cR2r1JmkPyL6edBQeHKz6ZBjCfS2oWk87Gc2G3wHVoA="
                        )
                    ),
                    AESEncryptionKey(
                        AESEncryptionKeyConfig(
                            secret="4nr0Hr4bck/xURGbpdDwnDwBP1iGnTtYZT752h/kWno="
                        )
                    ),
                ]
            ):
                decrypt(ciphertext)
        with encryption_keys_context(
            [
                AESEncryptionKey(
                    AESEncryptionKeyConfig(secret="cR2r1JmkPyL6edBQeHKz6ZBjCfS2oWk87Gc2G3wHVoA=")
                ),
                AESEncryptionKey(
                    AESEncryptionKeyConfig(secret="4nr0Hr4bck/xURGbpdDwnDwBP1iGnTtYZT752h/kWno=")
                ),
                get_identity_encryption_key(),
            ]
        ):
            assert decrypt(ciphertext) == "encrypted text"