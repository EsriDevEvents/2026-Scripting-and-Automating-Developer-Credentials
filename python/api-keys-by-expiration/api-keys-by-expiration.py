from arcgis import GIS
from datetime import datetime, timezone, timedelta


# connect to our portal
portal = GIS(profile="DTS2026")
print(f"connected to {portal.properties.name} as {portal.properties.user.username}")

now = datetime.now(timezone.utc)
days_in_future = (now + timedelta(days=7)).replace(
    hour=23, minute=59, second=59, microsecond=999000
)

token_url = "https://www.arcgis.com/sharing/rest/portals/self/apiTokens"
tokens_request = portal.session.post(
    token_url,
    {
        "f": "json",
        "num": 100,
        "startExpirationDate": int(now.timestamp() * 1000),
        "endExpirationDate": int(days_in_future.timestamp() * 1000),
    },
)

tokens_response = tokens_request.json()
print(f"{len(tokens_response['items'])} keys found expiring in the next month")
for itm in tokens_response["items"]:
    print(f"Item: {itm['title']} - {itm['itemId']} ")
    print(f"\tslot: {itm.get('apiToken')}")
    print(f"\towner: {itm['owner']}")
    print(
        f"\texpiration date: {datetime.fromtimestamp(itm['expirationDate'] / 1000, tz=timezone.utc)}"
    )
