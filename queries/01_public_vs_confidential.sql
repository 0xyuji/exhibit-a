-- Daily NEAR Intents volume, split into public and confidential.
-- Source table is maintained by NEAR. This is the core of NEAR's own saved query:
-- https://dune.com/queries/5179085  (its saved result is what data/confidential.csv was read from)
select
  date_at,
  sum(cast(volume_amount_usd as double))                                                       as volume_usd,
  sum(case when source_type = 'public'       then cast(volume_amount_usd as double) end)       as public_volume_usd,
  sum(case when source_type = 'confidential' then cast(volume_amount_usd as double) end)       as confidential_volume_usd
from dune.near.dataset_near_intents_metrics
group by date_at
order by date_at desc
