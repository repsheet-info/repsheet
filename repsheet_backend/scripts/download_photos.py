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
    "Green Party": "GP",
    "NDP": "NDP",
    "Liberal": "Lib",
    "Independent": "Ind", 
}

# Some of them just don't map nicely
MANUAL_ENTRIES = {
    "Michael Chong (Wellington—Halton Hills)": "ChongMichaelD_CPC.jpg",
    "François-Philippe Champagne (Saint-Maurice—Champlain)": "ChampagneFrancoisPhilippe_Lib.jpg",
    "Robert Morrissey (Egmont)": "MorrisseyRobertJ._Lib.jpg",
    "Han Dong (Don Valley North)": "DongHan_Lib.jpg",
    "Rhéal Éloi Fortin (Rivière-du-Nord)": "FortinRh%C3%A9al_BQ.jpg",
    "Ahmed Hussen (York South—Weston)": "HussenAhmedD_Lib.jpg",
    "Heath MacDonald (Malpeque)": "MacDonaldHeath_CPC.jpg",
    "Alistair MacGregor (Cowichan—Malahat—Langford)": "MacGregorAllistair_NDP.jpg",
    "David McGuinty (Ottawa South)": "McGuintyDavidJ._Lib.jpg",
    "Michael McLeod (Northwest Territories)": "McLeodMichaelV_Lib.jpg",
    "Alain Rayes (Richmond—Arthabaska)": "RayesAlain_CPC.jpg",
    "Michelle Rempel Garner (Calgary Nose Hill)": "RempelMichelle_CPC.jpg",
    "Ryan Turnbull (Whitby)": "TurnbullRyan_CPC.jpg",
    "Dave MacKenzie (Oxford)": "MacKenzieDavid_CPC.jpg",
    "Pablo Rodriguez (Honoré-Mercier)": "RodriguezPablo_Lib.jpg",
    "Harjit S. Sajjan (Vancouver South)": "SajjanHarjit_Lib.jpg"
}

def photo_url(mp: MemberInfo) -> str:
    if mp.id in MANUAL_ENTRIES:
        return f"https://www.ourcommons.ca/Content/Parliamentarians/Images/OfficialMPPhotos/44/{MANUAL_ENTRIES[mp.id]}"
    party = PARTY_SHORT.get(mp.party, "")
    name = f"{mp.last_name}{mp.first_name}"
    name = name.replace(" ", "").replace("-", "").replace("'", "").replace(".", "")
    return f"https://www.ourcommons.ca/Content/Parliamentarians/Images/OfficialMPPhotos/44/{name}_{party}.jpg"

def _download_photo(mp: MemberInfo) -> bool:
    target_blob = f"photos/{mp.id}.jpg"
    exists = image_bucket.blob(target_blob).exists()
    if exists:
        return True
    
    url = photo_url(mp)
    resp = httpx.get(url)
    try:
        resp.raise_for_status()
    except:
        print(f"Failed to download {mp.id} from {url}")
        return False
    blob = image_bucket.blob(target_blob)
    blob.upload_from_string(
        resp.content,
        content_type="image/jpeg",
    )
    print(f"Uploaded {mp.id} to GCS")
    return True

async def download_photo(mp: MemberInfo) -> bool:
    return await asyncio.to_thread(_download_photo, mp)


async def main():
    with RepsheetDB.connect() as db:
        members = db.get_current_members()
    print(f"Found {len(members)} current members")
    
    successes = await asyncio.gather(
        *[download_photo(mp) for mp in members]
    )
    print("Done downloading photos")

    if any(not success for success in successes):
        print("Some photos failed to download")
        exit(1)

if __name__ == "__main__":
    asyncio.run(main())