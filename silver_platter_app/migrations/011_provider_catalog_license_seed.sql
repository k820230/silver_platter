-- 011_provider_catalog_license_seed
INSERT INTO SP.data_provider (provider_code, provider_name, provider_type, base_url, auth_type)
SELECT 'krx_free', 'KRX Free Reference Data', 'reference_data', 'https://data.krx.co.kr', 'none'
WHERE NOT EXISTS (SELECT 1 FROM SP.data_provider WHERE provider_code = 'krx_free');

INSERT INTO SP.data_provider (provider_code, provider_name, provider_type, base_url, auth_type)
SELECT 'krx_data', 'KRX Data Marketplace Daily Price', 'market_data', 'https://data.krx.co.kr', 'none'
WHERE NOT EXISTS (SELECT 1 FROM SP.data_provider WHERE provider_code = 'krx_data');

INSERT INTO SP.data_provider (provider_code, provider_name, provider_type, base_url, auth_type)
SELECT 'krx_kind', 'KRX KIND Disclosure', 'disclosure', 'https://kind.krx.co.kr', 'none'
WHERE NOT EXISTS (SELECT 1 FROM SP.data_provider WHERE provider_code = 'krx_kind');

INSERT INTO SP.data_provider (provider_code, provider_name, provider_type, base_url, auth_type)
SELECT 'ecos_bok', 'Bank of Korea ECOS FX', 'fx', 'https://ecos.bok.or.kr/api', 'api_key'
WHERE NOT EXISTS (SELECT 1 FROM SP.data_provider WHERE provider_code = 'ecos_bok');

INSERT INTO SP.data_provider (provider_code, provider_name, provider_type, base_url, auth_type)
SELECT 'federal_reserve', 'Federal Reserve RSS', 'headline', 'https://www.federalreserve.gov/feeds', 'none'
WHERE NOT EXISTS (SELECT 1 FROM SP.data_provider WHERE provider_code = 'federal_reserve');

INSERT INTO SP.data_provider (provider_code, provider_name, provider_type, base_url, auth_type)
SELECT 'ecb', 'European Central Bank RSS', 'headline', 'https://www.ecb.europa.eu/rss', 'none'
WHERE NOT EXISTS (SELECT 1 FROM SP.data_provider WHERE provider_code = 'ecb');

INSERT INTO SP.data_provider (provider_code, provider_name, provider_type, base_url, auth_type)
SELECT 'ofac', 'OFAC Recent Actions', 'headline', 'https://ofac.treasury.gov/recent-actions', 'none'
WHERE NOT EXISTS (SELECT 1 FROM SP.data_provider WHERE provider_code = 'ofac');

INSERT INTO SP.data_provider (provider_code, provider_name, provider_type, base_url, auth_type)
SELECT 'free_fx_placeholder', 'Free FX Placeholder', 'fx', NULL, 'none'
WHERE NOT EXISTS (SELECT 1 FROM SP.data_provider WHERE provider_code = 'free_fx_placeholder');

INSERT INTO SP.data_license (
    provider_id,
    license_name,
    can_store,
    can_transform,
    can_display_realtime,
    can_redistribute
)
SELECT
    p.provider_id,
    p.provider_code || '_mvp_policy',
    TRUE,
    TRUE,
    FALSE,
    FALSE
FROM SP.data_provider p
WHERE p.provider_code IN (
    'krx',
    'krx_free',
    'krx_data',
    'opendart',
    'krx_kind',
    'sec_edgar',
    'ecos_bok',
    'federal_reserve',
    'ecb',
    'ofac',
    'free_fx_placeholder'
)
AND NOT EXISTS (
    SELECT 1 FROM SP.data_license l
    WHERE l.provider_id = p.provider_id
      AND l.license_name = p.provider_code || '_mvp_policy'
);
