from arcgis import GIS, pd

portal = GIS(profile="DTS2026")

query = (
    "owner:esri AND title:'BlockedApps Config' AND type: 'Application Configuration'"
)
items = portal.content.advanced_search(
    query="", filter=filter, sort_field="modified", sort_order="desc"
)
print(f"{items['total']} OAuth applications found")

apps = []
for itm in items["results"]:
    apps.append(
        {
            "title": itm.title,
            "itemId": itm.app_info["itemId"],
            "redirectUris": ", ".join(itm.app_info["redirect_uris"]),
            "link": f"https://www.arcgis.com/home/item.html?id={itm.app_info['itemId']}",
        }
    )

df = pd.DataFrame(apps)
print(df)
