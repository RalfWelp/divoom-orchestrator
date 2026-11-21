"""Configuration flow for Divoom Playlist."""

from homeassistant import config_entries


class DivoomPlaylistConfigFlow(config_entries.ConfigFlow, domain="divoom_playlist"):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        await self.async_set_unique_id("divoom_playlist")
        self._abort_if_unique_id_configured()
        if user_input is not None:
            return self.async_create_entry(title="Divoom Playlist", data={})
        return self.async_show_form(step_id="user")
