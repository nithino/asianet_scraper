"""The Asianet Scraper integration."""
import logging

_LOGGER = logging.getLogger(__name__)

DOMAIN = "asianet_scraper"

async def async_setup(hass, config):
    """Set up the Asianet Scraper component."""
    return True

async def async_setup_entry(hass, entry):
    """Set up Asianet Scraper from a config entry."""
    return True
