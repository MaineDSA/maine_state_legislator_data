from collections.abc import Callable, Generator
from unittest.mock import MagicMock, Mock, patch

import pytest
import urllib3
from bs4 import BeautifulSoup

from src.legislature_urls import LegislatureURL
from src.main import (
    collect_municipality_data,
    extract_legislator_from_string,
    get_most_common_url,
    get_pagination,
    scrape_committees,
    scrape_detailed_legislator_info,
)


@pytest.fixture
def mock_http() -> MagicMock:
    """Create a mock HTTP pool manager."""
    return MagicMock(spec=urllib3.PoolManager)


@pytest.fixture
def mock_http_response(mock_http: MagicMock) -> Callable:
    """Create a mock HTTP response factory."""

    def _make_response(html: str) -> MagicMock:
        mock_response = Mock()
        mock_response.data = html.encode()
        mock_http.request.return_value = mock_response
        return mock_http

    return _make_response


@pytest.fixture
def mock_house_url() -> Generator[LegislatureURL]:
    """Mock HouseURL configuration."""
    with patch("src.main.HouseURL") as mock_url:
        mock_url.StateLegislatureNetloc = "leg.maine.gov"
        mock_url.MunicipalityListPath = "/municipalities"
        yield mock_url


class TestExtractLegislatorFromString:
    """Tests for extract_legislator_from_string function."""

    @pytest.mark.parametrize(
        ("text", "expected_district", "expected_town", "expected_member", "expected_party"),
        [
            ("Manchester - District 23 - John Smith (Democrat)", "23", "Manchester", "John Smith", "Democrat"),
            ("Manchester\n\n - District 23  -   John Smith  (Democrat)", "23", "Manchester", "John Smith", "Democrat"),
            ("Weare (West) - District 5 - Jane Doe (Republican)", "5", "Weare (West)", "Jane Doe", "Republican"),
            ("Concord - District 1 - Bob Johnson (Independent)", "1", "Concord", "Bob Johnson", "Independent"),
        ],
        ids=["valid_string", "multiline_whitespace", "special_characters", "independent_party"],
    )
    def test_valid_extraction(self, text: str, expected_district: str, expected_town: str, expected_member: str, expected_party: str) -> None:
        """Test extraction from valid municipality strings."""
        district, town, member, party = extract_legislator_from_string(text)

        assert district == expected_district
        assert town == expected_town
        assert member == expected_member
        assert party == expected_party

    @pytest.mark.parametrize(
        "text",
        [
            "Manchester - 23 - John Smith (Democrat)",
            "Invalid format without proper structure",
            "",
        ],
        ids=["no_district_keyword", "malformed_string", "empty_string"],
    )
    def test_invalid_extraction(self, text: str) -> None:
        """Test returns empty strings for invalid input."""
        district, town, member, party = extract_legislator_from_string(text)

        assert district == ""
        assert town == ""
        assert member == ""
        assert party == ""


class TestScrapeCommittees:
    """Tests for scrape_committees function."""

    @pytest.mark.parametrize(
        ("html", "expected"),
        [
            (
                """
                <span class="font_weight_m">Committee(s):</span>
                <span><span>Finance</span></span>
                """,
                "Finance",
            ),
            (
                """
                <span class="font_weight_m">Committee(s):</span>
                <span><span>Finance</span><span>Education</span></span>
                """,
                "Finance; Education",
            ),
            (
                """
                <span class="font_weight_m">Committee(s):</span>
                <span><span>Finance</span><span>Education</span><span>Health</span></span>
                """,
                "Finance; Education; Health",
            ),
            (
                """
                <span class="font_weight_m">Other Label:</span>
                """,
                "",
            ),
            ("", ""),
        ],
        ids=["single_committee", "two_committees", "three_committees", "no_committees", "empty_html"],
    )
    def test_committee_extraction(self, html: str, expected: str) -> None:
        """Test extraction of committee information."""
        soup = BeautifulSoup(html, "html.parser")
        spans = soup.find_all("span", class_="font_weight_m")

        result = scrape_committees(spans)
        assert result == expected


class TestScrapeDetailedLegislatorInfo:
    """Tests for scrape_detailed_legislator_info function."""

    @pytest.fixture
    def mock_sleep(self) -> Generator[Callable]:
        """Mock time.sleep for all tests in this class."""
        with patch("src.main.time.sleep") as mock:
            yield mock

    def test_complete_info(self, mock_http_response: Mock, mock_sleep: Mock) -> None:
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

        http = mock_http_response(html)
        email, phone, committees = scrape_detailed_legislator_info(http, "leg.maine.gov", "/member/123", "John Smith")

        assert email == "john.smith@leg.maine.gov"
        assert phone == "(603) 555-1234"
        assert committees == "Finance"
        mock_sleep.assert_called_once_with(2)

    @pytest.mark.parametrize(
        ("html", "expected_email", "expected_phone", "expected_log"),
        [
            (
                """
                <div id="main-info">
                    <p>
                        <span class="text_right">(603) 555-1234</span>
                    </p>
                    <span class="font_weight_m">Committee(s):</span>
                    <span><span>Finance</span></span>
                </div>
                """,
                "",
                "(603) 555-1234",
                "Email not found for John Smith",
            ),
            (
                """
                <div id="main-info">
                    <p>
                        <a href="mailto:john.smith@leg.maine.gov">john.smith@leg.maine.gov</a>
                    </p>
                    <span class="font_weight_m">Committee(s):</span>
                    <span><span>Finance</span></span>
                </div>
                """,
                "john.smith@leg.maine.gov",
                "",
                "Phone not found for John Smith",
            ),
        ],
        ids=["missing_email", "missing_phone"],
    )
    def test_missing_info_with_warning(  # noqa: PLR0913
        self,
        mock_http_response: Mock,
        mock_sleep: Mock,  # noqa: ARG002
        caplog: pytest.LogCaptureFixture,
        html: str,
        expected_email: str,
        expected_phone: str,
        expected_log: str,
    ) -> None:
        """Test handles missing information with appropriate warnings."""
        http = mock_http_response(html)
        email, phone, _committees = scrape_detailed_legislator_info(http, "leg.maine.gov", "/member/123", "John Smith")

        assert email == expected_email
        assert phone == expected_phone
        assert expected_log in caplog.text

    def test_missing_main_info_div(self, mock_http_response: Mock, mock_sleep: Mock) -> None:  # noqa: ARG002
        """Test returns empty strings when main-info div missing."""
        html = "<div>No main info</div>"

        http = mock_http_response(html)
        email, phone, committees = scrape_detailed_legislator_info(http, "leg.maine.gov", "/member/123", "John Smith")

        assert email == ""
        assert phone == ""
        assert committees == ""


class TestCollectMunicipalityData:
    """Tests for collect_municipality_data function."""

    @pytest.fixture
    def mock_sleep(self) -> Generator[Callable]:
        """Mock time.sleep for all tests in this class."""
        with patch("src.main.time.sleep") as mock:
            yield mock

    def test_collect_multiple_rows(self, mock_http_response: Mock, mock_house_url: Mock, mock_sleep: Mock) -> None:  # noqa: ARG002
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

        http = mock_http_response(html)
        result = collect_municipality_data(http, "A")

        assert len(result) == 2  # noqa: PLR2004
        assert result[0] == ("23", "Manchester", "John Smith", "Democrat", "/member/123")
        assert result[1] == ("5", "Concord", "Jane Doe", "Republican", "/member/456")
        mock_sleep.assert_called_once_with(2)

    @pytest.mark.parametrize(
        ("html", "expected_length", "expected_detail_url"),
        [
            ("<div>No table here</div>", 0, None),
            (
                """
                <table class="short-table white">
                    <tr><th>Header 1</th></tr>
                    <tr><th>Header 2</th></tr>
                    <tr>
                        <td class="short-tabletdlf">Manchester - District 23 - John Smith (Democrat)</td>
                    </tr>
                </table>
                """,
                1,
                "",
            ),
        ],
        ids=["no_table", "missing_link"],
    )
    def test_edge_cases(  # noqa: PLR0913
        self,
        mock_http_response: Mock,
        mock_house_url: Mock,  # noqa: ARG002
        mock_sleep: Mock,  # noqa: ARG002
        html: str,
        expected_length: int,
        expected_detail_url: str | None,
    ) -> None:
        """Test edge cases in municipality data collection."""
        http = mock_http_response(html)
        result = collect_municipality_data(http, "A")

        assert len(result) == expected_length
        if expected_detail_url is not None:
            assert result[0][4] == expected_detail_url


class TestGetMostCommonUrl:
    """Tests for get_most_common_url function."""

    @pytest.mark.parametrize(
        ("urls", "expected"),
        [
            (["/member/123"], "/member/123"),
            (["/member/123", "/member/456", "/member/123", "/member/123", "/member/456"], "/member/123"),
            ([], ""),
        ],
        ids=["single_url", "most_common_url", "empty_list"],
    )
    def test_url_frequency(self, urls: list[str], expected: str) -> None:
        """Test URL frequency counting."""
        result = get_most_common_url(urls)
        if expected:
            assert result == expected
        else:
            assert result == ""

    def test_tie_returns_valid_url(self) -> None:
        """Test returns valid URL when URLs tied in frequency."""
        urls = ["/member/123", "/member/456"]
        result = get_most_common_url(urls)
        assert result in urls


class TestGetPagination:
    """Tests for get_pagination function."""

    @pytest.fixture
    def mock_sleep(self) -> Generator[Callable]:
        """Mock time.sleep for all tests in this class."""
        with patch("src.main.time.sleep") as mock:
            yield mock

    @pytest.mark.parametrize(
        ("html", "expected"),
        [
            (
                """
                <ul class="pagination">
                    <a>A</a>
                    <a>B</a>
                    <a>C</a>
                </ul>
                """,
                ["A", "B", "C"],
            ),
            ("<div>No pagination</div>", []),
        ],
        ids=["pagination_present", "no_pagination"],
    )
    def test_pagination_extraction(self, mock_http_response: Mock, mock_house_url: Mock, mock_sleep: Mock, html: str, expected: list[str]) -> None:  # noqa: ARG002
        """Test pagination letter extraction."""
        http = mock_http_response(html)
        result = get_pagination(http)

        assert result == expected
        mock_sleep.assert_called_once_with(2)
