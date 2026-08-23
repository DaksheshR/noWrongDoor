"""
Identity Matcher — Scores and matches residents across REST and XML sources.

Uses a weighted scoring algorithm to determine if a REST resident and an
XML benefit record refer to the same person, despite different data formats.

Scoring Weights:
- Name (first + last):     30%
- Date of Birth:           30% (match), 5% (missing), 0% (different)
- Address (ignore last word): 25%
- City / Town:             15%

Threshold: >= 70% = match
"""

MATCH_THRESHOLD = 70.0

# Scoring weights
WEIGHT_NAME = 30.0
WEIGHT_DOB = 30.0
WEIGHT_DOB_MISSING = 5.0
WEIGHT_ADDRESS = 25.0
WEIGHT_CITY = 15.0


def parse_xml_name(xml_name: str) -> tuple[str, str]:
    """
    Parses XML name format "LASTNAME, Firstname" into (first_name, last_name).

    The last_name in XML is all uppercase (e.g., "WHITLOCK").
    We convert it to title case (e.g., "Whitlock") to match REST format.

    Example:
        "WHITLOCK, Jennifer" -> ("Jennifer", "Whitlock")
    """
    if not xml_name or "," not in xml_name:
        return ("", "")

    parts = xml_name.split(",", 1)  # Split on first comma only
    raw_last = parts[0].strip()     # e.g., "WHITLOCK"
    raw_first = parts[1].strip()    # e.g., "Jennifer"

    # Convert last_name from ALL CAPS to Title Case
    last_name = raw_last.capitalize()  # "WHITLOCK" -> "Whitlock"

    return (raw_first, last_name)


def compare_names(rest_first: str, rest_last: str,
                  xml_first: str, xml_last: str) -> float:
    """
    Compares first_name and last_name from REST with parsed XML name.
    Case-insensitive comparison.

    Returns: WEIGHT_NAME (30.0) if match, 0.0 if different.
    """
    if not rest_first or not rest_last or not xml_first or not xml_last:
        return 0.0

    if (rest_first.lower() == xml_first.lower() and
            rest_last.lower() == xml_last.lower()):
        return WEIGHT_NAME

    return 0.0


def compare_dob(rest_dob: str | None, xml_born: str | None) -> float:
    """
    Compares date_of_birth (REST) with born (XML).

    Returns:
        WEIGHT_DOB (30.0) if both present and match.
        WEIGHT_DOB_MISSING (5.0) if either is missing/None.
        0.0 if both present but different.
    """
    # If either is missing, give partial credit
    if not rest_dob or not xml_born:
        return WEIGHT_DOB_MISSING

    # Both present — compare directly
    if rest_dob.strip() == xml_born.strip():
        return WEIGHT_DOB

    return 0.0


def compare_address(rest_addr: str | None, xml_addr: str | None) -> float:
    """
    Compares address_line (REST) with addr (XML).
    Ignores the last word (which is abbreviated in REST, full in XML).

    Example:
        REST: "435 Alder Ave"    -> ["435", "Alder"]
        XML:  "435 Alder Avenue" -> ["435", "Alder"]
        Match!

    Returns: WEIGHT_ADDRESS (25.0) if match, 0.0 if different.
    """
    if not rest_addr or not xml_addr:
        return 0.0

    rest_words = rest_addr.strip().split()
    xml_words = xml_addr.strip().split()

    # Remove last word (abbreviation vs full) and compare the rest
    rest_without_last = rest_words[:-1] if len(rest_words) > 1 else rest_words
    xml_without_last = xml_words[:-1] if len(xml_words) > 1 else xml_words

    if rest_without_last == xml_without_last:
        return WEIGHT_ADDRESS

    return 0.0


def compare_city(rest_city: str | None, xml_town: str | None) -> float:
    """
    Compares city (REST) with town (XML).
    Case-insensitive comparison.

    Returns: WEIGHT_CITY (15.0) if match, 0.0 if different.
    """
    if not rest_city or not xml_town:
        return 0.0

    if rest_city.strip().lower() == xml_town.strip().lower():
        return WEIGHT_CITY

    return 0.0


def calculate_match_score(rest_resident: dict, xml_record: dict) -> float:
    """
    Calculates the match score between a REST resident and an XML record.

    Returns a score from 0.0 to 100.0.
    """
    # Parse XML name into first_name, last_name
    xml_first, xml_last = parse_xml_name(xml_record.get("name", ""))

    # Score each field
    name_score = compare_names(
        rest_resident.get("first_name", ""),
        rest_resident.get("last_name", ""),
        xml_first,
        xml_last,
    )

    dob_score = compare_dob(
        rest_resident.get("date_of_birth"),
        xml_record.get("born"),
    )

    address_score = compare_address(
        rest_resident.get("address_line"),
        xml_record.get("address"),
    )

    city_score = compare_city(
        rest_resident.get("city"),
        xml_record.get("town"),
    )

    return name_score + dob_score + address_score + city_score


def find_matches(residents: list[dict],
                 benefits: list[dict]) -> dict[str, list[dict]]:
    """
    Finds matching XML benefit records for each REST resident.

    For each REST resident, compares against ALL XML records and
    returns any with a score >= 70%.

    Returns:
        A dictionary mapping REST resident IDs to their matched
        XML benefit records (with match scores).
    """
    matches: dict[str, list[dict]] = {}

    for resident in residents:
        resident_id = resident.get("id", "")
        resident_matches = []

        for benefit in benefits:
            score = calculate_match_score(resident, benefit)

            if score >= MATCH_THRESHOLD:
                # Add the match with its score
                match_entry = {
                    **benefit,
                    "match_score": score,
                }
                resident_matches.append(match_entry)

        if resident_matches:
            # Sort by score descending (best match first)
            resident_matches.sort(key=lambda m: m["match_score"], reverse=True)
            matches[resident_id] = resident_matches

    return matches


def find_matches_for_single(resident: dict,
                            benefits: list[dict]) -> list[dict]:
    """
    Finds matching XML benefit records for a single REST resident.

    Returns:
        A list of matched XML benefit records with scores.
    """
    matched = []

    for benefit in benefits:
        score = calculate_match_score(resident, benefit)

        if score >= MATCH_THRESHOLD:
            match_entry = {
                **benefit,
                "match_score": score,
            }
            matched.append(match_entry)

    matched.sort(key=lambda m: m["match_score"], reverse=True)
    return matched
