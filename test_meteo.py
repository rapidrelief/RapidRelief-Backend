import requests
import json

url = "https://api.open-meteo.com/v1/forecast?latitude=24.86&longitude=67.01&daily=precipitation_sum,temperature_2m_max&timezone=auto"
res = requests.get(url)
print(json.dumps(res.json(), indent=2))
