from json import dump, load
from arcgis.gis import GIS
from datetime import datetime, timedelta
from pathlib import Path

class cfg:
    item_id = "4f26fde50fda40678d98c575031ee720"
    days_in_future=3
    config_file_path=Path(__file__).resolve().parent / "app-config.json"

# Get the assigned slot for the provided key
def slot_for_key(key: str):
    slot = int(key[-10:-9])
    if slot == 1 or slot == 2:
        return slot

    return None


# Connect to our portal
portal = GIS(profile="DTS2026")
print(f"connected to {portal.properties.name} as {portal.properties.user.username}")

# Read the current API key from the app-config.json file.
with open(cfg.config_file_path, "r") as file:
    data = load(file)
current_api_key = data["apiKey"]

# Determine which slot current key is in.
api_key_slot = slot_for_key(current_api_key)
print(
    f"current key is in slot {api_key_slot} {current_api_key[-12:]}"
)

# Get the date three days from now.
new_expiration = (datetime.now() + timedelta(days=cfg.days_in_future)).replace(
    hour=23, minute=59, second=59, microsecond=999000
)
print(f"new key expiration date {new_expiration}")

# Use the ArcGIS API for Python to get the current developer credential item
developer_credential_item = portal.admin.developer_credentials.get(cfg.item_id)

# Which slot do we need to put the new key in
new_slot = 2 if api_key_slot == 1 else 1

# create a new token
new_key = developer_credential_item.generate_token(
    slot=new_slot, expiration=new_expiration
)
new_key_token = new_key.get("access_token")

print(f"new key in slot {new_slot} created {new_key_token[-12:]}...")

# write new key to our config file
print("writing new key to file...")
data["apiKey"] = new_key_token
with open(cfg.config_file_path, "w") as f:
    dump(data, f, indent=2)
    print(f"\tnew key written to {cfg.config_file_path}")


# invalidate the old API key
developer_credential_item.revoke(api_key_slot)
print(f"old key in slot {api_key_slot} invalidated")
