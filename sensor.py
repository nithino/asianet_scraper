"""
Asianet Broadband JSON Sensor for Home Assistant
Returns complete API response as JSON for flexible template sensor creation
"""

import logging
import asyncio
import aiohttp
import async_timeout
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import voluptuous as vol
import re
from urllib.parse import urljoin
import json

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_SCAN_INTERVAL = timedelta(days=1)
BASE_URL = "https://sms.ali.asianetindia.com"
LOGIN_URL = f"{BASE_URL}/subscriber"
API_ENDPOINT = "/api/subscribers/portal/details"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): cv.time_period,
})

async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType = None,
) -> None:
    """Set up the Asianet sensor platform."""
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]
    scan_interval = config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    
    session = async_get_clientsession(hass)
    api_client = AsianetAuthenticatedClient(session, username, password)
    
    # Create single sensor that returns all JSON data
    sensor = AsianetJSONSensor(api_client)
    
    async_add_entities([sensor], True)

class AsianetAuthenticatedClient:
    """Authenticated client for Asianet API."""
    
    def __init__(self, session: aiohttp.ClientSession, username: str, password: str):
        """Initialize the authenticated client."""
        self.session = session
        self.username = username
        self.password = password
        self.csrf_token = None
        self.authenticated = False
        self.raw_data = None
        self._last_update = None
        self._last_successful_data = None
        
        # Browser headers for realistic requests
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0'
        }
    
    async def _get_csrf_token(self):
        """Get CSRF token from login page."""
        try:
            async with async_timeout.timeout(30):
                async with self.session.get(LOGIN_URL, headers=self.headers) as response:
                    if response.status != 200:
                        _LOGGER.error(f"Failed to get login page: {response.status}")
                        return False
                    
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Method 1: Meta tag
                    csrf_meta = soup.find('meta', attrs={'name': 'csrf-token'})
                    if csrf_meta:
                        self.csrf_token = csrf_meta.get('content')
                        _LOGGER.debug("Found CSRF token in meta tag")
                        return True
                    
                    # Method 2: Form input
                    csrf_input = soup.find('input', attrs={'name': 'csrfmiddlewaretoken'})
                    if csrf_input:
                        self.csrf_token = csrf_input.get('value')
                        _LOGGER.debug("Found CSRF token in form")
                        return True
                    
                    # Method 3: Cookie
                    csrf_cookie = None
                    for cookie in response.cookies:
                        if cookie.key == 'csrftoken':
                            csrf_cookie = cookie.value
                            break
                    
                    if csrf_cookie:
                        self.csrf_token = csrf_cookie
                        _LOGGER.debug("Found CSRF token in cookie")
                        return True
                    
                    # Method 4: JavaScript variable
                    csrf_match = re.search(r'csrfToken[\'\"]\s*:\s*[\'\"](.*?)[\'\"]', html, re.IGNORECASE)
                    if not csrf_match:
                        csrf_match = re.search(r'csrf_token[\'\"]\s*:\s*[\'\"](.*?)[\'\"]', html, re.IGNORECASE)
                    
                    if csrf_match:
                        self.csrf_token = csrf_match.group(1)
                        _LOGGER.debug("Found CSRF token in JavaScript")
                        return True
                    
                    _LOGGER.warning("No CSRF token found, proceeding without it")
                    return True
                    
        except Exception as e:
            _LOGGER.error(f"Error getting CSRF token: {e}")
            return False
    
    async def _authenticate(self):
        """Authenticate with the portal."""
        try:
            # Get CSRF token
            if not await self._get_csrf_token():
                _LOGGER.error("Failed to get CSRF token")
                return False
            
            # Get login form details
            async with async_timeout.timeout(30):
                async with self.session.get(LOGIN_URL, headers=self.headers) as response:
                    if response.status != 200:
                        return False
                    
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Find login form
                    login_form = soup.find('form')
                    if not login_form:
                        _LOGGER.error("No login form found")
                        return False
                    
                    # Get form action
                    form_action = login_form.get('action')
                    if form_action:
                        if form_action.startswith('http'):
                            login_url = form_action
                        else:
                            login_url = urljoin(LOGIN_URL, form_action)
                    else:
                        login_url = LOGIN_URL
                    
                    # Prepare login data
                    login_data = {
                        'username': self.username,
                        'password': self.password
                    }
                    
                    # Add CSRF token
                    if self.csrf_token:
                        login_data['csrfmiddlewaretoken'] = self.csrf_token
                    
                    # Add hidden fields
                    for hidden_input in login_form.find_all('input', type='hidden'):
                        name = hidden_input.get('name')
                        value = hidden_input.get('value')
                        if name and value and name != 'csrfmiddlewaretoken':
                            login_data[name] = value
                    
                    # Update headers for login
                    login_headers = self.headers.copy()
                    login_headers.update({
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'Origin': BASE_URL,
                        'Referer': LOGIN_URL,
                    })
                    
                    if self.csrf_token:
                        login_headers['X-CSRFToken'] = self.csrf_token
                    
                    # Perform login
                    form_data = aiohttp.FormData()
                    for key, value in login_data.items():
                        form_data.add_field(key, value)
                    
                    async with self.session.post(
                        login_url, 
                        data=form_data, 
                        headers=login_headers,
                        allow_redirects=False
                    ) as login_response:
                        
                        _LOGGER.debug(f"Login response status: {login_response.status}")
                        
                        if login_response.status in [200, 301, 302]:
                            # Handle redirect
                            if login_response.status in [301, 302]:
                                redirect_url = login_response.headers.get('Location', '')
                                if redirect_url and redirect_url.startswith('/'):
                                    redirect_url = BASE_URL + redirect_url
                                
                                if redirect_url:
                                    async with self.session.get(redirect_url, headers=self.headers) as dashboard_response:
                                        if dashboard_response.status == 200:
                                            self.authenticated = True
                                            _LOGGER.info("Authentication successful")
                                            return True
                            
                            # Check response content
                            response_text = await login_response.text()
                            success_indicators = ['dashboard', 'welcome', 'logout', 'account', 'profile']
                            error_indicators = ['error', 'invalid', 'incorrect', 'failed']
                            
                            success_count = sum(1 for indicator in success_indicators if indicator.lower() in response_text.lower())
                            error_count = sum(1 for indicator in error_indicators if indicator.lower() in response_text.lower())
                            
                            if success_count > error_count:
                                self.authenticated = True
                                _LOGGER.info("Authentication successful")
                                return True
                        
                        _LOGGER.error(f"Authentication failed: {login_response.status}")
                        return False
                        
        except Exception as e:
            _LOGGER.error(f"Authentication error: {e}")
            return False
    
    async def _fetch_api_data(self):
        """Fetch raw data from the API."""
        try:
            # Update headers for API request
            api_headers = self.headers.copy()
            api_headers.update({
                'Accept': 'application/json, text/plain, */*',
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
                'Referer': f'{BASE_URL}/subscriber'
            })
            
            if self.csrf_token:
                api_headers['X-CSRFToken'] = self.csrf_token
            
            api_url = BASE_URL + API_ENDPOINT
            
            async with async_timeout.timeout(30):
                async with self.session.get(api_url, headers=api_headers) as response:
                    if response.status == 200:
                        try:
                            data = await response.json()
                            _LOGGER.info("Successfully fetched API data")
                            _LOGGER.debug(f"Raw API response: {json.dumps(data, indent=2)}")
                            return data
                        except Exception as e:
                            _LOGGER.error(f"Failed to parse JSON response: {e}")
                            text = await response.text()
                            _LOGGER.debug(f"Response text: {text[:200]}...")
                            return None
                    elif response.status == 403:
                        _LOGGER.warning("API returned 403 - re-authentication required")
                        self.authenticated = False
                        return None
                    else:
                        _LOGGER.error(f"API returned status {response.status}")
                        text = await response.text()
                        _LOGGER.debug(f"Error response: {text[:200]}...")
                        return None
                        
        except Exception as e:
            _LOGGER.error(f"Error fetching API data: {e}")
            return None
    
    async def async_update_data(self):
        """Update raw data from Asianet API."""
        try:
            # Authenticate if not already authenticated
            if not self.authenticated:
                if not await self._authenticate():
                    _LOGGER.error("Authentication failed")
                    return False
            
            # Fetch data from API
            raw_data = await self._fetch_api_data()
            
            # If API call failed due to auth issues, try to re-authenticate once
            if raw_data is None and not self.authenticated:
                _LOGGER.info("Re-authenticating and retrying...")
                if await self._authenticate():
                    raw_data = await self._fetch_api_data()
            
            if raw_data is None:
                _LOGGER.error("Failed to fetch data from API")
                return False
            
            # Store raw data
            self.raw_data = raw_data
            self._last_successful_data = raw_data
            self._last_update = datetime.now()
            
            _LOGGER.info("Successfully updated Asianet data")
            _LOGGER.debug(f"Updated data keys: {list(raw_data.keys()) if isinstance(raw_data, dict) else type(raw_data)}")
            return True
            
        except Exception as e:
            _LOGGER.error(f"Error updating data: {e}")
            return False

class AsianetJSONSensor(SensorEntity):
    """Sensor that returns complete JSON response from Asianet API."""
    
    def __init__(self, client: AsianetAuthenticatedClient):
        """Initialize the JSON sensor."""
        self._client = client
        self._attr_name = "Asianet Data"
        self._attr_unique_id = f"asianet_data_{client.username}"
        self._attr_icon = "mdi:web"
        self._attr_native_value = None
        self._attr_available = True
    
    async def async_update(self):
        """Update the sensor."""
        try:
            if await self._client.async_update_data():
                # Set the state to a simple status
                self._attr_native_value = "Connected"
                self._attr_available = True
                
            else:
                self._attr_native_value = "Disconnected"
                self._attr_available = False
                
        except Exception as e:
            _LOGGER.error(f"Error updating JSON sensor: {e}")
            self._attr_native_value = "Error"
            self._attr_available = False
    
    @property
    def extra_state_attributes(self):
        """Return the complete API response as attributes."""
        attrs = {
            "integration": "asianet_scraper",
            "username": self._client.username,
            "authenticated": self._client.authenticated,
        }
        
        if self._client._last_update:
            attrs["last_update"] = self._client._last_update.isoformat()
        
        # Add the raw API data as attributes
        if self._client.raw_data:
            if isinstance(self._client.raw_data, dict):
                # Add all API response fields as attributes
                for key, value in self._client.raw_data.items():
                    # Convert nested objects to JSON strings for display
                    if isinstance(value, (dict, list)):
                        attrs[f"api_{key}"] = json.dumps(value)
                    else:
                        attrs[f"api_{key}"] = value
            else:
                attrs["api_raw_response"] = str(self._client.raw_data)
        
        # Also keep the full JSON response as a single attribute for easy access
        if self._client.raw_data:
            attrs["json_data"] = json.dumps(self._client.raw_data)
        
        # If we have last successful data and current fetch failed, keep the last good data
        if not self._client.raw_data and self._client._last_successful_data:
            attrs["json_data"] = json.dumps(self._client._last_successful_data)
            attrs["data_status"] = "using_cached_data"
        else:
            attrs["data_status"] = "fresh_data"
        
        return attrs
    
    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {("asianet_scraper", self._client.username)},
            "name": f"Asianet Broadband ({self._client.username})",
            "manufacturer": "Asianet",
            "model": "Broadband Connection",
            "sw_version": "Portal API v1.0",
        }
