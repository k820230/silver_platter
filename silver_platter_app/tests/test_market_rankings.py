from unittest import TestCase
from unittest.mock import patch

from silver_platter.broker import KoreaInvestmentCredentials
from silver_platter.market_rankings import KoreaInvestmentVolumeRankingProvider


class FakeRankingTransport:
    def __init__(self):
        self.posts = []
        self.gets = []

    def post(self, path, headers, body):
        self.posts.append((path, headers, body))
        return {"access_token": "token-1"}

    def get(self, path, headers, params):
        self.gets.append((path, headers, params))
        if path.endswith("/volume-rank"):
            return {
                "output": [
                    {
                        "data_rank": "2",
                        "mksc_shrn_iscd": "000660",
                        "hts_kor_isnm": "SK하이닉스",
                        "stck_prpr": "201000",
                        "prdy_ctrt": "1.2",
                        "acml_vol": "12,000",
                        "acml_tr_pbmn": "2412000000",
                    },
                    {
                        "data_rank": "1",
                        "mksc_shrn_iscd": "005930",
                        "hts_kor_isnm": "삼성전자",
                        "stck_prpr": "70100",
                        "prdy_ctrt": "-0.3",
                        "acml_vol": "42,000",
                        "acml_tr_pbmn": "2944200000",
                    },
                ]
            }
        return {
            "output2": [
                {
                    "rank": "1",
                    "excd": params["EXCD"],
                    "symb": "%s1" % params["EXCD"],
                    "name": "%s leader" % params["EXCD"],
                    "last": "100.5",
                    "rate": "2.4",
                    "tvol": "1000",
                    "tamt": "100500",
                }
            ]
        }


class MarketRankingTests(TestCase):
    def test_kis_domestic_volume_leaders_normalize_and_rank_by_volume(self):
        transport = FakeRankingTransport()
        provider = KoreaInvestmentVolumeRankingProvider(
            KoreaInvestmentCredentials("app", "secret", "12345678"),
            transport,
        )

        with patch.dict("os.environ", {"KIS_REQUEST_SLEEP_SECONDS": "0"}):
            leaders = provider.domestic_volume_leaders(limit=2)

        self.assertEqual(["005930", "000660"], [item.symbol for item in leaders])
        self.assertEqual([1, 2], [item.rank for item in leaders])
        self.assertEqual("삼성전자", leaders[0].name)
        self.assertEqual(42000.0, leaders[0].volume)
        self.assertEqual("FHPST01710000", transport.gets[0][1]["tr_id"])
        self.assertEqual("J", transport.gets[0][2]["FID_COND_MRKT_DIV_CODE"])

    def test_kis_us_volume_leaders_merge_us_exchanges(self):
        transport = FakeRankingTransport()
        provider = KoreaInvestmentVolumeRankingProvider(
            KoreaInvestmentCredentials("app", "secret", "12345678"),
            transport,
        )

        with patch.dict("os.environ", {"KIS_REQUEST_SLEEP_SECONDS": "0"}):
            leaders = provider.us_volume_leaders(limit=2, exchanges=("NAS", "NYS", "AMS"))

        self.assertEqual(2, len(leaders))
        self.assertEqual(["NAS1", "NYS1"], [item.symbol for item in leaders])
        self.assertEqual("HHDFS76310010", transport.gets[0][1]["tr_id"])
        self.assertEqual(
            "/uapi/overseas-stock/v1/ranking/trade-vol",
            transport.gets[0][0],
        )
