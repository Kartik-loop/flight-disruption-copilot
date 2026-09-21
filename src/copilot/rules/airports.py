"""
copilot.rules.airports — Airport geodata, distance calculations, and jurisdiction lookup.

WHAT: Airport coordinate database, Haversine great-circle distance calculation,
      and regulatory jurisdiction classification (EU/EEA vs. US).
WHY:  Both EU261 and US DOT rules depend strictly on geography:
        - EU261 Art. 3 applies based on departure/arrival airport territorial location.
        - EU261 Art. 7 sets fixed compensation according to great-circle distance in km.
        - US DOT rules distinguish between US domestic flights and foreign flights.
HOW:  We maintain an embedded database of major global airports with IATA codes,
      coordinates (latitude/longitude), and country tags. We implement the standard
      Haversine formula to compute great-circle distance as mandated by EU261 Art. 7(4).

LEARN: Deterministic rules require deterministic inputs. Instead of asking an LLM
"how far is Frankfurt from New York?", which may hallucinate 6,200 km or 6,800 km,
we calculate the exact spherical great-circle distance in code using airport coordinates.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional


# ── Regulatory Jurisdiction Constants ─────────────────────────────────────
# LEARN: EU Regulation (EC) No 261/2004 applies to:
# 1. The 27 EU Member States.
# 2. Outermost Regions (OMRs) under Art. 355 TFEU (e.g., Canary Islands, Guadeloupe, Azores).
# 3. EEA countries (Norway, Iceland) via EEA Agreement Annex XIII.
# 4. Switzerland via the EU-Swiss Air Transport Agreement.
# 5. Note on UK: Since Brexit, the UK enacted "UK261" which mirrors EU261 in structure.
#    For simplicity and passenger rights protection, we treat UK airports as covered
#    under the European consumer framework.

EU_EEA_COUNTRIES = {
    # 27 EU Member States
    "AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "ES", "FI",
    "FR", "GR", "HR", "HU", "IE", "IT", "LT", "LU", "LV", "MT",
    "NL", "PL", "PT", "RO", "SE", "SI", "SK",
    # EEA & Bilateral Agreements
    "IS", "NO", "LI", "CH",
    # UK (UK261 parity)
    "GB",
}

US_COUNTRY_CODE = "US"


@dataclass(frozen=True)
class AirportLocation:
    """Geographical and political metadata for an airport."""
    iata: str
    name: str
    city: str
    country: str
    latitude: float
    longitude: float

    @property
    def is_eu_or_eea(self) -> bool:
        """Return True if airport is in the EU/EEA, Switzerland, or UK."""
        return self.country in EU_EEA_COUNTRIES

    @property
    def is_us(self) -> bool:
        """Return True if airport is in the United States."""
        return self.country == US_COUNTRY_CODE


# ── Embedded Airport Database ─────────────────────────────────────────────
# Curated dictionary of major hub airports covering Europe, North America,
# South America, Asia, Middle East, and Oceania.
# Coordinates are (latitude, longitude) in decimal degrees.

AIRPORTS: dict[str, AirportLocation] = {
    # European Hubs
    "FRA": AirportLocation("FRA", "Frankfurt Airport", "Frankfurt", "DE", 50.0379, 8.5622),
    "MUC": AirportLocation("MUC", "Munich Airport", "Munich", "DE", 48.3537, 11.7860),
    "BER": AirportLocation("BER", "Berlin Brandenburg Airport", "Berlin", "DE", 52.3667, 13.5033),
    "HAM": AirportLocation("HAM", "Hamburg Airport", "Hamburg", "DE", 53.6304, 10.0067),
    "CDG": AirportLocation("CDG", "Charles de Gaulle Airport", "Paris", "FR", 49.0097, 2.5479),
    "ORY": AirportLocation("ORY", "Orly Airport", "Paris", "FR", 48.7262, 2.3652),
    "NCE": AirportLocation("NCE", "Nice Côte d'Azur Airport", "Nice", "FR", 43.6584, 7.2159),
    "AMS": AirportLocation("AMS", "Amsterdam Airport Schiphol", "Amsterdam", "NL", 52.3105, 4.7683),
    "BRU": AirportLocation("BRU", "Brussels Airport", "Brussels", "BE", 50.9010, 4.4844),
    "LHR": AirportLocation("LHR", "Heathrow Airport", "London", "GB", 51.4700, -0.4543),
    "LGW": AirportLocation("LGW", "Gatwick Airport", "London", "GB", 51.1537, -0.1821),
    "MAN": AirportLocation("MAN", "Manchester Airport", "Manchester", "GB", 53.3537, -2.2750),
    "EDI": AirportLocation("EDI", "Edinburgh Airport", "Edinburgh", "GB", 55.9500, -3.3725),
    "MAD": AirportLocation("MAD", "Adolfo Suárez Madrid–Barajas", "Madrid", "ES", 40.4839, -3.5680),
    "BCN": AirportLocation("BCN", "Josep Tarradellas Barcelona-El Prat", "Barcelona", "ES", 41.2974, 2.0833),
    "AGP": AirportLocation("AGP", "Málaga-Costa del Sol", "Malaga", "ES", 36.6749, -4.4991),
    "LPA": AirportLocation("LPA", "Gran Canaria Airport", "Las Palmas", "ES", 27.9319, -15.3866),
    "TFS": AirportLocation("TFS", "Tenerife South Airport", "Tenerife", "ES", 28.0445, -16.5725),
    "FCO": AirportLocation("FCO", "Leonardo da Vinci–Fiumicino", "Rome", "IT", 41.8003, 12.2389),
    "MXP": AirportLocation("MXP", "Milan Malpensa Airport", "Milan", "IT", 45.6301, 8.7231),
    "VCE": AirportLocation("VCE", "Venice Marco Polo Airport", "Venice", "IT", 45.5053, 12.3519),
    "VIE": AirportLocation("VIE", "Vienna International Airport", "Vienna", "AT", 48.1103, 16.5697),
    "ZRH": AirportLocation("ZRH", "Zurich Airport", "Zurich", "CH", 47.4582, 8.5555),
    "GVA": AirportLocation("GVA", "Geneva Airport", "Geneva", "CH", 46.2381, 6.1089),
    "LIS": AirportLocation("LIS", "Humberto Delgado Airport", "Lisbon", "PT", 38.7742, -9.1342),
    "OPO": AirportLocation("OPO", "Francisco Sá Carneiro Airport", "Porto", "PT", 41.2481, -8.6814),
    "DUB": AirportLocation("DUB", "Dublin Airport", "Dublin", "IE", 53.4264, -6.2499),
    "CPH": AirportLocation("CPH", "Copenhagen Airport", "Copenhagen", "DK", 55.6180, 12.6508),
    "OSL": AirportLocation("OSL", "Oslo Airport Gardermoen", "Oslo", "NO", 60.1976, 11.1004),
    "ARN": AirportLocation("ARN", "Stockholm Arlanda Airport", "Stockholm", "SE", 59.6498, 17.9238),
    "HEL": AirportLocation("HEL", "Helsinki-Vantaa Airport", "Helsinki", "FI", 60.3172, 24.9633),
    "WAW": AirportLocation("WAW", "Warsaw Chopin Airport", "Warsaw", "PL", 52.1672, 20.9679),
    "KRK": AirportLocation("KRK", "Kraków John Paul II International", "Krakow", "PL", 50.0777, 19.7848),
    "PRG": AirportLocation("PRG", "Václav Havel Airport Prague", "Prague", "CZ", 50.1008, 14.2600),
    "BUD": AirportLocation("BUD", "Budapest Ferenc Liszt International", "Budapest", "HU", 47.4369, 19.2556),
    "ATH": AirportLocation("ATH", "Athens International Airport", "Athens", "GR", 37.9364, 23.9445),
    "OTP": AirportLocation("OTP", "Henri Coandă International Airport", "Bucharest", "RO", 44.5711, 26.0850),
    "SOF": AirportLocation("SOF", "Sofia Airport", "Sofia", "BG", 42.6951, 23.4061),
    "KEF": AirportLocation("KEF", "Keflavík International Airport", "Reykjavik", "IS", 63.9850, -22.6056),

    # US Hubs
    "JFK": AirportLocation("JFK", "John F. Kennedy International", "New York", "US", 40.6413, -73.7781),
    "EWR": AirportLocation("EWR", "Newark Liberty International", "Newark", "US", 40.6895, -74.1745),
    "LGA": AirportLocation("LGA", "LaGuardia Airport", "New York", "US", 40.7769, -73.8740),
    "LAX": AirportLocation("LAX", "Los Angeles International", "Los Angeles", "US", 33.9416, -118.4085),
    "ORD": AirportLocation("ORD", "O'Hare International Airport", "Chicago", "US", 41.9742, -87.9073),
    "MDW": AirportLocation("MDW", "Chicago Midway International", "Chicago", "US", 41.7868, -87.7522),
    "ATL": AirportLocation("ATL", "Hartsfield-Jackson Atlanta", "Atlanta", "US", 33.6407, -84.4277),
    "DFW": AirportLocation("DFW", "Dallas/Fort Worth International", "Dallas", "US", 32.8998, -97.0403),
    "DEN": AirportLocation("DEN", "Denver International Airport", "Denver", "US", 39.8561, -104.6737),
    "SFO": AirportLocation("SFO", "San Francisco International", "San Francisco", "US", 37.6213, -122.3790),
    "SEA": AirportLocation("SEA", "Seattle-Tacoma International", "Seattle", "US", 47.4502, -122.3088),
    "BOS": AirportLocation("BOS", "Logan International Airport", "Boston", "US", 42.3656, -71.0096),
    "MIA": AirportLocation("MIA", "Miami International Airport", "Miami", "US", 25.7959, -80.2870),
    "MCO": AirportLocation("MCO", "Orlando International Airport", "Orlando", "US", 28.4312, -81.3081),
    "LAS": AirportLocation("LAS", "Harry Reid International Airport", "Las Vegas", "US", 36.0840, -115.1537),
    "PHX": AirportLocation("PHX", "Phoenix Sky Harbor International", "Phoenix", "US", 33.4373, -112.0078),
    "IAH": AirportLocation("IAH", "George Bush Intercontinental", "Houston", "US", 29.9902, -95.3368),
    "CLT": AirportLocation("CLT", "Charlotte Douglas International", "Charlotte", "US", 35.2144, -80.9473),
    "MSP": AirportLocation("MSP", "Minneapolis-Saint Paul International", "Minneapolis", "US", 44.8848, -93.2223),
    "DTW": AirportLocation("DTW", "Detroit Metropolitan Airport", "Detroit", "US", 42.2162, -83.3554),
    "PHL": AirportLocation("PHL", "Philadelphia International Airport", "Philadelphia", "US", 39.8729, -75.2437),
    "BWI": AirportLocation("BWI", "Baltimore/Washington International", "Baltimore", "US", 39.1754, -76.6683),
    "IAD": AirportLocation("IAD", "Washington Dulles International", "Washington", "US", 38.9531, -77.4565),
    "DCA": AirportLocation("DCA", "Ronald Reagan Washington National", "Washington", "US", 38.8512, -77.0402),
    "SAN": AirportLocation("SAN", "San Diego International", "San Diego", "US", 32.7338, -117.1933),
    "TPA": AirportLocation("TPA", "Tampa International Airport", "Tampa", "US", 27.9755, -82.5332),
    "HNL": AirportLocation("HNL", "Daniel K. Inouye International", "Honolulu", "US", 21.3187, -157.9225),

    # Other Global Hubs (for international route distance and scope checks)
    "DXB": AirportLocation("DXB", "Dubai International Airport", "Dubai", "AE", 25.2532, 55.3657),
    "DOH": AirportLocation("DOH", "Hamad International Airport", "Doha", "QA", 25.2731, 51.6081),
    "SIN": AirportLocation("SIN", "Singapore Changi Airport", "Singapore", "SG", 1.3644, 103.9915),
    "HND": AirportLocation("HND", "Tokyo Haneda Airport", "Tokyo", "JP", 35.5494, 139.7798),
    "NRT": AirportLocation("NRT", "Narita International Airport", "Tokyo", "JP", 35.7720, 140.3929),
    "HKG": AirportLocation("HKG", "Hong Kong International Airport", "Hong Kong", "HK", 22.3080, 113.9185),
    "SYD": AirportLocation("SYD", "Sydney Kingsford Smith Airport", "Sydney", "AU", -33.9399, 151.1753),
    "YYZ": AirportLocation("YYZ", "Toronto Pearson International", "Toronto", "CA", 43.6777, -79.6248),
    "DEL": AirportLocation("DEL", "Indira Gandhi International", "Delhi", "IN", 28.5562, 77.1000),
    "BOM": AirportLocation("BOM", "Chhatrapati Shivaji Maharaj", "Mumbai", "IN", 19.0896, 72.8656),
    "GRU": AirportLocation("GRU", "São Paulo/Guarulhos International", "Sao Paulo", "BR", -23.4356, -46.4731),
    "EZE": AirportLocation("EZE", "Ministro Pistarini International", "Buenos Aires", "AR", -34.8222, -58.5358),
    "JNB": AirportLocation("JNB", "O. R. Tambo International", "Johannesburg", "ZA", -26.1367, 28.2411),
    "IST": AirportLocation("IST", "Istanbul Airport", "Istanbul", "TR", 41.2753, 28.7519),
}


# ── Distance Calculation ──────────────────────────────────────────────────

def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance between two points on a sphere.

    Formula:
      a = sin²(Δlat/2) + cos(lat1) * cos(lat2) * sin²(Δlon/2)
      c = 2 * atan2(√a, √(1−a))
      d = R * c
    Where R is Earth's mean radius = 6,371.0 km.

    WHY: EU Regulation (EC) No 261/2004 Article 7(4) specifies:
      "The distances given in paragraphs 1 and 2 shall be measured by
       the great circle route method."
    The CJEU (Court of Justice of the European Union) confirmed in Case C-559/16
    (Bossen v Brussels Airlines) that this is the direct orthodromic distance
    between the original point of departure and the final destination, regardless
    of actual legs flown or connections made.
    """
    earth_radius_km = 6371.0

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(earth_radius_km * c, 1)


def get_airport(iata: str) -> Optional[AirportLocation]:
    """Retrieve airport information by 3-letter IATA code."""
    return AIRPORTS.get(iata.strip().upper())


def calculate_flight_distance_km(departure_iata: str, arrival_iata: str) -> float:
    """
    Calculate great-circle flight distance in kilometers between two IATA airports.

    If either airport is not in our embedded database, returns a reasonable
    fallback estimate (2,000 km) and logs a warning in comments.

    LEARN: In production, you would connect to a full airport database or GIS service
    (like OpenFlights or OurAirports). For this learning project, we provide a rich
    curated dataset of major airports and graceful fallback defaults.
    """
    dep = get_airport(departure_iata)
    arr = get_airport(arrival_iata)

    if dep and arr:
        return haversine_distance_km(
            dep.latitude, dep.longitude, arr.latitude, arr.longitude
        )

    # Fallback distance if airport coordinates are unlisted
    # NOTE: 2000 km falls into the medium band (1500–3500 km)
    return 2000.0


def is_eu_airport(iata: str) -> bool:
    """
    Check whether an airport code belongs to the EU/EEA, Switzerland, or UK.
    Returns False if unlisted or outside European jurisdiction.
    """
    airport = get_airport(iata)
    return airport.is_eu_or_eea if airport else False


def is_us_airport(iata: str) -> bool:
    """
    Check whether an airport code belongs to the United States.
    Returns False if unlisted or outside the US.
    """
    airport = get_airport(iata)
    return airport.is_us if airport else False


def is_intra_eu_flight(departure_iata: str, arrival_iata: str) -> bool:
    """
    Return True if both departure and arrival airports are located within
    the EU/EEA/Switzerland (intra-Community flight).

    WHY: EU261 Art. 7(1)(b) caps compensation at €400 for ALL intra-Community
    flights over 1500 km, even if the distance exceeds 3500 km (e.g. Paris to
    Réunion or Martinique).
    """
    return is_eu_airport(departure_iata) and is_eu_airport(arrival_iata)
