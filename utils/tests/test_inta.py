"""
Tests para criza/utils/inta.py

Unit tests: sin red, mock de _get.
Integration tests: requieren acceso a repositorio.inta.gob.ar. Correr con: pytest -m integration
"""

import xml.etree.ElementTree as ET
from unittest.mock import patch, MagicMock

import pytest

import criza.utils.inta as inta


# ── fixtures de XML OAI-PMH mock ─────────────────────────────────────────────

_RECORD_OPEN_XML = """<?xml version="1.0" encoding="UTF-8"?>
<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">
  <GetRecord>
    <record>
      <header>
        <identifier>oai:repositorio.inta.gob.ar:20.500.12123/999</identifier>
        <datestamp>2023-01-15T10:00:00Z</datestamp>
        <setSpec>com_20.500.12123_172</setSpec>
      </header>
      <metadata>
        <oai_dc:dc xmlns:oai_dc="http://www.openarchives.org/OAI/2.0/oai_dc/"
                   xmlns:dc="http://purl.org/dc/elements/1.1/">
          <dc:title>Estudio sobre control biológico de garrapatas en bovinos</dc:title>
          <dc:creator>García, Juan</dc:creator>
          <dc:creator>López, María</dc:creator>
          <dc:subject>Garrapata</dc:subject>
          <dc:subject>Control Biológico</dc:subject>
          <dc:subject>Bovinos</dc:subject>
          <dc:description>Este trabajo analiza métodos de control biológico para el manejo sustentable de garrapatas en bovinos de la región pampeana. Se evaluaron diferentes hongos entomopatógenos.</dc:description>
          <dc:description>EEA Marcos Juárez</dc:description>
          <dc:date>2023-01-15T10:00:00Z</dc:date>
          <dc:date>2023</dc:date>
          <dc:type>info:eu-repo/semantics/article</dc:type>
          <dc:identifier>http://hdl.handle.net/20.500.12123/999</dc:identifier>
          <dc:identifier>https://repositorio.inta.gob.ar/bitstream/handle/20.500.12123/999/paper.pdf</dc:identifier>
          <dc:identifier>https://doi.org/10.1234/fake.doi</dc:identifier>
          <dc:language>spa</dc:language>
          <dc:rights>info:eu-repo/semantics/openAccess</dc:rights>
          <dc:rights>http://creativecommons.org/licenses/by-nc-sa/4.0/</dc:rights>
          <dc:source>Revista de Biotecnología, 10(2): 45-58. (2023)</dc:source>
        </oai_dc:dc>
      </metadata>
    </record>
  </GetRecord>
</OAI-PMH>"""

_RECORD_RESTRICTED_XML = """<?xml version="1.0" encoding="UTF-8"?>
<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">
  <GetRecord>
    <record>
      <header>
        <identifier>oai:repositorio.inta.gob.ar:20.500.12123/888</identifier>
        <datestamp>2022-06-01T00:00:00Z</datestamp>
      </header>
      <metadata>
        <oai_dc:dc xmlns:oai_dc="http://www.openarchives.org/OAI/2.0/oai_dc/"
                   xmlns:dc="http://purl.org/dc/elements/1.1/">
          <dc:title>Paper con acceso restringido</dc:title>
          <dc:creator>Rodríguez, Carlos</dc:creator>
          <dc:date>2022</dc:date>
          <dc:type>info:eu-repo/semantics/article</dc:type>
          <dc:identifier>http://hdl.handle.net/20.500.12123/888</dc:identifier>
          <dc:rights>info:eu-repo/semantics/restrictedAccess</dc:rights>
          <dc:description>Abstract corto sin suficiente longitud</dc:description>
          <dc:description>Institución origen</dc:description>
        </oai_dc:dc>
      </metadata>
    </record>
  </GetRecord>
</OAI-PMH>"""

_RECORD_DELETED_XML = """<?xml version="1.0" encoding="UTF-8"?>
<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">
  <GetRecord>
    <record>
      <header status="deleted">
        <identifier>oai:repositorio.inta.gob.ar:20.500.12123/777</identifier>
        <datestamp>2023-01-01T00:00:00Z</datestamp>
      </header>
    </record>
  </GetRecord>
</OAI-PMH>"""


# ── unit tests — _parse_record ────────────────────────────────────────────────

class TestParseRecord:

    def _get_record_elem(self, xml_str: str) -> ET.Element:
        root = ET.fromstring(xml_str)
        ns = "http://www.openarchives.org/OAI/2.0/"
        return root.find(f".//{{{ns}}}record")

    def test_parsea_registro_abierto(self):
        elem = self._get_record_elem(_RECORD_OPEN_XML)
        result = inta._parse_record(elem)

        assert result is not None
        assert result["titulo"] == "Estudio sobre control biológico de garrapatas en bovinos"
        assert "García, Juan" in result["autores"]
        assert "López, María" in result["autores"]
        assert result["año"] == "2023"
        assert "Garrapata" in result["subjects"]
        assert "Control Biológico" in result["subjects"]
        assert result["open_access"] is True
        assert result["doi"] == "https://doi.org/10.1234/fake.doi"
        assert result["handle_id"] == "20.500.12123/999"

    def test_pdf_url_solo_en_open_access(self):
        elem_open = self._get_record_elem(_RECORD_OPEN_XML)
        elem_restricted = self._get_record_elem(_RECORD_RESTRICTED_XML)

        result_open = inta._parse_record(elem_open)
        result_restricted = inta._parse_record(elem_restricted)

        assert result_open["pdf_url"] is not None
        assert "bitstream" in result_open["pdf_url"]
        assert result_restricted["pdf_url"] is None

    def test_registro_deleted_retorna_none(self):
        elem = self._get_record_elem(_RECORD_DELETED_XML)
        result = inta._parse_record(elem)
        assert result is None

    def test_abstract_es_la_description_larga(self):
        elem = self._get_record_elem(_RECORD_OPEN_XML)
        result = inta._parse_record(elem)
        assert len(result["abstract"]) > 80
        assert "hongos entomopatógenos" in result["abstract"]

    def test_acceso_restringido_sin_pdf(self):
        elem = self._get_record_elem(_RECORD_RESTRICTED_XML)
        result = inta._parse_record(elem)
        assert result["open_access"] is False
        assert result["pdf_url"] is None


class TestExtractDate:

    def test_prefiere_ano_solo(self):
        assert inta._extract_date(["2023-01-15T10:00:00Z", "2023-01-15T10:00:00Z", "2023"]) == "2023"

    def test_extrae_ano_de_iso(self):
        assert inta._extract_date(["2022-06-01T00:00:00Z"]) == "2022"

    def test_retorna_none_si_vacio(self):
        assert inta._extract_date([]) is None


class TestFindPdfUrl:

    def test_retorna_none_si_acceso_restringido(self):
        result = inta._find_pdf_url(
            ["https://repositorio.inta.gob.ar/bitstream/handle/123/doc.pdf"],
            ["info:eu-repo/semantics/restrictedAccess"],
        )
        assert result is None

    def test_retorna_bitstream_inta_en_open_access(self):
        url = "https://repositorio.inta.gob.ar/bitstream/handle/123/doc.pdf"
        result = inta._find_pdf_url(
            [url, "http://hdl.handle.net/123"],
            ["info:eu-repo/semantics/openAccess"],
        )
        assert result == url

    def test_no_retorna_handle_como_pdf(self):
        result = inta._find_pdf_url(
            ["http://hdl.handle.net/20.500.12123/999"],
            ["info:eu-repo/semantics/openAccess"],
        )
        assert result is None


# ── integration tests ─────────────────────────────────────────────────────────

@pytest.mark.integration
class TestIntegration:

    def test_search_devuelve_resultados(self):
        results = inta.search("garrapata", max_results=3)
        assert len(results) > 0
        assert all("titulo" in r for r in results)
        assert all("handle_id" in r for r in results)

    def test_get_record_metadata_completa(self):
        rec = inta.get_record("20.500.12123/23889")
        assert rec is not None
        assert rec["titulo"] != ""
        assert len(rec["autores"]) > 0
        assert rec["open_access"] is True

    def test_get_pdf_url_encuentra_bitstream(self):
        url = inta.get_pdf_url("20.500.12123/23889")
        assert url is not None
        assert "bitstream" in url
        assert url.endswith(".pdf")

    def test_harvest_biotecnologia_retorna_registros(self):
        records = inta.harvest("biotecnologia", max_records=5)
        assert len(records) == 5
        assert all("titulo" in r for r in records)
        assert all("subjects" in r for r in records)

    def test_harvest_con_fecha_filtra(self):
        records = inta.harvest("biotecnologia", from_date="2024-01-01", max_records=10)
        years = [int(r["año"]) for r in records if r["año"] and r["año"].isdigit()]
        assert all(y >= 2024 for y in years)
