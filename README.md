Asiant Scraper
A Home Assistant custom component scraper utility to fetch Asianet Broadband usage details from the portail. 
This integration is only applicable if you can log-in to https://sms.ali.asianetindia.com/subscriber/details/

Installation
Follow the below directory structure. 
```
config/
└── custom_components/
    └── asianet_scraper/
        ├── __init__.py
        ├── manifest.json
        └── sensor.py
```

In configuration.yaml, add:
```
sensor:
  - platform: asianet_scraper
    username: !secret asianet_username
    password: !secret asianet_password
    scan_interval: 86400  # 24 hours
```
In secrets.yaml, add:
```
asianet_username: "yoursubscribercode"
asianet_password: "123456"
```

If you need to debug the sensor, add the following to configuration.yaml:
```
logger:
  logs:
    custom_components.asianet_scraper: debug
```

The configuration creates `sensor.asianet_data`. 
The sensor `sensor.asianet_data` shows connected, disconnected, or unavailable status. All API Endpoints will be displayed as attributes to the sensor. 


