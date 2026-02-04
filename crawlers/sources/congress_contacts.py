import requests

from crawlers.base import BaseCrawler
from crawlers.conditions import (
    FieldCompleteness,
    FieldCoverage,
    MaxCount,
    MinCount,
    RequiredFields,
    UniqueField,
)

LEGISLATORS_URL = "https://unitedstates.github.io/congress-legislators/legislators-current.json"
SOCIAL_MEDIA_URL = "https://unitedstates.github.io/congress-legislators/legislators-social-media.json"


class CongressContactsCrawler(BaseCrawler):
    @property
    def name(self) -> str:
        return "congress_contacts"

    def crawl(self):
        legislators = requests.get(LEGISLATORS_URL, timeout=30).json()
        social_raw = requests.get(SOCIAL_MEDIA_URL, timeout=30).json()

        # Index social media by bioguide ID
        social = {}
        for entry in social_raw:
            bio_id = entry.get("id", {}).get("bioguide")
            if bio_id:
                social[bio_id] = entry.get("social", {})

        for leg in legislators:
            bio_id = leg["id"]["bioguide"]
            name = leg["name"]
            term = leg["terms"][-1] if leg.get("terms") else {}
            soc = social.get(bio_id, {})

            yield {
                "id": bio_id,
                "first_name": name.get("first", ""),
                "last_name": name.get("last", ""),
                "full_name": f"{name.get('first', '')} {name.get('last', '')}".strip(),
                "chamber": "senate" if term.get("type") == "sen" else "house",
                "state": term.get("state", ""),
                "district": term.get("district"),
                "party": term.get("party", ""),
                "phone": term.get("phone", ""),
                "office_address": term.get("address", ""),
                "website": term.get("url", ""),
                "contact_form_url": term.get("contact_form", ""),
                "twitter": soc.get("twitter", ""),
                "facebook": soc.get("facebook", ""),
                "youtube": soc.get("youtube", ""),
                "instagram": soc.get("instagram", ""),
            }

    def done_conditions(self):
        return [
            MinCount(530),
            MaxCount(600),
            RequiredFields(["id", "first_name", "last_name", "chamber", "state", "party"]),
            UniqueField("id"),
            FieldCoverage("phone", 0.85),
            FieldCoverage("website", 0.90),
            FieldCompleteness("full_name"),
        ]
