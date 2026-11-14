-- Daily volume per chain. A next step for "who is behind the dollars that pay nothing":
-- on the days we looked, most of the official volume touched Ethereum or Tron.
-- NEAR's own saved query: https://dune.com/queries/5157565
select
  date_at,
  upper(blockchain)                         as blockchain,
  sum(cast(volume_amount_usd as double))    as volume_usd
from dune.near.dataset_near_intents_metrics
group by 1, 2
having sum(cast(volume_amount_usd as double)) > 0
order by date_at desc, volume_usd desc
