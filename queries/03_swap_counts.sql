-- Daily number of swaps, counted per token like the volume.
-- NEAR's own saved query: https://dune.com/queries/4374089  (data/official_swaps.csv was read from it)
select
  date_at,
  sum(cast(swaps_amount as integer)) as total_swaps
from dune.near.dataset_near_intents_metrics
where date_at >= '2024-12-10'
group by date_at
order by date_at desc
