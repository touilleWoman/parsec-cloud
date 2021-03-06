import pytest
from pendulum import Pendulum

from tests.common import freeze_time


@pytest.mark.trio
@pytest.mark.backend_not_populated
async def test_lazy_root_manifest_generation(
    running_backend, backend_data_binder, local_db_factory, fs_factory, coolorg, alice
):
    with freeze_time("2000-01-01"):
        await backend_data_binder.bind_organization(
            coolorg, alice, initial_user_manifest_in_v0=True
        )
    local_db = local_db_factory(alice, user_manifest_in_v0=True)

    async with fs_factory(alice, local_db) as fs:
        with freeze_time("2000-01-02"):
            stat = await fs.stat("/")

        assert stat == {
            "type": "root",
            "created": Pendulum(2000, 1, 2),
            "updated": Pendulum(2000, 1, 2),
            "base_version": 0,
            "is_folder": True,
            "is_placeholder": True,
            "need_sync": True,
            "children": [],
        }

        with freeze_time("2000-01-03"):
            await fs.sync("/")

        stat = await fs.stat("/")
        assert stat == {
            "type": "root",
            "created": Pendulum(2000, 1, 2),
            "updated": Pendulum(2000, 1, 2),
            "base_version": 1,
            "is_folder": True,
            "is_placeholder": False,
            "need_sync": False,
            "children": [],
        }


@pytest.mark.trio
@pytest.mark.backend_not_populated
async def test_concurrent_devices_agreed_on_root_manifest(
    running_backend, backend_data_binder, local_db_factory, fs_factory, coolorg, alice, alice2
):
    with freeze_time("2000-01-01"):
        await backend_data_binder.bind_organization(
            coolorg, alice, initial_user_manifest_in_v0=True
        )
        await backend_data_binder.bind_device(alice2, initial_user_manifest_in_v0=True)

    alice_local_db = local_db_factory(alice, user_manifest_in_v0=True)
    alice2_local_db = local_db_factory(alice2, user_manifest_in_v0=True)

    async with fs_factory(alice, alice_local_db) as fs1, fs_factory(alice2, alice2_local_db) as fs2:

        with freeze_time("2000-01-03"):
            await fs1.workspace_create("/from_1")
        with freeze_time("2000-01-04"):
            await fs2.workspace_create("/from_2")

        with fs1.event_bus.listen() as spy:
            with freeze_time("2000-01-05"):
                await fs1.sync("/")
        date_sync = Pendulum(2000, 1, 5)
        spy.assert_events_exactly_occured(
            [
                ("fs.entry.minimal_synced", {"path": "/", "id": spy.ANY}, date_sync),
                ("fs.entry.minimal_synced", {"path": "/from_1", "id": spy.ANY}, date_sync),
                ("fs.entry.synced", {"path": "/", "id": spy.ANY}, date_sync),
                ("fs.entry.synced", {"path": "/from_1", "id": spy.ANY}, date_sync),
            ]
        )

        with fs2.event_bus.listen() as spy:
            with freeze_time("2000-01-06"):
                await fs2.sync("/")
        date_sync = Pendulum(2000, 1, 6)
        spy.assert_events_exactly_occured(
            [
                ("fs.entry.minimal_synced", {"path": "/", "id": spy.ANY}, date_sync),
                ("fs.entry.minimal_synced", {"path": "/from_2", "id": spy.ANY}, date_sync),
                ("fs.entry.synced", {"path": "/", "id": spy.ANY}, date_sync),
                ("fs.entry.synced", {"path": "/from_2", "id": spy.ANY}, date_sync),
            ]
        )

        with fs1.event_bus.listen() as spy:
            with freeze_time("2000-01-07"):
                await fs1.sync("/")
        date_sync = Pendulum(2000, 1, 7)
        spy.assert_events_exactly_occured(
            [
                (
                    "fs.entry.remote_changed",
                    {"path": "/", "id": spy.ANY},
                    date_sync,
                )  # TODO: really needed ?
            ]
        )

    stat1 = await fs1.stat("/")
    stat2 = await fs2.stat("/")
    assert stat1 == {
        "type": "root",
        "created": Pendulum(2000, 1, 3),
        "updated": Pendulum(2000, 1, 4),
        "base_version": 3,
        "is_folder": True,
        "is_placeholder": False,
        "need_sync": False,
        "children": ["from_1", "from_2"],
    }
    assert stat1 == stat2
