from unittest import mock

import requests

from src import geocoding

PHOTON = {"features": [
    {"properties": {"osm_type": "N", "osm_id": 1, "osm_key": "natural", "osm_value": "peak", "name": "Fern"},
     "geometry": {"coordinates": [10.79, 46.80]}},
    {"properties": {"osm_type": "N", "osm_id": 2, "osm_key": "natural", "osm_value": "peak", "name": "Nah"},
     "geometry": {"coordinates": [10.7779, 46.8046]}},
    {"properties": {"osm_type": "W", "osm_id": 3, "osm_key": "highway", "osm_value": "path", "name": "Weg"},
     "geometry": {"coordinates": [10.7778, 46.8045]}},
    {"properties": {"osm_type": "N", "osm_id": 4, "osm_key": "tourism", "osm_value": "alpine_hut", "name": "Hütte"},
     "geometry": {"coordinates": [10.7780, 46.8044]}},
]}


def test_kandidaten_nur_gipfel_und_huetten_nach_typ_und_abstand():
    k = geocoding.kandidaten_aus_photon(PHOTON, 46.8045, 10.7778, 2000)
    assert [x.name for x in k] == ["Nah", "Fern", "Hütte"]  # Weg ignoriert, Gipfel vor Hütte
    assert k[0].osm_id == "N2"


def test_vorschlag_nur_wenn_nah():
    k = geocoding.kandidaten_aus_photon(PHOTON, 46.8045, 10.7778, 2000)
    assert geocoding.vorschlag_waehlen(k).name == "Nah"
    weit = geocoding.kandidaten_aus_photon(PHOTON, 46.83, 10.80, 5000)
    assert geocoding.vorschlag_waehlen(weit) is None  # Gemeinde/ferner Gipfel wird nicht automatisch Name


def test_region_und_hoehen():
    region, ort = geocoding.region_aus_photon({"features": [{"properties": {
        "city": "Sölden", "county": "Bezirk Imst", "state": "Tirol", "country": "Österreich", "countrycode": "AT"}}]})
    assert region == "Bezirk Imst, Tirol" and ort == "Sölden"
    assert geocoding.hoehen_aus_nominatim([
        {"osm_type": "node", "osm_id": 2, "extratags": {"ele": "3768"}},
        {"osm_type": "node", "osm_id": 5, "extratags": {"ele": "ca. viel"}},
        {"osm_type": "way", "osm_id": 6, "extratags": {"ele": "2310,5 m"}},
    ]) == {"N2": 3768, "W6": 2310}


def test_ort_bestimmen_bei_ausfall_ohne_fehler():
    with mock.patch.object(geocoding.requests, "get", side_effect=requests.ConnectionError("offline")):
        info = geocoding.ort_bestimmen(47.0001234, 11.0004321)
    assert info.kandidaten == [] and info.vorschlag is None and info.gelaendehoehe_m is None
    assert len(info.hinweise) == 2
