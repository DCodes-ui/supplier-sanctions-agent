from pathlib import Path

from screener.sources.eu_fsf import parse_eu_fsf
from screener.sources.ofac_sdn import parse_ofac_sdn

FIXTURES = Path(__file__).parent / "fixtures"


def test_eu_fixture_has_name_programme_and_identifier():
    entity = parse_eu_fsf(FIXTURES / "eu_fsf.xml").records[0].entity
    assert entity.primary_name
    assert entity.programme
    assert entity.identifiers


def test_ofac_fixture_has_name_programme_and_identifier():
    entity = parse_ofac_sdn(FIXTURES / "ofac_sdn.xml").records[0].entity
    assert entity.primary_name
    assert entity.programme
    assert entity.identifiers
