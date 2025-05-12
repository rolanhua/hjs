import requests

AK = "O3jlxnpVqp1KKw8Z4srNtkhTrg3RJXsc"
url = f"https://api.map.baidu.com/geocoding/v3/?address=百度大厦&output=json&ak={AK}"
response = requests.get(url)
print(response.json())
