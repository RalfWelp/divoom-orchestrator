"""Configuration flow for Divoom Orchestrator."""

from homeassistant import config_entries


class DivoomOrchestratorConfigFlow(config_entries.ConfigFlow, domain="divoom_orchestrator"):
    """Allow one instance of the playlist controller."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Create the single configuration entry."""
        await self.async_set_unique_id("divoom_orchestrator")
        self._abort_if_unique_id_configured()
        if user_input is not None:
            return self.async_create_entry(title="Divoom Orchestrator", data={})
        return self.async_show_form(step_id="user")
