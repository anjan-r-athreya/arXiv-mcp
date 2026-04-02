"""Tests for identifier parsing and normalization."""

from arxiv_library_mcp.utils.identifiers import parse_identifier, normalize_arxiv_id


class TestParseIdentifier:
    def test_new_arxiv_id(self):
        r = parse_identifier("2301.07041")
        assert r.type == "arxiv"
        assert r.value == "2301.07041"
        assert r.version is None

    def test_new_arxiv_id_with_version(self):
        r = parse_identifier("2301.07041v2")
        assert r.type == "arxiv"
        assert r.value == "2301.07041"
        assert r.version == "v2"

    def test_new_arxiv_id_five_digits(self):
        r = parse_identifier("2301.12345")
        assert r.type == "arxiv"
        assert r.value == "2301.12345"

    def test_old_arxiv_id(self):
        r = parse_identifier("hep-th/9901001")
        assert r.type == "arxiv"
        assert r.value == "hep-th/9901001"

    def test_old_arxiv_id_with_version(self):
        r = parse_identifier("hep-th/9901001v3")
        assert r.type == "arxiv"
        assert r.value == "hep-th/9901001"
        assert r.version == "v3"

    def test_doi(self):
        r = parse_identifier("10.1234/foo.bar")
        assert r.type == "doi"
        assert r.value == "10.1234/foo.bar"

    def test_doi_complex(self):
        r = parse_identifier("10.48550/arXiv.2301.07041")
        assert r.type == "doi"
        assert r.value == "10.48550/arXiv.2301.07041"

    def test_arxiv_abs_url(self):
        r = parse_identifier("https://arxiv.org/abs/2301.07041")
        assert r.type == "arxiv"
        assert r.value == "2301.07041"

    def test_arxiv_abs_url_with_version(self):
        r = parse_identifier("https://arxiv.org/abs/2301.07041v2")
        assert r.type == "arxiv"
        assert r.value == "2301.07041"
        assert r.version == "v2"

    def test_arxiv_pdf_url(self):
        r = parse_identifier("https://arxiv.org/pdf/2301.07041")
        assert r.type == "arxiv"
        assert r.value == "2301.07041"

    def test_doi_url(self):
        r = parse_identifier("https://doi.org/10.1234/foo.bar")
        assert r.type == "doi"
        assert r.value == "10.1234/foo.bar"

    def test_dx_doi_url(self):
        r = parse_identifier("https://dx.doi.org/10.1234/foo.bar")
        assert r.type == "doi"
        assert r.value == "10.1234/foo.bar"

    def test_unknown(self):
        r = parse_identifier("not an identifier")
        assert r.type == "unknown"
        assert r.value == "not an identifier"

    def test_whitespace_stripped(self):
        r = parse_identifier("  2301.07041  ")
        assert r.type == "arxiv"
        assert r.value == "2301.07041"


class TestNormalizeArxivId:
    def test_strips_version(self):
        assert normalize_arxiv_id("2301.07041v2") == "2301.07041"

    def test_no_version(self):
        assert normalize_arxiv_id("2301.07041") == "2301.07041"

    def test_old_format(self):
        assert normalize_arxiv_id("hep-th/9901001v3") == "hep-th/9901001"
