import pytest

from qortal_mcp.config import QortalConfig
from qortal_mcp.qortal_api import InvalidAddressError, NodeUnreachableError, QortalApiError
from qortal_mcp.tools.chat import (
    get_chat_messages,
    count_chat_messages,
    get_chat_message_by_signature,
    get_active_chats,
)


@pytest.mark.asyncio
async def test_chat_messages_requires_criteria():
    result = await get_chat_messages()
    assert result == {"error": "Either txGroupId or two involving addresses are required."}

    result = await get_chat_messages(tx_group_id=1, involving=["Q" * 34, "Q" * 34])
    assert "either txGroupId or two involving addresses" in result["error"]

    result = await get_chat_messages(involving=["bad", "Q" * 34])
    assert result == {"error": "Invalid Qortal address in involving filter."}


@pytest.mark.asyncio
async def test_chat_messages_validation_rules():
    result = await get_chat_messages(involving=["Q" * 34, "Q" * 34], before=1)
    assert result == {"error": "Invalid before timestamp."}

    result = await get_chat_messages(involving=["Q" * 34, "Q" * 34], encoding="invalid")
    assert result == {"error": "Invalid encoding."}

    result = await get_chat_messages(involving=["Q" * 34, "Q" * 34], reference="***")
    assert result == {"error": "Invalid reference."}


@pytest.mark.asyncio
async def test_chat_messages_clamps_limit_and_truncates():
    class StubClient:
        async def fetch_chat_messages(self, **kwargs):
            return [
                {
                    "timestamp": 1,
                    "txGroupId": 0,
                    "sender": "Q" * 34,
                    "data": "x" * 5000,
                    "isText": True,
                    "isEncrypted": False,
                }
                for _ in range(10)
            ]

    cfg = QortalConfig(max_chat_messages=3, default_chat_messages=2, max_chat_data_preview=50)
    result = await get_chat_messages(involving=["Q" * 34, "Q" * 34], limit=999, client=StubClient(), config=cfg)
    assert isinstance(result, list)
    assert len(result) == 3
    assert result[0]["data"].endswith("... (truncated)")
    assert "decodedText" not in result[0]


@pytest.mark.asyncio
async def test_chat_messages_error_mapping():
    class StubClient:
        async def fetch_chat_messages(self, **kwargs):
            raise NodeUnreachableError("down")

    result = await get_chat_messages(involving=["Q" * 34, "Q" * 34], client=StubClient())
    assert result == {"error": "Node unreachable"}


@pytest.mark.asyncio
async def test_count_chat_messages_maps_count():
    class StubClient:
        async def count_chat_messages(self, **kwargs):
            return 7

    result = await count_chat_messages(involving=["Q" * 34, "Q" * 34], client=StubClient())
    assert result == {"count": 7}

    class UnauthorizedClient:
        async def count_chat_messages(self, **kwargs):
            raise InvalidAddressError("bad")

    result = await count_chat_messages(involving=["Q" * 34, "Q" * 34], client=UnauthorizedClient())
    assert result == {"error": "Invalid Qortal address."}

    class UnreachableClient:
        async def count_chat_messages(self, **kwargs):
            raise NodeUnreachableError("down")

    assert await count_chat_messages(involving=["Q" * 34, "Q" * 34], client=UnreachableClient()) == {"error": "Node unreachable"}


@pytest.mark.asyncio
async def test_chat_message_by_signature_validation_and_normalization():
    assert await get_chat_message_by_signature(signature=None) == {"error": "Invalid signature."}
    assert await get_chat_message_by_signature(signature="bad!") == {"error": "Invalid signature."}

    class StubClient:
        async def fetch_chat_message(self, signature, encoding=None):
            return {
                "timestamp": 1,
                "txGroupId": 0,
                "sender": "Q" * 34,
                "data": "data",
                "isText": True,
                "isEncrypted": False,
                "signature": signature,
            }

    result = await get_chat_message_by_signature(signature="1" * 10, client=StubClient())
    assert result["signature"] == "1" * 10
    assert "decodedText" not in result


@pytest.mark.asyncio
async def test_active_chats_validation_and_mapping():
    assert await get_active_chats(address="bad") == {"error": "Invalid Qortal address."}

    class StubClient:
        async def fetch_active_chats(self, address, **kwargs):
            return {
                "groups": [
                    {"groupId": 1, "groupName": "g", "data": "x" * 500},
                ],
                "direct": [
                    {"address": address, "name": "n", "timestamp": 1, "sender": address, "senderName": "s"},
                ],
            }

    cfg = QortalConfig(max_chat_data_preview=10)
    result = await get_active_chats(address="Q" * 34, client=StubClient(), config=cfg)
    assert result["groups"][0]["data"].endswith("... (truncated)")
    assert result["direct"][0]["address"] == "Q" * 34


@pytest.mark.asyncio
async def test_decode_text_base58_and_base64():
    class StubClient:
        async def fetch_chat_messages(self, **kwargs):
            return [
                {"data": "Cn8eVZg", "encoding": "BASE58", "isText": True, "isEncrypted": False},
                {"data": "aGVsbG8=", "encoding": "BASE64", "isText": True, "isEncrypted": False},
            ]

    cfg = QortalConfig(max_chat_messages=5, default_chat_messages=5, max_chat_data_preview=10)
    result = await get_chat_messages(involving=["Q" * 34, "Q" * 34], decode_text=True, client=StubClient(), config=cfg)
    assert result[0]["decodedText"] == "hello"
    assert result[1]["decodedText"] == "hello"
    assert result[0].get("decodedTextTruncated") is False


@pytest.mark.asyncio
async def test_decode_text_skips_encrypted_or_binary():
    class StubClient:
        async def fetch_chat_messages(self, **kwargs):
            return [
                {"data": "Cn8eVZg", "encoding": "BASE58", "isText": True, "isEncrypted": True},
                {"data": "%%%notbase58%%%", "encoding": "BASE58", "isText": True, "isEncrypted": False},
            ]

    result = await get_chat_messages(involving=["Q" * 34, "Q" * 34], decode_text=True, client=StubClient())
    assert "decodedText" not in result[0]
    assert "decodedText" not in result[1]


@pytest.mark.asyncio
async def test_decode_text_truncates_decoded_payload():
    long_plain = "a" * 200
    import base64

    encoded = base64.b64encode(long_plain.encode("utf-8")).decode("utf-8")

    class StubClient:
        async def fetch_chat_messages(self, **kwargs):
            return [{"data": encoded, "encoding": "BASE64", "isText": True, "isEncrypted": False}]

    cfg = QortalConfig(max_chat_data_preview=50)
    result = await get_chat_messages(involving=["Q" * 34, "Q" * 34], decode_text=True, client=StubClient(), config=cfg)
    assert result[0]["decodedText"].endswith("... (truncated)")
    assert result[0]["decodedTextTruncated"] is True


@pytest.mark.asyncio
async def test_chat_message_by_signature_error_mapping():
    class FailClient:
        async def fetch_chat_message(self, signature, encoding=None):
            raise NodeUnreachableError("down")

    assert await get_chat_message_by_signature(signature="1" * 10, client=FailClient()) == {"error": "Node unreachable"}

    class ApiClient:
        async def fetch_chat_message(self, signature, encoding=None):
            raise QortalApiError("bad")

    assert await get_chat_message_by_signature(signature="1" * 10, client=ApiClient()) == {"error": "Qortal API error."}


@pytest.mark.asyncio
async def test_chat_messages_decode_text_type_validation():
    result = await get_chat_messages(involving=["Q" * 34, "Q" * 34], decode_text="yes")
    assert result == {"error": "decode_text must be boolean."}
