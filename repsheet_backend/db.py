from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime
import re
import sqlite3
from typing import Iterable, Iterator, Optional
import pandas as pd
from tqdm import tqdm

from repsheet_backend.common import (
    BILLS_TABLE,
    MEMBER_VOTES_TABLE,
    MEMBERS_TABLE,
    PARLIAMENTS_TABLE,
    PARLIMENTARY_SESSIONS,
    LATEST_PARLIAMENT,
    VOTES_HELD_TABLE,
    VOTE_SUMMARY_TABLE,
    VOTE_PARTY_SUMMARY_TABLE,
    PARLIAMENT_META,
    BillId,
    BillSummary,
    BillVotingRecord,
    MemberInfo,
    MemberSummary,
    PartyVotes,
)

FULL_MEMBER_NAME_REGEX = re.compile(r"^([^ ]+\. )?([^\(]+)(\([^\)]+\))?$")
HOUSE_CHAMBER_ID = 1
SENATE_CHAMBER_ID = 2
REPSHEET_DB = "repsheet.sqlite"

WITH_MOST_RECENT_VOTE_QUERY = f"""
WITH most_recent_vote AS (
SELECT
    b.[Bill ID] AS bill_id,
    MAX(v.[Vote ID]) AS vote_id
FROM {MEMBER_VOTES_TABLE} AS mv
JOIN {VOTES_HELD_TABLE} v
    ON mv.[Vote ID] = v.[Vote ID]
JOIN {BILLS_TABLE} AS b
    ON v.[Bill ID] = b.[Bill ID]
WHERE
    mv.[Member ID] = :member_id
GROUP BY
    b.[Bill ID]
)
"""
MEMBER_BILL_VOTING_QUERY = f"""
{WITH_MOST_RECENT_VOTE_QUERY}

SELECT
    b.[Bill ID] AS bill_id,
    b.[Bill Number] AS bill_number,
    b.[Summary] AS full_summary,
    mv.[Member Voted] AS voted,
    mv.[Vote ID] AS vote_id,
    mv.[Political Affiliation] AS member_party,
    b.[Private Bill Sponsor Member ID] = :member_id AS is_sponsor,
    b.[Became Law] AS became_law,
    b.[Is Budget] AS is_budget,
    p.[Government] = mv.[Political Affiliation] AS is_in_government,
    p.[Opposition] = mv.[Political Affiliation] AS is_in_opposition,
    p.[Supply-and-confidence] = mv.[Political Affiliation] AS is_in_supply_and_confidence,
    vs.[Yea Percentage] AS parliament_yea_percentage,
    pvs.[Yea Percentage] AS party_yea_percentage,
FROM most_recent_vote
JOIN {MEMBER_VOTES_TABLE} AS mv
    ON most_recent_vote.vote_id = mv.[Vote ID]
JOIN {BILLS_TABLE} AS b
    ON most_recent_vote.bill_id = b.[Bill ID]
JOIN {PARLIAMENTS_TABLE} AS p
    ON b.[Parliament] = p.[Parliament]
JOIN {VOTE_SUMMARY_TABLE} AS vs
    ON most_recent_vote.vote_id = vs.[Vote ID]
JOIN {VOTE_PARTY_SUMMARY_TABLE} AS pvs
    ON most_recent_vote.vote_id = pvs.[Vote ID] AND pvs.[Political Affiliation] = mv.[Political Affiliation]
WHERE
    mv.[Member ID] = :member_id
AND
    b.[Summary] IS NOT NULL
ORDER BY
    b.[Bill ID] DESC
"""

CREATE_VOTE_SUMMARY_TABLE_QUERY = f"""
CREATE TABLE {VOTE_SUMMARY_TABLE} AS
SELECT
    v.[Bill ID] AS [Bill ID],
    v.[Vote ID] AS [Vote ID],
    SUM(CASE WHEN vote = "Yea" THEN 1 ELSE 0 END) AS [Yea],
    SUM(CASE WHEN vote = "Nay" THEN 1 ELSE 0 END) AS [Nay],
    SUM(CASE WHEN vote = "Paired" THEN 1 ELSE 0 END) AS [Paired],
    SUM(CASE WHEN vote = "Yea" THEN 1 ELSE 0 END) / COUNT(*) AS [Yea Percentage],
    SUM(CASE WHEN vote = "Nay" THEN 1 ELSE 0 END) / COUNT(*) AS [Nay Percentage],
    SUM(CASE WHEN vote = "Paired" THEN 1 ELSE 0 END) / COUNT(*) AS [Paired Percentage],
FROM {VOTES_HELD_TABLE}
GROUP BY v.[Bill ID], v.[Vote ID]
"""

CREATE_PARTY_VOTE_SUMMARY_TABLE_QUERY = f"""
CREATE TABLE {VOTE_PARTY_SUMMARY_TABLE} AS
SELECT
    v.[Bill ID] AS [Bill ID],
    v.[Vote ID] AS [Vote ID],
    v.[Political Affiliation] AS [Political Affiliation],
    SUM(CASE WHEN vote = "Yea" THEN 1 ELSE 0 END) AS [Yea],
    SUM(CASE WHEN vote = "Nay" THEN 1 ELSE 0 END) AS [Nay],
    SUM(CASE WHEN vote = "Paired" THEN 1 ELSE 0 END) AS [Paired],
    SUM(CASE WHEN vote = "Yea" THEN 1 ELSE 0 END) / COUNT(*) AS [Yea Percentage],
    SUM(CASE WHEN vote = "Nay" THEN 1 ELSE 0 END) / COUNT(*) AS [Nay Percentage],
    SUM(CASE WHEN vote = "Paired" THEN 1 ELSE 0 END) / COUNT(*) AS [Paired Percentage],
FROM {VOTES_HELD_TABLE}
GROUP BY v.[Bill ID], v.[Vote ID], v.[Political Affiliation]
"""


class RepsheetDB:
    db: sqlite3.Connection
    _full_member_name_cache: dict[str, str | None]
    _voting_stats_cache: dict[str, list[tuple[str, PartyVotes]]]

    def __init__(self, db: sqlite3.Connection):
        self.db = db
        self._full_member_name_cache = {}
        self._voting_stats_cache = {}

    @contextmanager
    @staticmethod
    def connect() -> Iterator["RepsheetDB"]:
        """Context manager for database connection."""
        db = sqlite3.connect(REPSHEET_DB)
        db.row_factory = sqlite3.Row
        try:
            yield RepsheetDB(db)
        finally:
            db.commit()
            db.close()

    def find_member_id(self, full_member_name: str) -> Optional[str]:
        """Find a member ID from their full name (e.g. Mr. Justin Trudeau (Papineau)).
        Does not check honorifics or constituency names.
        Generally really flakey matching but it guarantees at most one result,
        so if there's ambiguity it will raise an error."""
        if full_member_name in self._full_member_name_cache:
            return self._full_member_name_cache[full_member_name]

        match = FULL_MEMBER_NAME_REGEX.match(full_member_name)
        if not match:
            raise ValueError(f"Failed to match full member name: {full_member_name}")
        honorific, member_name, constituency = match.groups()
        member_name = member_name.strip()
        first_name = member_name.split(" ")[0]
        last_name = member_name.split(" ")[-1]

        rows = self.db.execute(
            f"SELECT [Member ID] FROM {MEMBERS_TABLE} "
            "WHERE [First Name] LIKE ? AND [Last Name] LIKE ?",
            (f"{first_name}%", f"%{last_name}"),
        ).fetchall()

        if len(rows) > 1:
            raise ValueError(f"Found multiple member IDs for {full_member_name}: {rows}")
        if len(rows) == 0:
            result = None
        else:
            assert len(rows) == 1
            result = rows[0][0]

        self._full_member_name_cache[full_member_name] = result
        return result

    def create_parliaments_table(self):
        self.db.execute(f"DROP TABLE IF EXISTS {PARLIAMENTS_TABLE}")
        self.db.execute(
            f"CREATE TABLE {PARLIAMENTS_TABLE} ("
            "[Parliament] INTEGER NOT NULL PRIMARY KEY, "
            "[Government] TEXT NOT NULL, "
            "[Opposition] TEXT NOT NULL, "
            "[Supply-and-confidence] TEXT "
            ")"
        )

        for parliament, meta in PARLIAMENT_META.items():
            self.db.execute(
                f"INSERT INTO {PARLIAMENTS_TABLE} ([Parliament], [Government], [Opposition], [Supply-and-confidence]) VALUES (?, ?, ?, ?)",
                (
                    parliament,
                    meta["government"],
                    meta["opposition"],
                    meta.get("supply-and-confidence", None),
                ),
            )

    def create_members_table(self, members: pd.DataFrame):
        members["Start Date"] = members["Start Date"].apply(parse_parl_datetime)
        members["End Date"] = members["End Date"].apply(parse_parl_datetime)
        members["Member ID"] = members.apply(
            lambda row: f"{row['First Name']} {row["Last Name"]} ({row["Constituency"]})", axis=1
        )
        members["Photo URL"] = members.apply(
            lambda row: f"https://storage.googleapis.com/repsheet-images/photos/{row["Member ID"]}.jpg", axis=1
        )

        self.db.execute(f"DROP TABLE IF EXISTS {MEMBERS_TABLE}")
        self.db.execute(
            f"CREATE TABLE {MEMBERS_TABLE} ("
            "[Member ID] TEXT NOT NULL PRIMARY KEY, "
            "[Honorific Title] TEXT NULL, "
            "[First Name] TEXT NOT NULL, "
            "[Last Name] TEXT NOT NULL, "
            "[Constituency] TEXT NOT NULL, "
            "[Province / Territory] TEXT NOT NULL, "
            "[Political Affiliation] TEXT NOT NULL, "
            "[Start Date] TIMESTAMP NOT NULL, "
            "[End Date] TIMESTAMP, "
            "[Summary] TEXT NULL, "
            "[Short Summary] TEXT NULL, "
            "[Photo URL] TEXT NOT NULL "
            ")"
        )

        members.to_sql(MEMBERS_TABLE, self.db, if_exists="append", index=False)
        print(f"Inserted {len(members)} members into {MEMBERS_TABLE} table.")

        assert self.find_member_id("Mr. Justin Trudeau (Papineau)") == "Justin Trudeau (Papineau)"
        assert self.find_member_id("Mr. Harjit S. Sajjan (Vancouver South)") is not None
        assert self.find_member_id("Ms. Soraya Martinez Ferrada (Hochelaga)") is not None
        assert self.find_member_id("Senator Josée Verner (Louis-Saint-Laurent)") is None
        assert self.find_member_id("Gord Johns") is not None

    def create_bills_table(self, bills_by_session: dict[str, list[dict]]):
        self.db.execute(f"DROP TABLE IF EXISTS {BILLS_TABLE}")
        self.db.execute(
            f"CREATE TABLE {BILLS_TABLE} ("
            "[Bill ID] TEXT NOT NULL PRIMARY KEY, "
            "[Parliament] INTEGER NOT NULL, "
            "[Session] INTEGER NOT NULL, "
            "[Bill Number] TEXT NOT NULL, "
            "[Bill Type] TEXT NOT NULL, "
            "[Private Bill Sponsor Member ID] TEXT NULL,"
            "[Became Law] INTEGER NOT NULL, "
            "[Long Title] TEXT NOT NULL, "
            "[Short Title] TEXT NULL, "
            "[Is Budget] BOOLEAN NOT NULL, "
            "[Bill External URL] TEXT NOT NULL, "
            "[First Reading Date] TIMESTAMP NOT NULL, "
            "[Summary] TEXT NULL, "
            f"FOREIGN KEY ([Private Bill Sponsor Member ID]) REFERENCES {MEMBERS_TABLE}([Member ID]) "
            ")"
        )

        assert bills_by_session.keys() == set(PARLIMENTARY_SESSIONS)
        for psession, bills in bills_by_session.items():
            parliament, session = psession.split("-")
            parliament = int(parliament)
            session = int(session)
            bills = bills_by_session[psession]
            bill_rows = []
            for bill in bills:
                row = {}

                row["Parliament"] = parliament
                row["Session"] = session

                reading_dates = [
                    str(bill[k])
                    for k in bill.keys()
                    if k.endswith("ReadingDateTime") and bill[k] is not None
                ]
                if len(reading_dates) == 0:
                    continue
                else:
                    row["First Reading Date"] = datetime.fromisoformat(
                        sorted(reading_dates)[0]
                    )

                row["Long Title"] = bill["LongTitleEn"]
                short_title = bill["ShortTitleEn"]

                if not short_title:
                    row["Is Budget"] = False
                    short_title = None
                else:
                    row["Is Budget"] = short_title.startswith("Appropriation Act")
                row["Short Title"] = short_title

                bill_type = bill["BillTypeEn"]
                if (
                    bill_type == "Private Member’s Bill"
                    and bill["OriginatingChamberId"] == HOUSE_CHAMBER_ID
                ):
                    sponsor_member_id = self.find_member_id(bill["SponsorEn"])
                    if parliament == LATEST_PARLIAMENT and sponsor_member_id is None:
                        raise ValueError(f"Failed to find member ID for {bill['SponsorEn']}")
                else:
                    sponsor_member_id = None
                row["Private Bill Sponsor Member ID"] = sponsor_member_id
                row["Bill Type"] = bill_type

                bill_number = bill["BillNumberFormatted"]
                row["Bill Number"] = bill_number
                row["Bill ID"] = f"{parliament}-{session}-{bill_number}"
                row["Bill External URL"] = (
                    f"https://www.parl.ca/legisinfo/en/bill/{parliament}-{session}/{bill_number.lower()}"
                )
                row["Became Law"] = bill["ReceivedRoyalAssentDateTime"] is not None

                bill_rows.append(row)

            pd.DataFrame(bill_rows).to_sql(
                BILLS_TABLE,
                self.db,
                if_exists="append",
                index=False,
            )
            print(
                f"Inserted {len(bill_rows)} bills into {BILLS_TABLE} table from session {psession}."
            )

    def create_votes_table(self, votes_by_session: dict[str, pd.DataFrame]) -> None:
        self.db.execute(f"DROP TABLE IF EXISTS {VOTES_HELD_TABLE}")
        self.db.execute(
            f"CREATE TABLE {VOTES_HELD_TABLE} ("
            "[Vote ID] TEXT NOT NULL PRIMARY KEY, "
            "[Parliament] INTEGER NOT NULL, "
            "[Session] INTEGER NOT NULL, "
            "[Date] TIMESTAMP NOT NULL, "
            "[Vote Number] INTEGER NOT NULL, "
            "[Vote Subject] TEXT NOT NULL, "
            "[Vote Result] TEXT NOT NULL, "
            "[Yeas] INTEGER, "
            "[Nays] INTEGER, "
            "[Paired] INTEGER, "
            "[Bill Number] TEXT NULL, "
            "[Bill ID] TEXT NULL, "
            "[Agreed To] INTEGER NOT NULL, "
            f"FOREIGN KEY ([Bill ID]) REFERENCES {BILLS_TABLE}([Bill ID]) "
            ")"
        )
        self.db.execute(
            f"CREATE UNIQUE INDEX idx_session_vote_id ON {VOTES_HELD_TABLE} ([Parliament], [Session], [Vote Number])"
        )

        assert votes_by_session.keys() == set(PARLIMENTARY_SESSIONS)
        for p_session, v in votes_by_session.items():
            parliament, session = p_session.split("-")
            v["Vote Subject"] = v["Vote Subject"].astype("string")
            v["Vote Result"] = v["Vote Result"].astype("string")
            v["Agreed To"] = v["Vote Result"].apply(lambda x: True if x == "Agreed To" else False)
            v["Bill Number"] = v["Bill Number"].astype("string")
            v["Bill ID"] = (
                v["Bill Number"]
                .apply(lambda x: f"{parliament}-{session}-{x}" if pd.notna(x) else None)
                .astype("string")
            )
            v["Date"] = v["Date"].apply(parse_parl_datetime)
            v["Vote ID"] = (
                v["Parliament"].astype("string")
                + "-"
                + v["Session"].astype("string")
                + "-"
                + v["Vote Number"].astype("string")
            )

            for c in v.columns:
                assert v[c].dtype != "object", f"Column {c} is still an object type"

            v.to_sql(VOTES_HELD_TABLE, self.db, if_exists="append", index=False)
            print(
                f"Inserted {len(v)} votes into {VOTES_HELD_TABLE} table from session {p_session}."
            )

    def get_all_votes_held(self) -> list[str]:
        """Return Vote ID for all votes held"""
        rows = self.db.execute(f"SELECT [Vote ID] FROM {VOTES_HELD_TABLE}").fetchall()
        return [row[0] for row in rows]

    def create_member_votes_table(self, member_votes_by_vote_id: dict[str, pd.DataFrame]) -> None:
        self.db.execute(f"DROP TABLE IF EXISTS {MEMBER_VOTES_TABLE}")
        self.db.execute(
            f"CREATE TABLE {MEMBER_VOTES_TABLE} ("
            "[Vote ID] TEXT NOT NULL, "
            # null if this is not a current MP
            "[Member ID] TEXT NULL, "
            "[Member of Parliament] TEXT NOT NULL, "
            "[Political Affiliation] TEXT NOT NULL, "
            "[Member Voted] TEXT NULL, "
            "Paired TEXT NULL, "
            f"FOREIGN KEY ([Vote ID]) REFERENCES {VOTES_HELD_TABLE}([Vote ID]), "
            f"FOREIGN KEY ([Member ID]) REFERENCES {MEMBERS_TABLE}([Member ID]), "
            "PRIMARY KEY ([Vote ID], [Member ID]) "
            ")"
        )

        self.db.execute(
            f"CREATE UNIQUE INDEX IF NOT EXISTS idx_member_vote ON {MEMBER_VOTES_TABLE} ([Vote ID], [Member ID])"
        )
        self.db.execute(
            f"CREATE INDEX IF NOT EXISTS idx_member_vote_id ON {MEMBER_VOTES_TABLE} ([Member ID])"
        )
        self.db.execute(
            f"CREATE INDEX IF NOT EXISTS idx_member_vote_vote_id ON {MEMBER_VOTES_TABLE} ([Vote ID])"
        )

        print(
            f"Inserting {sum(len(v) for v in member_votes_by_vote_id.values())} member votes into {MEMBER_VOTES_TABLE} table."
        )
        for vote_id, v in tqdm(member_votes_by_vote_id.items()):
            v["Vote ID"] = vote_id
            v["Member ID"] = v["Member of Parliament"].apply(self.find_member_id)
            parliament = vote_id.split("-")[0]
            if parliament == LATEST_PARLIAMENT and len(v[v["Member ID"].isna()]) > 0:
                raise ValueError(
                    f"Found members of latest Parliament we could not match to an ID: {v[v["Member ID"].isna()]}"
                )
            v.to_sql(
                MEMBER_VOTES_TABLE,
                self.db,
                if_exists="append",
                index=False,
            )

    def create_vote_summary_tables(self):
        self.db.execute(f"DROP TABLE IF EXISTS {VOTE_SUMMARY_TABLE}")
        self.db.execute(f"DROP TABLE IF EXISTS {VOTE_PARTY_SUMMARY_TABLE}")
        self.db.execute(CREATE_VOTE_SUMMARY_TABLE_QUERY)
        self.db.execute(CREATE_PARTY_VOTE_SUMMARY_TABLE_QUERY)

    def get_every_bill_voted_on_by_a_current_member(self) -> list[BillId]:
        bills = self.db.execute(
            "SELECT DISTINCT v.[Parliament], v.[Session], v.[Bill Number] "
            f"FROM {MEMBER_VOTES_TABLE} mv "
            f"LEFT JOIN {VOTES_HELD_TABLE} v ON v.[Vote ID] = mv.[Vote ID] "
            "WHERE [Bill Number] IS NOT NULL "
            "AND [Member ID] IS NOT NULL "
            "ORDER BY v.[Parliament] DESC "
        ).fetchall()
        return [BillId(*bill) for bill in bills]

    def insert_bill_summaries(self, summaries: dict[BillId, str]) -> None:
        bill_summaries = [
            {"summary": summary, "bill_id": str(bill)} for bill, summary in summaries.items()
        ]
        self.db.executemany(
            f"UPDATE {BILLS_TABLE} SET Summary = :summary WHERE [Bill ID] = :bill_id",
            bill_summaries,
        )
        self.db.commit()
        print(f"Inserted {len(bill_summaries)} bill summaries")

    def get_voting_stats(self, vote_id) -> list[tuple[str, PartyVotes]]:
        if vote_id not in self._voting_stats_cache:
            rows = self.db.execute(
                f"""
                SELECT 
                    [Vote ID] AS vote_id,
                    [Political Affiliation] as party,
                    [Member Voted] AS vote,
                    COUNT(*) AS count
                FROM {MEMBER_VOTES_TABLE} 
                WHERE [Vote ID] = :vote_id
                GROUP BY vote_id, party, vote
                ORDER BY vote_id, party, vote""",
                {"vote_id": vote_id},
            ).fetchall()
            votes = {(row["party"], row["vote"]): row["count"] for row in rows}
            # sorted to preserve determinism of output order
            parties = sorted(list(set(row["party"] for row in rows)))
            assert len(parties) > 0, f"No votes found for vote ID {vote_id}"
            assert set(row["vote"] for row in rows) <= {
                "Yea",
                "Nay",
                None,
            }, f"Unexpected vote values: {set(row['vote'] for row in rows)}"
            stats = [
                (
                    party,
                    PartyVotes.build(
                        yea=votes.get((party, "Yea"), 0),
                        nay=votes.get((party, "Nay"), 0),
                        abstain=votes.get((party, None), 0),
                    ),
                )
                for party in parties
            ]
            self._voting_stats_cache[vote_id] = stats
        return self._voting_stats_cache[vote_id]

    def get_member_voting_record(self, member_id: str) -> list[BillVotingRecord]:
        rows = self.db.execute(MEMBER_BILL_VOTING_QUERY, {"member_id": member_id}).fetchall()
        voting_record: list[BillVotingRecord] = []
        member_party = set(row["member_party"] for row in rows)
        assert (
            len(member_party) == 1
        ), f"Found multiple parties for member {member_id}: {member_party}"
        member_party = member_party.pop()
        for row in rows:
            full_summary = BillSummary.model_validate_json(row["full_summary"])
            voted = row["voted"].lower() if row["voted"] else "abstain"
            voting_by_party = self.get_voting_stats(row["vote_id"])
            other_party_votes = []
            member_party_votes = None
            for party, party_votes in voting_by_party:
                if party == member_party:
                    member_party_votes = party_votes
                else:
                    other_party_votes.append(party_votes)
            assert (
                member_party_votes is not None
            ), f"Failed to find party votes for {member_party} in {row['vote_id']}"
            voting_record.append(
                BillVotingRecord(
                    summary=full_summary.summary,
                    billID=row["bill_id"],
                    billNumber=row["bill_number"],
                    billBecameLaw=row["became_law"],
                    memberVote=voted,
                    membersPartyVote=member_party_votes,
                    # not yet using the other party votes info in the prompts
                    # otherPartyVotes=other_party_votes,
                    issues=full_summary.issues,
                    privateBillOfMember=bool(row["is_sponsor"]),
                    billIsBudget=row["is_budget"],
                    parliamentYeaPercentage=row["parliament_yea_percentage"],
                    memberInGovernment=row["is_in_government"],
                    memberInOpposition=row["is_in_opposition"],
                    memberInSupplyAndConfidence=row["is_in_supply_and_confidence"],
                )
            )
        bill_ids = [vote.billID for vote in voting_record]
        assert len(set(bill_ids)) == len(
            bill_ids
        ), "Duplicate bill IDs found in voting record"
        return voting_record

    def insert_member_summaries(
        self, member_summaries: Iterable[tuple[str, MemberSummary]]
    ) -> None:
        summaries_for_db = [
            {"member_id": member_id, "summary": summary.model_dump_json()}
            for member_id, summary in member_summaries
            if summary is not None
        ]
        self.db.executemany(
            f"UPDATE {MEMBERS_TABLE} SET Summary = :summary WHERE [Member ID] = :member_id",
            summaries_for_db,
        )
        self.db.commit()
        print(f"Inserted {len(summaries_for_db)} member summaries")

    def insert_short_member_summaries(
        self, short_summaries: Iterable[tuple[str, str]]
    ) -> None:
        summaries_for_db = [
            {"member_id": member_id, "summary": summary}
            for member_id, summary in short_summaries
            if summary is not None
        ]
        self.db.executemany(
            f"UPDATE {MEMBERS_TABLE} SET [Short Summary] = :summary WHERE [Member ID] = :member_id",
            summaries_for_db,
        )
        self.db.commit()
        print(f"Inserted {len(summaries_for_db)} short member summaries")

    def get_current_members(self) -> list[MemberInfo]:
        rows = self.db.execute(
            f"""SELECT
                [Member ID] AS id, 
                [First Name] AS first_name, 
                [Last Name] As last_name,
                [Political Affiliation] AS party 
                FROM {MEMBERS_TABLE}"""
        ).fetchall()
        return [MemberInfo.model_validate(dict(row)) for row in rows]

    def optimize(self):
        # totally pointless given we have no performance issues but I couldn't help myself
        self.db.execute("VACUUM")
        self.db.execute("ANALYZE")
        print("Pointlessly optimized database.")


def parse_parl_datetime(date_str: str) -> Optional[pd.Timestamp]:
    """Parses strings in parliamentary datetime format, e.g. 2024-12-17 3:50:01 p.m."""
    if not date_str or pd.isna(date_str):
        return None
    date_str = date_str.replace("p.m.", "PM").replace("a.m.", "AM")
    return pd.to_datetime(date_str, format="%Y-%m-%d %I:%M:%S %p").tz_localize("Canada/Eastern")
