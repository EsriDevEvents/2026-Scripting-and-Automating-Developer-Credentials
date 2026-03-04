from arcgis import GIS,pd



portal = GIS(profile="DTS2026")

query = f"owner:esri AND title:'BlockedApps Config' AND type: 'Application Configuration'"
filter = 'owner: mtorrey_devlabs -typekeywords:("MapAreaPackage") -type:("Map Area" OR "Indoors Map Configuration" OR "Code Attachment") (type:"Application" AND typekeywords:"Registered App" -typekeywords:("APIToken" OR "MapAreaPackage"))'
items = portal.content.advanced_search(query="", filter=filter,sort_field="modified", sort_order="desc")
print(f"{items["total"]} OAuth applications found")

apps = []
for itm in items['results']:
  apps.append({
    "title":itm.title,
    "itemId": itm.app_info["itemId"],
    "redirectUris": ", ".join(itm.app_info["redirect_uris"]),
    "link": f"https://www.arcgis.com/home/item.html?id={itm.app_info["itemId"]}"
  })

df = pd.DataFrame(apps)
print(df)

