"""
tests/test_airports.py — Unit tests for airport geodata and distance calculations.

WHAT: Verifies Haversine great-circle distance accuracy and EU/US jurisdiction checks.
WHY:  Distance calculation determines the EU261 compensation amount (€250, €400, or €600).
      Jurisdiction classification determines whether EU261 or DOT applies.
"""

from copilot.rules.airports import (
    calculate_flight_distance_km,
    get_airport,
    haversine_distance_km,
    is_eu_airport,
    is_intra_eu_flight,
    is_us_airport,
)


def test_haversine_known_routes():
    """Verify distance calculation against known geodesic distance benchmarks."""
    # Frankfurt (FRA) to London Heathrow (LHR) ~ 655 km (Short-haul <= 1500 km)
    dist_fra_lhr = calculate_flight_distance_km("FRA", "LHR")
    assert 600.0 < dist_fra_lhr < 700.0

    # Paris (CDG) to New York (JFK) ~ 5835 km (Long-haul > 3500 km)
    dist_cdg_jfk = calculate_flight_distance_km("CDG", "JFK")
    assert 5700.0 < dist_cdg_jfk < 6000.0

    # Frankfurt (FRA) to Madrid (MAD) ~ 1425 km (Short-haul <= 1500 km)
    dist_fra_mad = calculate_flight_distance_km("FRA", "MAD")
    assert 1350.0 < dist_fra_mad < 1500.0

    # Madrid (MAD) to Warsaw (WAW) ~ 2290 km (Medium-haul 1500-3500 km)
    dist_mad_waw = calculate_flight_distance_km("MAD", "WAW")
    assert 2200.0 < dist_mad_waw < 2400.0


def test_jurisdiction_checks():
    """Verify territorial classification for European and US hubs."""
    # EU / EEA Hubs
    assert is_eu_airport("FRA") is True
    assert is_eu_airport("CDG") is True
    assert is_eu_airport("AMS") is True
    assert is_eu_airport("LHR") is True  # UK parity
    assert is_eu_airport("ZRH") is True  # Switzerland bilateral

    # US Hubs
    assert is_us_airport("JFK") is True
    assert is_us_airport("LAX") is True
    assert is_us_airport("ORD") is True
    assert is_us_airport("FRA") is False

    # Third country
    assert is_eu_airport("NRT") is False
    assert is_us_airport("NRT") is False


def test_intra_eu_flight():
    """Verify intra-Community flight detection."""
    assert is_intra_eu_flight("FRA", "CDG") is True
    assert is_intra_eu_flight("MAD", "WAW") is True
    assert is_intra_eu_flight("FRA", "JFK") is False
    assert is_intra_eu_flight("JFK", "LAX") is False


def test_unlisted_airport_fallback():
    """Unlisted airports should return a safe fallback distance and not crash."""
    dist = calculate_flight_distance_km("XYZ", "ABC")
    assert dist == 2000.0
    assert is_eu_airport("XYZ") is False
    assert is_us_airport("XYZ") is False
