import asyncio
import os
import httpx

from repsheet_backend.common import MemberInfo
from repsheet_backend.db import RepsheetDB

from google.cloud import storage

IMAGES_BUCKET = "repsheet-images"

gcs = storage.Client()
image_bucket = gcs.bucket(IMAGES_BUCKET)

PARTY_SHORT = {
    "Bloc Québécois": "BQ",
    "Conservative": "CPC",
    "Green": "GPC",
    "NDP": "NDP",
    "Liberal": "Lib",
}

# Some of them just don't map nicely
MANUAL_ENTRIES = {
    "Michael Chong (Wellington—Halton Hills)": "ChongMichaelD_CPC.jpg",
    "François-Philippe Champagne (Saint-Maurice—Champlain)": "ChampagneFrancoisPhilippe_Lib.jpg",
    "Robert Morrissey (Egmont)": "MorrisseyRobertJ._Lib.jpg",
}

def photo_url(mp: MemberInfo) -> str:
    if mp.id in MANUAL_ENTRIES:
        return f"https://www.ourcommons.ca/Content/Parliamentarians/Images/OfficialMPPhotos/44/{MANUAL_ENTRIES[mp.id]}"
    party = PARTY_SHORT.get(mp.party, "")
    name = f"{mp.last_name}{mp.first_name}"
    name = name.replace(" ", "").replace("-", "").replace("'", "")
    return f"https://www.ourcommons.ca/Content/Parliamentarians/Images/OfficialMPPhotos/44/{name}_{party}.jpg"

def _download_photo(mp: MemberInfo) -> None:
    target_blob = f"photos/{mp.id}.jpg"
    exists = image_bucket.blob(target_blob).exists()
    if exists:
        return
    
    url = photo_url(mp)
    resp = httpx.get(url)
    try:
        resp.raise_for_status()
    except:
        print(f"Failed to download {mp.id} from {url}")
        return
    blob = image_bucket.blob(target_blob)
    blob.upload_from_string(
        resp.content,
        content_type="image/jpeg",
    )
    print(f"Uploaded {mp.id} to GCS")

async def download_photo(mp: MemberInfo) -> None:
    await asyncio.to_thread(_download_photo, mp)


async def main():
    with RepsheetDB.connect() as db:
        members = db.get_current_members()
    print(f"Found {len(members)} current members")
    
    await asyncio.gather(
        *[download_photo(mp) for mp in members]
    )
    print("Done downloading photos")

if __name__ == "__main__":
    asyncio.run(main())