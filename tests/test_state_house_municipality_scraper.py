from unittest.mock import MagicMock, Mock, patch

import pytest
import urllib3
from bs4 import BeautifulSoup

from src.main import (
    collect_municipality_data,
    extract_legislator_from_string,
    get_most_common_url,
    get_pagination,
    scrape_committees,
    scrape_detailed_legislator_info,
)


class TestExtractLegislatorFromString:
    """Tests for extract_legislator_from_string function."""

    def test_valid_string(self) -> None:
        """Test extraction from valid municipality string."""
        text = "Manchester - District 23 - John Smith (Democrat)"
        district, town, member, party = extract_legislator_from_string(text)

        assert district == "23"
        assert town == "Manchester"
        assert member == "John Smith"
        assert party == "Democrat"

    def test_string_with_multiline(self) -> None:
        """Test extraction handles newlines and extra whitespace."""
        text = "Manchester\n\n - District 23  -   John Smith  (Democrat)"
        district, town, member, party = extract_legislator_from_string(text)

        assert district == "23"
        assert town == "Manchester"
        assert member == "John Smith"
        assert party == "Democrat"

    def test_town_with_special_characters(self) -> None:
        """Test extraction handles towns with hyphens and parentheses."""
        text = "Weare (West) - District 5 - Jane Doe (Republican)"
        district, town, member, party = extract_legislator_from_string(text)

        assert district == "5"
        assert town == "Weare (West)"
        assert member == "Jane Doe"
        assert party == "Republican"

    def test_no_district_keyword(self) -> None:
        """Test returns empty strings when 'District' keyword missing."""
        text = "Manchester - 23 - John Smith (Democrat)"
        district, town, member, party = extract_legislator_from_string(text)

        assert district == ""
        assert town == ""
        assert member == ""
        assert party == ""

    def test_malformed_string(self) -> None:
        """Test returns empty strings for malformed input."""
        text = "Invalid format without proper structure"
        district, town, member, party = extract_legislator_from_string(text)

        assert district == ""
        assert town == ""
        assert member == ""
        assert party == ""


class TestScrapeCommittees:
    """Tests for scrape_committees function."""

    def test_single_committee(self) -> None:
        """Test extraction of single committee."""
        html = """
        <span class="font_weight_m">Committee(s):</span>
        <span><span>Finance</span></span>
        """
        soup = BeautifulSoup(html, "html.parser")
        spans = soup.find_all("span", class_="font_weight_m")

        result = scrape_committees(spans)
        assert result == "Finance"

    def test_two_committees(self) -> None:
        """Test extraction of two committees."""
        html = """
        <span class="font_weight_m">Committee(s):</span>
        <span><span>Finance</span><span>Education</span></span>
        """
        soup = BeautifulSoup(html, "html.parser")
        spans = soup.find_all("span", class_="font_weight_m")

        result = scrape_committees(spans)
        assert result == "Finance; Education"

    def test_three_committees(self) -> None:
        """Test extraction of three committees."""
        html = """
        <span class="font_weight_m">Committee(s):</span>
        <span><span>Finance</span><span>Education</span><span>Health</span></span>
        """
        soup = BeautifulSoup(html, "html.parser")
        spans = soup.find_all("span", class_="font_weight_m")

        result = scrape_committees(spans)
        assert result == "Finance; Education; Health"

    def test_no_committees(self) -> None:
        """Test returns empty string when no committees found."""
        html = """
        <span class="font_weight_m">Other Label:</span>
        """
        soup = BeautifulSoup(html, "html.parser")
        spans = soup.find_all("span", class_="font_weight_m")

        result = scrape_committees(spans)
        assert result == ""

    def test_empty_result_set(self) -> None:
        """Test returns empty string for empty ResultSet."""
        soup = BeautifulSoup("", "html.parser")
        spans = soup.find_all("span", class_="font_weight_m")

        result = scrape_committees(spans)
        assert result == ""


class TestScrapeDetailedLegislatorInfo:
    """Tests for scrape_detailed_legislator_info function."""

    @patch("src.main.time.sleep")
    def test_complete_info(self, mock_sleep: Mock) -> None:
        """Test extraction of complete legislator information."""
        html = """
        <div id="main-info">
            <p>
                <a href="mailto:john.smith@leg.maine.gov">john.smith@leg.maine.gov</a>
                <span class="text_right">(603) 555-1234</span>
            </p>
            <span class="font_weight_m">Committee(s):</span>
            <span><span>Finance</span></span>
        </div>
        """

        mock_http = MagicMock(spec=urllib3.PoolManager)
        mock_response = Mock()
        mock_response.data = html.encode()
        mock_http.request.return_value = mock_response

        email, phone, committees = scrape_detailed_legislator_info(mock_http, "leg.maine.gov", "/member/123", "John Smith")

        assert email == "john.smith@leg.maine.gov"
        assert phone == "(603) 555-1234"
        assert committees == "Finance"
        mock_sleep.assert_called_once_with(2)

    @patch("src.main.time.sleep")
    def test_missing_email(self, mock_sleep: Mock, caplog: pytest.LogCaptureFixture) -> None:  # noqa: ARG002
        """Test handles missing email with warning."""
        html = """
        <div id="main-info">
            <p>
                <span class="text_right">(603) 555-1234</span>
            </p>
            <span class="font_weight_m">Committee(s):</span>
            <span><span>Finance</span></span>
        </div>
        """

        mock_http = MagicMock(spec=urllib3.PoolManager)
        mock_response = Mock()
        mock_response.data = html.encode()
        mock_http.request.return_value = mock_response

        email, phone, _committees = scrape_detailed_legislator_info(mock_http, "leg.maine.gov", "/member/123", "John Smith")

        assert email == ""
        assert phone == "(603) 555-1234"
        assert "Email not found for John Smith" in caplog.text

    @patch("src.main.time.sleep")
    def test_missing_phone(self, mock_sleep: Mock, caplog: pytest.LogCaptureFixture) -> None:  # noqa: ARG002
        """Test handles missing phone with warning."""
        html = """
        <div id="main-info">
            <p>
                <a href="mailto:john.smith@leg.maine.gov">john.smith@leg.maine.gov</a>
            </p>
            <span class="font_weight_m">Committee(s):</span>
            <span><span>Finance</span></span>
        </div>
        """

        mock_http = MagicMock(spec=urllib3.PoolManager)
        mock_response = Mock()
        mock_response.data = html.encode()
        mock_http.request.return_value = mock_response

        email, phone, _committees = scrape_detailed_legislator_info(mock_http, "leg.maine.gov", "/member/123", "John Smith")

        assert email == "john.smith@leg.maine.gov"
        assert phone == ""
        assert "Phone not found for John Smith" in caplog.text

    @patch("src.main.time.sleep")
    def test_missing_main_info_div(self, mock_sleep: Mock) -> None:  # noqa: ARG002
        """Test returns empty strings when main-info div missing."""
        html = "<div>No main info</div>"

        mock_http = MagicMock(spec=urllib3.PoolManager)
        mock_response = Mock()
        mock_response.data = html.encode()
        mock_http.request.return_value = mock_response

        email, phone, committees = scrape_detailed_legislator_info(mock_http, "leg.maine.gov", "/member/123", "John Smith")

        assert email == ""
        assert phone == ""
        assert committees == ""


class TestCollectMunicipalityData:
    """Tests for collect_municipality_data function."""

    @patch("src.main.time.sleep")
    def test_collect_multiple_rows(self, mock_sleep: Mock) -> None:
        """Test collecting data from multiple table rows."""
        html = """
        <table class="short-table white">
            <tr><th>Header 1</th></tr>
            <tr><th>Header 2</th></tr>
            <tr>
                <td class="short-tabletdlf">Manchester - District 23 - John Smith (Democrat)</td>
                <a class="btn btn-default" href="/member/123">View</a>
            </tr>
            <tr>
                <td class="short-tabletdlf">Concord - District 5 - Jane Doe (Republican)</td>
                <a class="btn btn-default" href="/member/456">View</a>
            </tr>
        </table>
        """

        mock_http = MagicMock(spec=urllib3.PoolManager)
        mock_response = Mock()
        mock_response.data = html.encode()
        mock_http.request.return_value = mock_response

        with patch("src.main.HouseURL") as mock_url:
            mock_url.StateLegislatureNetloc = "leg.maine.gov"
            mock_url.MunicipalityListPath = "/municipalities"

            result = collect_municipality_data(mock_http, "A")

        assert len(result) == 2  # noqa: PLR2004
        assert result[0] == ("23", "Manchester", "John Smith", "Democrat", "/member/123")
        assert result[1] == ("5", "Concord", "Jane Doe", "Republican", "/member/456")
        mock_sleep.assert_called_once_with(2)

    @patch("src.main.time.sleep")
    def test_no_table_found(self, mock_sleep: Mock) -> None:  # noqa: ARG002
        """Test returns empty list when table not found."""
        html = "<div>No table here</div>"

        mock_http = MagicMock(spec=urllib3.PoolManager)
        mock_response = Mock()
        mock_response.data = html.encode()
        mock_http.request.return_value = mock_response

        with patch("src.main.HouseURL") as mock_url:
            mock_url.StateLegislatureNetloc = "leg.maine.gov"
            mock_url.MunicipalityListPath = "/municipalities"

            result = collect_municipality_data(mock_http, "A")

        assert result == []

    @patch("src.main.time.sleep")
    def test_missing_link(self, mock_sleep: Mock) -> None:  # noqa: ARG002
        """Test handles row with missing detail link."""
        html = """
        <table class="short-table white">
            <tr><th>Header 1</th></tr>
            <tr><th>Header 2</th></tr>
            <tr>
                <td class="short-tabletdlf">Manchester - District 23 - John Smith (Democrat)</td>
            </tr>
        </table>
        """

        mock_http = MagicMock(spec=urllib3.PoolManager)
        mock_response = Mock()
        mock_response.data = html.encode()
        mock_http.request.return_value = mock_response

        with patch("src.main.HouseURL") as mock_url:
            mock_url.StateLegislatureNetloc = "leg.maine.gov"
            mock_url.MunicipalityListPath = "/municipalities"

            result = collect_municipality_data(mock_http, "A")

        assert len(result) == 1
        assert result[0][4] == ""  # detail_url should be empty string


class TestGetMostCommonUrl:
    """Tests for get_most_common_url function."""

    def test_single_url(self) -> None:
        """Test returns the only URL when list has one item."""
        urls = ["/member/123"]
        assert get_most_common_url(urls) == "/member/123"

    def test_most_common_url(self) -> None:
        """Test returns most frequently occurring URL."""
        urls = ["/member/123", "/member/456", "/member/123", "/member/123", "/member/456"]
        assert get_most_common_url(urls) == "/member/123"

    def test_tie_returns_first(self) -> None:
        """Test returns first when URLs tied in frequency."""
        urls = ["/member/123", "/member/456"]
        result = get_most_common_url(urls)
        assert result in ["/member/123", "/member/456"]

    def test_empty_list(self) -> None:
        """Test returns empty string for empty list."""
        assert get_most_common_url([]) == ""


class TestGetPagination:
    """Tests for get_pagination function."""

    @patch("src.main.time.sleep")
    def test_pagination_letters(self, mock_sleep: Mock) -> None:
        """Test extracts pagination letters from page."""
        html = """
        <ul class="pagination">
            <a>A</a>
            <a>B</a>
            <a>C</a>
        </ul>
        """

        mock_http = MagicMock(spec=urllib3.PoolManager)
        mock_response = Mock()
        mock_response.data = html.encode()
        mock_http.request.return_value = mock_response

        with patch("src.main.HouseURL") as mock_url:
            mock_url.StateLegislatureNetloc = "leg.maine.gov"
            mock_url.MunicipalityListPath = "/municipalities"

            result = get_pagination(mock_http)

        assert result == ["A", "B", "C"]
        mock_sleep.assert_called_once_with(2)

    @patch("src.main.time.sleep")
    def test_no_pagination(self, mock_sleep: Mock) -> None:  # noqa: ARG002
        """Test returns empty list when pagination not found."""
        html = "<div>No pagination</div>"

        mock_http = MagicMock(spec=urllib3.PoolManager)
        mock_response = Mock()
        mock_response.data = html.encode()
        mock_http.request.return_value = mock_response

        with patch("src.main.HouseURL") as mock_url:
            mock_url.StateLegislatureNetloc = "leg.maine.gov"
            mock_url.MunicipalityListPath = "/municipalities"

            result = get_pagination(mock_http)

        assert result == []
