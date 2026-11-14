-- Daily volume per token. A swap appears under both of its tokens, so the sum over tokens
-- counts every swap twice. Compare with partner swaps that touch each token (pipeline/swaps.py).
-- NEAR's own saved query: https://dune.com/queries/5157527  (data/official_tokens.csv was read from it)
select
  date_at,
  symbol,
  sum(cast(volume_amount_usd as double)) as volume_usd
from dune.near.dataset_near_intents_metrics
group by date_at, symbol
having sum(cast(volume_amount_usd as double)) > 0
order by date_at desc, volume_usd desc
