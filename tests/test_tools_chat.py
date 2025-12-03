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
                }
                for _ in range(10)
            ]

    cfg = QortalConfig(max_chat_messages=3, default_chat_messages=2, max_chat_data_preview=50)
    result = await get_chat_messages(involving=["Q" * 34, "Q" * 34], limit=999, client=StubClient(), config=cfg)
    assert isinstance(result, list)
    assert len(result) == 3
    assert result[0]["data"].endswith("... (truncated)")


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
                "signature": signature,
            }

    result = await get_chat_message_by_signature(signature="1" * 10, client=StubClient())
    assert result["signature"] == "1" * 10


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
