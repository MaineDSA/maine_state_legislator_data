from src.main import extract_legislator_from_string


def test_extract_legislator_from_string() -> None:
    test_legislators = {
        "Allagash - District 1 - Lucien J.B. Daigle (R - Fort Kent)": ("1", "Allagash", "Lucien J.B. Daigle", "R - Fort Kent"),
        "township T11 R4 WELS - District 6 - Donald J. Ardell (R - Monticello)": ("6", "township T11 R4 WELS", "Donald J. Ardell", "R - Monticello"),
        "Abbot - District 30 - James Lee White (R - Guilford)": ("30", "Abbot", "James Lee White", "R - Guilford"),
        "plantation Lake View - District 31 - Chad R. Perkins (R - Dover-Foxcroft)": ("31", "plantation Lake View", "Chad R. Perkins", "R - Dover-Foxcroft"),
        "unorganized territory of Albany Township - District 81 - Peter Conley Wood (R - Norway) ": (
            "81",
            "unorganized territory of Albany Township",
            "Peter Conley Wood",
            "R - Norway",
        ),
        "Auburn (Part) - District 88 - Quentin J. Chapman (R - Auburn)": ("88", "Auburn (Part)", "Quentin J. Chapman", "R - Auburn"),
        "Old Orchard Beach - District 131 - Lori K. Gramlich (D - Old Orchard Beach)": (
            "131",
            "Old Orchard Beach",
            "Lori K. Gramlich",
            "D - Old Orchard Beach",
        ),
    }
    for legislator_input, legislator_output in test_legislators.items():
        legislator_data = extract_legislator_from_string(legislator_input)
        assert legislator_output == legislator_data
