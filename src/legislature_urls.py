from abc import ABC


class LegislatureURL(ABC):
    """Shared Maine legislature url class."""

    StateLegislatureNetloc = "legislature.maine.gov"
    MunicipalityListPath: str


class HouseURL(LegislatureURL):
    """Class representing the URL structure of Maine State House Representate list."""

    MunicipalityListPath = "/house/house/MemberProfiles/ListAlphaTown"
