"""Administrator-only community search, preview and import."""

from pathlib import Path
from uuid import uuid4

import voluptuous as vol
from homeassistant.components import websocket_api

from . import community

DOMAIN = "divoom_orchestrator"


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "divoom_orchestrator/community_search",
    vol.Required("query"): vol.All(str, vol.Length(min=1, max=100)),
    vol.Required("page"): vol.All(int, vol.Range(min=1, max=100)),
    vol.Required("sort"): vol.In([0, 1]),
})
@websocket_api.async_response
async def websocket_search(hass, connection, msg):
    try:
        result = await hass.async_add_executor_job(
            community.search, msg["query"], msg["page"], msg["sort"]
        )
    except (OSError, ValueError) as err:
        connection.send_error(msg["id"], "community_search_failed", str(err))
        return
    searches = hass.data[DOMAIN].setdefault("community", {})
    search_id = uuid4().hex
    searches[search_id] = {
        item["id"]: {"work": item, "content": None} for item in result["works"]
    }
    while len(searches) > 10:
        searches.pop(next(iter(searches)))
    connection.send_result(msg["id"], {"search_id": search_id, **result})


def selected(hass, search_id, gallery_id):
    item = hass.data[DOMAIN].get("community", {}).get(search_id, {}).get(gallery_id)
    if item is None or not item["work"]["importable"]:
        raise ValueError("Dieses Werk ist nicht freigegeben oder nicht mehr in den Suchergebnissen")
    return item


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "divoom_orchestrator/community_preview",
    vol.Required("search_id"): str,
    vol.Required("gallery_id"): vol.All(int, vol.Range(min=1)),
})
@websocket_api.async_response
async def websocket_preview(hass, connection, msg):
    try:
        item = selected(hass, msg["search_id"], msg["gallery_id"])
        if item["content"] is None:
            item["content"] = await hass.async_add_executor_job(community.render, msg["gallery_id"])
        result = community.encoded(item["content"])
    except (OSError, ValueError) as err:
        connection.send_error(msg["id"], "community_preview_failed", str(err))
        return
    connection.send_result(msg["id"], {"data": result})


@websocket_api.require_admin
@websocket_api.websocket_command({
    vol.Required("type"): "divoom_orchestrator/community_import",
    vol.Required("search_id"): str,
    vol.Required("gallery_id"): vol.All(int, vol.Range(min=1)),
    vol.Required("folder"): str,
})
@websocket_api.async_response
async def websocket_import(hass, connection, msg):
    try:
        item = selected(hass, msg["search_id"], msg["gallery_id"])
        if item["content"] is None:
            raise ValueError("Bitte zuerst die Vorschau laden")
        path = await hass.async_add_executor_job(
            community.save, Path(hass.config.path("pixelart")), msg["folder"],
            msg["gallery_id"], item["content"],
        )
    except FileExistsError:
        connection.send_error(msg["id"], "already_exists", "GIF existiert bereits und wurde nicht überschrieben")
        return
    except (OSError, ValueError) as err:
        connection.send_error(msg["id"], "community_import_failed", str(err))
        return
    connection.send_result(msg["id"], {"file": path})


def register(hass):
    for command in (websocket_search, websocket_preview, websocket_import):
        websocket_api.async_register_command(hass, command)
