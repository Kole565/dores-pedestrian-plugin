"""WebSocket: /ws/streams/{id} — поток кадров (JPEG base64) + статистики."""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .streams import get_manager

logger = logging.getLogger("app.ws")
router = APIRouter()


@router.websocket("/ws/streams/{stream_id}")
async def ws_stream(websocket: WebSocket, stream_id: str) -> None:
    manager = get_manager()
    session = manager.get(stream_id)
    if session is None:
        await websocket.close(code=4404, reason="Stream not found")
        return

    await websocket.accept()
    loop = asyncio.get_running_loop()
    queue = session.subscribe(loop)

    # Приветственное сообщение — текущий статус + последний stats
    await websocket.send_json({
        "type": "status",
        "status": session.status.value,
    })

    # Если есть последний кадр — сразу отдадим, чтобы клиент не ждал
    snap = session.get_snapshot()
    if snap is not None:
        import base64
        await websocket.send_json({
            "type": "frame",
            "jpeg_b64": base64.b64encode(snap).decode("ascii"),
        })

    # Задача: читать сообщения от клиента (pause/resume — игнорируем пока,
    # но соединение должно оставаться открытым)
    async def _reader() -> None:
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        except Exception:  # noqa: BLE001
            pass

    reader_task = asyncio.create_task(_reader())

    try:
        while True:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=30.0)
            except asyncio.TimeoutError:
                # keep-alive: ping
                await websocket.send_json({"type": "ping"})
                continue

            await websocket.send_json(msg)

            if msg.get("type") == "status" and msg.get("status") in (
                "stopped", "error",
            ):
                break
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001
        logger.exception("WS error for stream %s", stream_id)
    finally:
        reader_task.cancel()
        session.unsubscribe(queue)
        try:
            await websocket.close()
        except Exception:  # noqa: BLE001
            pass
