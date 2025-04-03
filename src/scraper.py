import re
from pathlib import Path
from urllib.parse import ParseResult

import ratelimit
import requests
from bs4 import BeautifulSoup, Tag, PageElement
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


@ratelimit.sleep_and_retry
@ratelimit.limits(calls=12, period=10)
def scrape_legislator_contact_info(url: ParseResult, path: str) -> tuple[str, str]:
    page_url = url._replace(path=path)

    response = requests.get(page_url.geturl(), allow_redirects=True)
    soup = BeautifulSoup(response.content, "html.parser")

    main_info = soup.find("div", id="main-info")
    if not main_info or not isinstance(main_info, Tag):
        return "", ""

    info_paragraph = main_info.find("p")
    if not info_paragraph or not isinstance(info_paragraph, Tag):
        return "", ""

    email_tag = info_paragraph.find("a", href=True)
    if not email_tag or not isinstance(email_tag, Tag):
        return "", ""
    email = email_tag.getText().strip()

    phone_possible = info_paragraph.find("span", class_="text_right")
    if not phone_possible:
        return email, ""
    for phone_tag in phone_possible:
        if not isinstance(phone_tag, PageElement):
            continue
        return email, phone_tag.getText().strip()

    return email, ""


def parse_legislators_page(url: ParseResult, value: str, query: str = "selectedLetter") -> list[tuple[str, str, str, str]]:
    page_url = url._replace(query=f"{query}={value}")

    response = requests.get(page_url.geturl(), allow_redirects=True)
    soup = BeautifulSoup(response.content, "html.parser")

    table_tag = soup.find("table", class_="short-table white")
    if not table_tag or not isinstance(table_tag, Tag):
        return []

    legislators: list = []
    for table_row_tag in tqdm(table_tag.find_all("tr")[2:], unit="legislators", leave=False):  # Skip first 2 rows (header)
        row_cell = table_row_tag.find("td", class_="short-tabletdlf")
        district, town, member, party = extract_legislator_from_string(row_cell.get_text())
        row_link = table_row_tag.find("a", class_="btn btn-default", href=True)
        email, phone = scrape_legislator_contact_info(url, row_link["href"])
        legislators.append((district, town, member, party, email, phone))

    return legislators


def get_pagination(url: ParseResult) -> list[str]:
    response = requests.get(url.geturl(), allow_redirects=True)
    soup = BeautifulSoup(response.content, "html.parser")
    pages = soup.find("ul", class_="pagination")
    if not pages or not isinstance(pages, Tag):
        return []

    return [page.get_text() for page in pages.find_all("a")]


def main() -> None:
    url = ParseResult(scheme="https", netloc="legislature.maine.gov:443", path="/house/house/MemberProfiles/ListAlphaTown", params="", query="", fragment="")

    letters = get_pagination(url)
    pages = [parse_legislators_page(url, letter) for letter in tqdm(letters, unit="pages")]

    with Path("district_data.csv").open(mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerows([("District", "Town", "Member", "Party", "Email", "Phone")])
        for page in pages:
            writer.writerows(page)

    print("CSV file 'district_data.csv' has been created.")


main()
