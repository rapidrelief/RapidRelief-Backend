import asyncio
from contextlib import suppress
from typing import Callable

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.core.config import settings
from app.routes.sos import get_active_sos
from app.routes.zones import get_zone_logs, get_zones_map

router = APIRouter(tags=["realtime"])


async def consume_client_messages(websocket: WebSocket):
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        return
    except asyncio.CancelledError:
        raise
    except (OSError, RuntimeError):
        return


async def stream_snapshot(websocket: WebSocket, stream_type: str, loader: Callable[[], dict]):
    await websocket.accept()
    receiver_task = asyncio.create_task(consume_client_messages(websocket))

    try:
        while True:
            if receiver_task.done():
                break

            try:
                data = loader()
            except Exception as err:
                data = {"error": str(err)}

            await websocket.send_json({
                "type": stream_type,
                "data": data,
            })

            await asyncio.sleep(settings.realtime_stream_interval_seconds)

    except WebSocketDisconnect:
        return
    except asyncio.CancelledError:
        return
    except OSError:
        return
    except RuntimeError:
        return
    finally:
        receiver_task.cancel()
        with suppress(asyncio.CancelledError):
            await receiver_task

        if websocket.client_state == WebSocketState.CONNECTED:
            try:
                await websocket.close()
            except RuntimeError:
                pass


@router.websocket("/ws/zones")
async def zones_stream(websocket: WebSocket):
    await stream_snapshot(websocket, "zones", get_zones_map)


@router.websocket("/ws/sos/active")
async def active_sos_stream(websocket: WebSocket):
    await stream_snapshot(websocket, "active_sos", get_active_sos)


@router.websocket("/ws/zones/{zone_id}/logs")
async def zone_logs_stream(websocket: WebSocket, zone_id: int):
    await stream_snapshot(
        websocket,
        "zone_logs",
        lambda: get_zone_logs(zone_id),
    )
