import gzip
from datetime import date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from silver_platter.providers import (
    CsvFxRateProvider,
    DisclosureMetadataInput,
    EcosFxRateProvider,
    FxRateInput,
    KrxDailyPriceProvider,
    KrxKindDisclosureProvider,
    OpenDartDisclosureProvider,
    ProviderMetadata,
    SecEdgarDisclosureProvider,
    SecurityReference,
    StaticDisclosureMetadataProvider,
    StaticFxRateProvider,
    StaticReferenceDataProvider,
    _default_json_fetcher,
    default_mvp_provider_catalog,
    license_policy_from_provider,
)


class ProviderTests(TestCase):
    def test_default_catalog_contains_mvp_free_sources(self):
        catalog = default_mvp_provider_catalog()
        codes = {provider.provider_code for provider in catalog}

        self.assertIn("krx_free", codes)
        self.assertIn("krx_data", codes)
        self.assertIn("opendart", codes)
        self.assertIn("sec_edgar", codes)
        self.assertIn("ecos_bok", codes)
        self.assertIn("federal_reserve", codes)
        self.assertIn("ecb", codes)
        self.assertIn("ofac", codes)
        self.assertIn("free_fx_placeholder", codes)

    def test_license_policy_inherits_provider_rights(self):
        provider = ProviderMetadata("vendor", "headline", True, False, False, 80)

        policy = license_policy_from_provider(provider)

        self.assertEqual("vendor", policy.provider_code)
        self.assertEqual("vendor_mvp_policy", policy.license_name)
        self.assertTrue(policy.can_store)
        self.assertTrue(policy.can_transform)
        self.assertFalse(policy.can_display_realtime)
        self.assertFalse(policy.can_redistribute)

    def test_static_reference_provider_returns_securities(self):
        provider = StaticReferenceDataProvider(
            "krx_free",
            [
                SecurityReference(
                    symbol="005930",
                    security_name="Samsung Electronics",
                    market_code="KOSPI",
                    country_code="KOR",
                    currency="KRW",
                    asset_type="stock",
                    exchange_code="KRX",
                    provider_symbol="005930",
                )
            ],
        )

        self.assertEqual("reference_data", provider.metadata.provider_type)
        self.assertEqual(1, len(list(provider.get_securities())))

    def test_static_disclosure_provider_filters_by_symbol(self):
        disclosure = DisclosureMetadataInput(
            provider_event_id="dart-1",
            security_id="005930",
            disclosure_type="earnings",
            title="Quarterly report",
            disclosed_at=datetime(2026, 5, 22, 9, 0, 0),
            source_url="https://dart.fss.or.kr/",
        )
        provider = StaticDisclosureMetadataProvider("opendart", [disclosure])

        self.assertEqual([disclosure], list(provider.get_disclosures("005930")))
        self.assertEqual([], list(provider.get_disclosures("000660")))

    def test_static_fx_provider_filters_pair(self):
        rate = FxRateInput("USD", "KRW", date(2026, 5, 22), 1360.0, "free_fx_placeholder")
        provider = StaticFxRateProvider("free_fx_placeholder", [rate])

        self.assertEqual([rate], list(provider.get_rates("usd", "krw")))
        self.assertEqual([], list(provider.get_rates("KRW", "USD")))

    def test_csv_fx_provider_loads_pair_from_file(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "fx.csv"
            path.write_text(
                "base_currency,quote_currency,rate_date,rate\n"
                "USD,KRW,2026-05-22,1360.5\n"
                "EUR,KRW,2026-05-22,1480.0\n",
                encoding="utf-8",
            )
            provider = CsvFxRateProvider(path, provider_code="manual_fx")

            rates = list(provider.get_rates("usd", "krw"))

        self.assertEqual(1, len(rates))
        self.assertEqual("manual_fx", rates[0].provider_code)
        self.assertEqual(date(2026, 5, 22), rates[0].rate_date)
        self.assertEqual(1360.5, rates[0].rate)

    def test_csv_fx_provider_requires_columns(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "fx.csv"
            path.write_text("base_currency,rate\nUSD,1360.5\n", encoding="utf-8")
            provider = CsvFxRateProvider(path)

            with self.assertRaises(ValueError):
                list(provider.get_rates("USD", "KRW"))

    def test_krx_daily_price_provider_normalizes_download_csv(self):
        calls = []

        def fetcher(otp_url, download_url, headers, params):
            calls.append((otp_url, download_url, headers, params))
            return (
                "종목코드,종목명,시장구분,종가,시가,고가,저가,거래량,거래대금\n"
                "005930,삼성전자,KOSPI,\"70,500\",\"70,000\",\"71,000\",\"69,900\","
                "\"15,000,000\",\"1,050,000,000,000\"\n"
                "000660,SK하이닉스,KOSPI,\"185,000\",\"184,000\",\"187,000\","
                "\"183,000\",\"3,000,000\",\"555,000,000,000\"\n"
            )

        provider = KrxDailyPriceProvider(date(2026, 5, 22), fetcher=fetcher)

        bars = list(provider.get_price_bars("005930"))

        self.assertEqual(1, len(bars))
        self.assertEqual("krx_data", provider.metadata.provider_code)
        self.assertEqual("005930", bars[0].security_id)
        self.assertEqual(datetime(2026, 5, 22, 16, 0, 0), bars[0].bar_ts)
        self.assertEqual(70500.0, bars[0].close_price)
        self.assertEqual(15000000.0, bars[0].volume)
        self.assertEqual(1050000000000.0, bars[0].turnover_krw)
        self.assertEqual("ALL", calls[0][3]["mktId"])
        self.assertEqual("20260522", calls[0][3]["trdDd"])
        self.assertEqual("dbms/MDC/STAT/standard/MDCSTAT01501", calls[0][3]["url"])

    def test_sec_edgar_provider_requires_user_agent(self):
        with self.assertRaises(ValueError):
            SecEdgarDisclosureProvider("")

    def test_opendart_provider_requires_api_key(self):
        with self.assertRaises(ValueError):
            OpenDartDisclosureProvider("")

    def test_ecos_fx_provider_requires_api_key(self):
        with self.assertRaises(ValueError):
            EcosFxRateProvider("", date(2026, 5, 1), date(2026, 5, 22))

    def test_ecos_fx_provider_normalizes_statistic_search_rows(self):
        calls = []

        def fetcher(url, headers):
            calls.append((url, headers))
            return {
                "StatisticSearch": {
                    "RESULT": {"CODE": "INFO-000", "MESSAGE": "정상"},
                    "row": [
                        {
                            "TIME": "20260521",
                            "DATA_VALUE": "1365.5",
                            "ITEM_CODE1": "0000001",
                            "ITEM_NAME1": "원/미국달러",
                        }
                    ],
                }
            }

        provider = EcosFxRateProvider(
            "ecos-key",
            date(2026, 5, 1),
            date(2026, 5, 22),
            fetcher=fetcher,
        )

        rates = list(provider.get_rates("usd", "krw"))

        self.assertEqual(1, len(rates))
        self.assertEqual("ecos_bok", provider.metadata.provider_code)
        self.assertEqual("USD", rates[0].base_currency)
        self.assertEqual("KRW", rates[0].quote_currency)
        self.assertEqual(date(2026, 5, 21), rates[0].rate_date)
        self.assertEqual(1365.5, rates[0].rate)
        self.assertIn(
            "/StatisticSearch/ecos-key/json/kr/1/100/731Y001/D/20260501/20260522/0000001",
            calls[0][0],
        )

    def test_ecos_fx_provider_requires_pair_item_code(self):
        provider = EcosFxRateProvider(
            "ecos-key",
            date(2026, 5, 1),
            date(2026, 5, 22),
            item_code_lookup={"USD/KRW": "0000001"},
        )

        with self.assertRaises(ValueError):
            list(provider.get_rates("GBP", "KRW"))

    def test_krx_kind_provider_normalizes_company_search_html(self):
        calls = []

        def fetcher(url, headers, params):
            calls.append((url, headers, params))
            return """
            <table>
              <tr><th>번호</th><th>시간</th><th>회사명</th><th>공시제목</th><th>제출인</th></tr>
              <tr>
                <td>19183</td>
                <td>2026-05-21 20:00</td>
                <td>삼성전자</td>
                <td><a href="/common/disclsviewer.do?method=search&acptno=20260521000123">기업설명회(IR) 개최</a></td>
                <td>유가증권시장본부</td>
              </tr>
            </table>
            """

        provider = KrxKindDisclosureProvider(
            begin_date=date(2026, 5, 1),
            end_date=date(2026, 5, 22),
            fetcher=fetcher,
        )

        disclosures = list(provider.get_disclosures("005930"))

        self.assertEqual(1, len(disclosures))
        self.assertEqual("krx_kind", provider.metadata.provider_code)
        self.assertEqual("19183", disclosures[0].provider_event_id)
        self.assertEqual("005930", disclosures[0].security_id)
        self.assertEqual("기업설명회(IR) 개최", disclosures[0].title)
        self.assertEqual(datetime(2026, 5, 21, 20, 0, 0), disclosures[0].disclosed_at)
        self.assertIn("/common/disclsviewer.do", disclosures[0].source_url)
        self.assertEqual("searchDisclosureByCorpMain", calls[0][2]["method"])
        self.assertEqual("005930", calls[0][2]["searchCorpName"])
        self.assertEqual("2026-05-01", calls[0][2]["fromDate"])

    def test_opendart_provider_normalizes_disclosure_metadata(self):
        calls = []

        def fetcher(url, headers, params):
            calls.append((url, headers, params))
            return {
                "status": "000",
                "message": "정상",
                "list": [
                    {
                        "corp_code": "00126380",
                        "corp_name": "삼성전자",
                        "stock_code": "005930",
                        "corp_cls": "Y",
                        "report_nm": "반기보고서",
                        "rcept_no": "20260522000123",
                        "flr_nm": "삼성전자",
                        "rcept_dt": "20260522",
                        "rm": "",
                    }
                ],
            }

        provider = OpenDartDisclosureProvider(
            "dart-key",
            corp_code_lookup={"005930": "00126380"},
            begin_date=date(2026, 5, 1),
            end_date=date(2026, 5, 22),
            fetcher=fetcher,
        )

        disclosures = list(provider.get_disclosures("005930"))

        self.assertEqual(1, len(disclosures))
        self.assertEqual("opendart", provider.metadata.provider_code)
        self.assertEqual("20260522000123", disclosures[0].provider_event_id)
        self.assertEqual("005930", disclosures[0].security_id)
        self.assertEqual("반기보고서", disclosures[0].title)
        self.assertIn("rcpNo=20260522000123", disclosures[0].source_url)
        self.assertEqual("https://opendart.fss.or.kr/api/list.json", calls[0][0])
        self.assertEqual("dart-key", calls[0][2]["crtfc_key"])
        self.assertEqual("00126380", calls[0][2]["corp_code"])
        self.assertEqual("20260501", calls[0][2]["bgn_de"])

    def test_sec_edgar_provider_normalizes_submission_metadata(self):
        calls = []

        def fetcher(url, headers):
            calls.append((url, headers))
            return {
                "filings": {
                    "recent": {
                        "accessionNumber": [
                            "0000320193-26-000010",
                            "0000320193-26-000011",
                        ],
                        "form": ["10-Q", "4"],
                        "filingDate": ["2026-05-22", "2026-05-23"],
                        "acceptanceDateTime": [
                            "2026-05-22T21:31:02.000Z",
                            "2026-05-23T10:00:00.000Z",
                        ],
                        "reportDate": ["2026-03-31", "2026-05-23"],
                        "primaryDocument": ["aapl-20260331.htm", "xslF345X05/doc.xml"],
                        "primaryDocDescription": [
                            "Quarterly report",
                            "Ownership form",
                        ],
                    }
                }
            }

        provider = SecEdgarDisclosureProvider(
            "Silver Platter dev@example.com",
            cik_lookup={"AAPL": "320193"},
            forms=["10-Q"],
            fetcher=fetcher,
        )

        disclosures = list(provider.get_disclosures("aapl"))

        self.assertEqual(1, len(disclosures))
        self.assertEqual("sec_edgar", provider.metadata.provider_code)
        self.assertEqual("AAPL", disclosures[0].security_id)
        self.assertEqual("10-Q", disclosures[0].disclosure_type)
        self.assertIn("Quarterly report", disclosures[0].title)
        self.assertEqual("0000320193-26-000010", disclosures[0].provider_event_id)
        self.assertIn(
            "https://www.sec.gov/Archives/edgar/data/320193/000032019326000010/",
            disclosures[0].source_url,
        )
        self.assertEqual(
            "https://data.sec.gov/submissions/CIK0000320193.json",
            calls[0][0],
        )
        self.assertEqual("Silver Platter dev@example.com", calls[0][1]["User-Agent"])

    def test_default_json_fetcher_decodes_gzip_payload(self):
        class FakeResponse:
            headers = {"Content-Encoding": "gzip"}

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def read(self):
                return gzip.compress(b'{"ok": true}')

        with patch("silver_platter.providers.urllib.request.urlopen", return_value=FakeResponse()):
            payload = _default_json_fetcher("https://example.test", {})

        self.assertTrue(payload["ok"])
