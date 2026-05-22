-- 004_seed_policy
INSERT INTO SP.data_provider (provider_code, provider_name, provider_type, base_url, auth_type)
SELECT 'krx', 'KRX', 'market_data', NULL, 'none'
WHERE NOT EXISTS (SELECT 1 FROM SP.data_provider WHERE provider_code = 'krx');

INSERT INTO SP.data_provider (provider_code, provider_name, provider_type, base_url, auth_type)
SELECT 'opendart', 'OpenDART', 'disclosure', 'https://opendart.fss.or.kr', 'api_key'
WHERE NOT EXISTS (SELECT 1 FROM SP.data_provider WHERE provider_code = 'opendart');

INSERT INTO SP.data_provider (provider_code, provider_name, provider_type, base_url, auth_type)
SELECT 'sec_edgar', 'SEC EDGAR', 'disclosure', 'https://data.sec.gov', 'user_agent'
WHERE NOT EXISTS (SELECT 1 FROM SP.data_provider WHERE provider_code = 'sec_edgar');

INSERT INTO SP.data_provider (provider_code, provider_name, provider_type, base_url, auth_type)
SELECT 'korea_investment', 'Korea Investment Open API', 'broker', NULL, 'oauth'
WHERE NOT EXISTS (SELECT 1 FROM SP.data_provider WHERE provider_code = 'korea_investment');

INSERT INTO SP.risk_limit (limit_code, scope_type, warning_value, block_value, stop_value, unit)
SELECT 'single_security_weight', 'security', 0.05, 0.10, NULL, 'ratio'
WHERE NOT EXISTS (SELECT 1 FROM SP.risk_limit WHERE limit_code = 'single_security_weight');

INSERT INTO SP.risk_limit (limit_code, scope_type, warning_value, block_value, stop_value, unit)
SELECT 'sector_weight', 'sector', 0.25, 0.35, NULL, 'ratio'
WHERE NOT EXISTS (SELECT 1 FROM SP.risk_limit WHERE limit_code = 'sector_weight');

INSERT INTO SP.risk_limit (limit_code, scope_type, warning_value, block_value, stop_value, unit)
SELECT 'business_group_weight', 'business_group', 0.20, 0.30, NULL, 'ratio'
WHERE NOT EXISTS (SELECT 1 FROM SP.risk_limit WHERE limit_code = 'business_group_weight');

INSERT INTO SP.risk_limit (limit_code, scope_type, warning_value, block_value, stop_value, unit)
SELECT 'daily_loss', 'portfolio', -0.01, -0.02, -0.03, 'ratio'
WHERE NOT EXISTS (SELECT 1 FROM SP.risk_limit WHERE limit_code = 'daily_loss');

INSERT INTO SP.risk_limit (limit_code, scope_type, warning_value, block_value, stop_value, unit)
SELECT 'mdd', 'portfolio', -0.08, -0.12, -0.15, 'ratio'
WHERE NOT EXISTS (SELECT 1 FROM SP.risk_limit WHERE limit_code = 'mdd');

INSERT INTO SP.risk_limit (limit_code, scope_type, warning_value, block_value, stop_value, unit)
SELECT 'order_to_adv20', 'security', NULL, 0.05, NULL, 'ratio'
WHERE NOT EXISTS (SELECT 1 FROM SP.risk_limit WHERE limit_code = 'order_to_adv20');

INSERT INTO SP.risk_limit (limit_code, scope_type, warning_value, block_value, stop_value, unit)
SELECT 'group_order_to_adv20', 'business_group', NULL, 0.05, NULL, 'ratio'
WHERE NOT EXISTS (SELECT 1 FROM SP.risk_limit WHERE limit_code = 'group_order_to_adv20');

INSERT INTO SP.slippage_rule (market_code, order_type, base_slippage_bps, low_liquidity_multiplier)
SELECT 'KR', 'market', 10, 3
WHERE NOT EXISTS (SELECT 1 FROM SP.slippage_rule WHERE market_code = 'KR' AND order_type = 'market');

INSERT INTO SP.slippage_rule (market_code, order_type, base_slippage_bps, low_liquidity_multiplier)
SELECT 'KR', 'limit', 5, 3
WHERE NOT EXISTS (SELECT 1 FROM SP.slippage_rule WHERE market_code = 'KR' AND order_type = 'limit');

INSERT INTO SP.slippage_rule (market_code, order_type, base_slippage_bps, low_liquidity_multiplier)
SELECT 'US', 'market', 8, 3
WHERE NOT EXISTS (SELECT 1 FROM SP.slippage_rule WHERE market_code = 'US' AND order_type = 'market');

INSERT INTO SP.slippage_rule (market_code, order_type, base_slippage_bps, low_liquidity_multiplier)
SELECT 'US', 'limit', 4, 3
WHERE NOT EXISTS (SELECT 1 FROM SP.slippage_rule WHERE market_code = 'US' AND order_type = 'limit');

INSERT INTO SP.db_backup_policy (
    policy_code,
    schedule_cron,
    timezone,
    base_path,
    retention_days,
    encryption_type
)
SELECT
    'weekly_goldilocks_full_backup',
    '0 10 * * 6',
    'Asia/Seoul',
    '/home/jhkim5/backup_sp',
    NULL,
    'none'
WHERE NOT EXISTS (
    SELECT 1 FROM SP.db_backup_policy
    WHERE policy_code = 'weekly_goldilocks_full_backup'
);
