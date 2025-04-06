

from os import path
import os
from typing import NamedTuple, Optional
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from repsheet_backend.common import DATA_DIR, MEMBER_VOTES_TABLE, VOTES_HELD_TABLE, db_connect

class BillId(NamedTuple):
    parliament: int
    session: int
    bill_number: str

    def __str__(self):
        return f"{self.parliament}-{self.session}-{self.bill_number}"


@retry(stop=stop_after_attempt(10), wait=wait_exponential())
def download_all_bill_texts(parliament, session, bill_number):
    bill_dir = path.join(DATA_DIR, "bill_text", str(parliament), str(session), str(bill_number))
    found = False
    for reading in (1, 2, 3, 4):
        for lang in ("-E", "_E"):
            filename = f"{bill_number}_{reading}/{bill_number}{lang}.xml"
            filepath = path.join(bill_dir, filename)
            if path.exists(filepath):
                # empty file indicates that the file was not found
                if path.getsize(filepath) > 0:
                    found = True
                continue
            for bill_type in ("Private", "Government"):
                url = f"https://www.parl.ca/Content/Bills/{parliament}{session}/{bill_type}/{bill_number}/{filename}"
                resp = httpx.get(url)
                os.makedirs(path.dirname(filepath), exist_ok=True)
                with open(filepath, "wb") as f:
                    if resp.status_code == 200:
                        f.write(resp.content)
                        print(f"Downloaded {filename} from {url}")
                        found = True
                        # break otherwise the next iteration might overwrite the file with an empty file
                        break
                    else:
                        # use an empty file to indicate that the file was not found
                        f.write(b"")
    return found


def get_latest_bill_text_path(bill: BillId) -> Optional[str]:
    parliament, session, bill_number = bill
    latest_reading_path = ""
    for reading in (1, 2, 3, 4):
        texts_path = path.join(DATA_DIR, f"bill_text/{parliament}/{session}/{bill_number}/{bill_number}_{reading}")
        for file in os.listdir(texts_path):
            assert file.endswith(".xml")
            filepath = path.join(texts_path, file)
            if path.getsize(filepath) > 0:
                latest_reading_path = max(latest_reading_path, filepath)
    if latest_reading_path:
        return latest_reading_path
    return None


def get_every_bill_voted_on_by_a_member() -> list[BillId]:
    with db_connect() as db:
        bills = db.execute(
            "SELECT DISTINCT v.[Parliament], v.[Session], v.[Bill Number] "
            f"FROM {MEMBER_VOTES_TABLE} mv "
            f"LEFT JOIN {VOTES_HELD_TABLE} v ON v.[Vote ID] = mv.[Vote ID] "
            "WHERE [Bill Number] IS NOT NULL "
            "ORDER BY v.[Parliament] DESC "
        ).fetchall()
        return [BillId(*bill) for bill in bills]
