**Asiant Data Scraper**

A Home Assistant custom component scraper utility to fetch Asianet Broadband usage details from the portail. 
This integration is only applicable if you can log-in to https://sms.ali.asianetindia.com/subscriber/details/

_**WARNING**_
1. This is a vibe coded integration. Not code-reviewd for quality, reliability etc. 
2. You are using this at your own risk.
3. I cannot guarantee any future updates to this sensor, nor I am skilled enough to resolve the issues that you may face while using this sensor. I created this for my personal use. You mileage may vary. 

**Installation**

Follow the below directory structure. 
```
config/
└── custom_components/
    └── asianet_scraper/
        ├── __init__.py
        ├── manifest.json
        └── sensor.py
```

**Configuration**

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

**Debug**

If you need to debug the sensor, add the following to configuration.yaml:
```
logger:
  logs:
    custom_components.asianet_scraper: debug
```

The configuration creates `sensor.asianet_data`. 
The sensor `sensor.asianet_data` shows connected, disconnected, or unavailable status. All API Endpoints will be displayed as attributes to the sensor. 


You can find basic template sensor configurations in `sensors.yaml`.
You can add contents in the `sensors.yaml` file either in configuration under `sensor` or in a seperate `sensor.yaml` file if you keep seperate files. 
