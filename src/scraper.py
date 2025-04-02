import re
from pathlib import Path
from urllib.parse import ParseResult

import requests
from bs4 import BeautifulSoup
import csv

from tqdm import tqdm


def extract_legislator_from_string(text: str) -> tuple[str, str, str, str]:
    if "District" not in text:
        return "", "", "", ""

    formatted_text = re.sub(r"[\r\n]", " ", text)
    formatted_text = re.sub(r"\s+", " ", formatted_text)

    # Extract  town, district, and member name from the formatted string
    match = re.match(r"([A-Za-z\s()]+)\s*-\s*District\s+(\d+)\s*-\s*(.+)\s*\((.+)\)", formatted_text)
    if not match:
        return "", "", "", ""

    town = match.group(1).strip()
    district = match.group(2).strip()
    member = match.group(3).strip()
    party = match.group(4).strip()

    return district, town, member, party


def parse_legislators_page(url: ParseResult, value: str, query: str = "selectedLetter") -> list[tuple[str, str, str, str]]:
    page_url = url
    page_url = page_url._replace(query=f"{query}={value}")

    response = requests.get(page_url.geturl(), allow_redirects=True)
    soup = BeautifulSoup(response.content, "html.parser")

    table = soup.find("table", class_="short-table")
    if not table:
        return []

    rows = table.find_all("tr")[2:]  # Skip first 2 rows (header)

    return [extract_legislator_from_string(row.find("td", class_="short-tabletdlf").get_text()) for row in rows]


def main() -> None:
    url = ParseResult(scheme="https", netloc="legislature.maine.gov:443", path="/house/house/MemberProfiles/ListAlphaTown", params="", query="", fragment="")

    letters = ["A", "B"]

    pages = [parse_legislators_page(url, letter) for letter in tqdm(letters)]

    with Path("district_data.csv").open(mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerows([("District", "Town", "Member", "Party")])
        for page in pages:
            writer.writerows(page)

    print("CSV file 'district_data.csv' has been created.")


main()
