import pytest

from qortal_mcp.config import QortalConfig
from qortal_mcp.qortal_api import GroupNotFoundError, NodeUnreachableError
from qortal_mcp.tools.groups import (
    list_groups,
    get_groups_by_owner,
    get_groups_by_member,
    get_group,
    get_group_members,
    get_group_invites_by_address,
    get_group_invites_by_group,
    get_group_join_requests,
    get_group_bans,
)


@pytest.mark.asyncio
async def test_list_groups_clamps_limit_and_normalizes():
    class StubClient:
        async def fetch_groups(self, *, limit=None, offset=None, reverse=None):
            return [
                {
                    "groupId": i,
                    "groupName": f"Group {i}",
                    "owner": "Q" * 34,
                    "description": "d" * 2000,
                    "memberCount": i + 1,
                }
                for i in range(10)
            ]

    cfg = QortalConfig(max_groups=5, default_groups=3, max_name_data_preview=100)
    result = await list_groups(limit=50, client=StubClient(), config=cfg)
    assert isinstance(result, list)
    assert len(result) == 5
    assert result[0]["description"].endswith("... (truncated)")


@pytest.mark.asyncio
async def test_groups_by_owner_requires_valid_address():
    assert await get_groups_by_owner(address=None) == {"error": "Invalid Qortal address."}
    assert await get_groups_by_owner(address="bad") == {"error": "Invalid Qortal address."}


@pytest.mark.asyncio
async def test_groups_by_member_success_and_unreachable():
    class StubClient:
        async def fetch_groups_by_member(self, address: str):
            return [{"groupId": 1, "groupName": "demo", "owner": address, "memberCount": 2}]

    result = await get_groups_by_member(address="Q" * 34, client=StubClient())
    assert result[0]["id"] == 1

    class FailClient:
        async def fetch_groups_by_member(self, address: str):
            raise NodeUnreachableError("down")

    assert await get_groups_by_member(address="Q" * 34, client=FailClient()) == {"error": "Node unreachable"}


@pytest.mark.asyncio
async def test_group_detail_invalid_and_not_found():
    assert await get_group(group_id="x") == {"error": "Invalid group id."}

    class StubClient:
        async def fetch_group(self, group_id: int):
            raise GroupNotFoundError("missing")

    assert await get_group(group_id=1, client=StubClient()) == {"error": "Group not found."}


@pytest.mark.asyncio
async def test_group_members_validation_and_normalization():
    assert await get_group_members(group_id=0) == {"error": "Invalid group id."}
    assert await get_group_members(group_id=1, only_admins="yes") == {"error": "only_admins must be boolean."}

    class StubClient:
        async def fetch_group_members(self, group_id: int, **kwargs):
            return {
                "memberCount": 3,
                "adminCount": 1,
                "members": [
                    {"member": "Q" * 34, "joined": 1, "isAdmin": True},
                    {"member": "Q" * 34, "joined": 2, "isAdmin": False},
                ],
            }

    cfg = QortalConfig(max_group_members=1, default_group_members=1)
    result = await get_group_members(group_id=2, client=StubClient(), config=cfg)
    assert result["memberCount"] == 3
    assert len(result["members"]) == 1


@pytest.mark.asyncio
async def test_group_invites_and_bans_trim_and_map_errors():
    class StubClient:
        async def fetch_group_invites_by_address(self, address: str):
            return [{"groupId": i, "inviter": "Q" * 34, "invitee": "Q" * 34} for i in range(5)]

        async def fetch_group_invites_by_group(self, group_id: int):
            return [{"groupId": group_id, "inviter": "Q" * 34, "invitee": "Q" * 34} for _ in range(5)]

        async def fetch_group_join_requests(self, group_id: int):
            raise NodeUnreachableError("down")

        async def fetch_group_bans(self, group_id: int):
            return [
                {"groupId": group_id, "offender": "Q" * 34, "admin": "Q" * 34, "reason": "r" * 200}
                for _ in range(5)
            ]

    cfg = QortalConfig(max_group_events=2, max_name_data_preview=50)
    invites = await get_group_invites_by_address(address="Q" * 34, client=StubClient(), config=cfg)
    assert len(invites) == 2

    invites_group = await get_group_invites_by_group(group_id=2, client=StubClient(), config=cfg)
    assert len(invites_group) == 2

    join_requests = await get_group_join_requests(group_id=2, client=StubClient(), config=cfg)
    assert join_requests == {"error": "Node unreachable"}

    bans = await get_group_bans(group_id=2, client=StubClient(), config=cfg)
    assert len(bans) == 2
    assert bans[0]["reason"].endswith("... (truncated)")
