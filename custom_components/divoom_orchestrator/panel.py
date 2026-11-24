"""Register the Home Assistant sidebar panel."""

from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.components import panel_custom
from homeassistant.core import HomeAssistant

PANEL_URL = "/divoom-orchestrator-static/panel.js"
PANEL_VERSION = "0.4.6"


async def async_register_panel(hass: HomeAssistant) -> None:
    """Make the frontend module and admin-only panel available."""
    frontend = Path(__file__).parent / "frontend" / "panel.js"
    await hass.http.async_register_static_paths(
        [StaticPathConfig(PANEL_URL, str(frontend), False)]
    )
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path="divoom-orchestrator",
        webcomponent_name="divoom-orchestrator-panel",
        sidebar_title="Divoom Orchestrator",
        sidebar_icon="mdi:animation-play",
        module_url=f"{PANEL_URL}?v={PANEL_VERSION}",
        require_admin=True,
    )
