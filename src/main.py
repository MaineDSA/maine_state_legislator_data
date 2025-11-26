import csv
import logging
import re
import time
from pathlib import Path
from urllib.parse import urlencode, urlunparse

import urllib3
from bs4 import BeautifulSoup, PageElement, ResultSet, Tag
from tqdm import tqdm
from urllib3.util.retry import Retry

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Rate limiting configuration
REQUEST_DELAY = 3  # seconds between requests


LEGISLATURE_NETLOC = "legislature.maine.gov"
LEGISLATOR_LIST_PATH = "/house/house/MemberProfiles/ListAlphaTown"


def extract_legislator_from_string(text: str) -> tuple[str, str, str, str]:
    if "District" not in text:
        return "", "", "", ""

    formatted_text = re.sub(r"[\r\n]", " ", text)
    formatted_text = re.sub(r"\s+", " ", formatted_text)
    logger.debug("Extracting data from legislator string: %s", formatted_text)

    # Extract town, district, and member name from the formatted string
    match = re.match(r"([\W\w\s()-]+)\s*-\s*District\s+(\d+)\s*-\s*(.+?)\s*\((.+)\)", formatted_text)
    if not match:
        logger.error("Regex match not found, can't extract legislator district data")
        return "", "", "", ""

    town = match.group(1).strip()
    district = match.group(2).strip()
    member = match.group(3).strip()
    party = match.group(4).strip()

    return district, town, member, party


def scrape_committees(spans_medium: ResultSet) -> str:
    committees = ""
    for committees_tag in spans_medium:
        if committees_tag and isinstance(committees_tag, Tag) and committees_tag.getText() == "Committee(s):":
            committee_tag_1 = committees_tag.find_next("span").find_next("span")
            committees = committee_tag_1.getText().strip()
            committee_tag_2 = committee_tag_1.find_next_sibling("span")
            if committee_tag_2:
                committees = f"{committees}; {committee_tag_2.getText().strip()}"
                committee_tag_3 = committee_tag_2.find_next_sibling("span")
                if committee_tag_3:
                    committees = f"{committees}; {committee_tag_3.getText().strip()}"
    return committees


def scrape_detailed_legislator_info(http: urllib3.PoolManager, path: str, member: str) -> tuple[str, str, str]:
    time.sleep(REQUEST_DELAY)  # Rate limiting
    url = urlunparse(("https", LEGISLATURE_NETLOC, path, "", "", ""))

    logger.debug("Getting legislator data from URL: %s", url)
    response = http.request("GET", url)
    soup = BeautifulSoup(response.data, "html.parser")

    main_info = soup.find("div", id="main-info")
    if not main_info or not isinstance(main_info, Tag):
        return "", "", ""

    info_paragraph = main_info.find("p")
    if not info_paragraph or not isinstance(info_paragraph, Tag):
        return "", "", ""

    spans_medium = main_info.find_all("span", class_="font_weight_m")
    committees = scrape_committees(spans_medium)

    email = ""
    email_tag = info_paragraph.find("a", href=True)
    if not email_tag or not isinstance(email_tag, Tag):
        warn = f"Email not found for {member}"
        logger.warning(warn)
    else:
        email = email_tag.getText().strip()

    phone = ""
    phone_possible = info_paragraph.find("span", class_="text_right")
    if not phone_possible:
        return email, phone, committees
    for phone_tag in phone_possible:
        if not isinstance(phone_tag, PageElement):
            continue
        phone = phone_tag.getText().strip()
        return email, phone, committees

    warn = f"Phone not found for {member}"
    logger.warning(warn)
    return email, phone, committees


def parse_legislators_page(http: urllib3.PoolManager, value: str, query: str = "selectedLetter") -> list[tuple[str, str, str, str, str, str, str]]:
    query_string = urlencode({query: value})
    url = urlunparse(("https", LEGISLATURE_NETLOC, LEGISLATOR_LIST_PATH, "", query_string, ""))

    response = http.request("GET", url)
    soup = BeautifulSoup(response.data, "html.parser")

    table_tag = soup.find("table", class_="short-table white")
    if not table_tag or not isinstance(table_tag, Tag):
        return []

    legislators: list = []
    for table_row_tag in tqdm(table_tag.find_all("tr")[2:], unit="legislator", leave=False):  # Skip first 2 rows (header)
        row_cell = table_row_tag.find("td", class_="short-tabletdlf")
        district, town, member, party = extract_legislator_from_string(row_cell.get_text())
        row_link = table_row_tag.find("a", class_="btn btn-default", href=True)
        email, phone, committees = scrape_detailed_legislator_info(http, row_link["href"], member)
        legislators.append((district, town, member, party, email, phone, committees))

    return legislators


def get_pagination(http: urllib3.PoolManager) -> list[str]:
    url = urlunparse(("https", LEGISLATURE_NETLOC, LEGISLATOR_LIST_PATH, "", "", ""))

    response = http.request("GET", url)
    soup = BeautifulSoup(response.data, "html.parser")
    pages = soup.find("ul", class_="pagination")
    if not pages or not isinstance(pages, Tag):
        return []

    return [page.get_text() for page in pages.find_all("a")]


def main() -> None:
    # Configure retry strategy
    retry_strategy = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504], respect_retry_after_header=True)

    # Create a PoolManager with retry strategy
    http = urllib3.PoolManager(retries=retry_strategy)

    letters = get_pagination(http)
    pages = [parse_legislators_page(http, letter) for letter in tqdm(letters, unit="page")]

    with Path("district_data.csv").open(mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerows([("District", "Town", "Member", "Party", "Email", "Phone", "Committees")])
        for page in pages:
            writer.writerows(page)

    logger.info("CSV file 'district_data.csv' has been created.")


if __name__ == "__main__":
    main()
