-- What the protocol's own fee earns next to what front-ends charge, per day.
-- Adapted from a third party's saved query: https://dune.com/queries/9074851
-- (its saved result gave the protocol-fee figure in data/notes.json)
with protocol as (
  select cast(substr(cast(date_at as varchar), 1, 10) as date) as day, sum(cast(amount_fee as double)) as protocol_usd
  from dune.near.dataset_near_intents_protocol_fees
  group by 1
),
affiliate as (
  select cast(substr(cast(date_at as varchar), 1, 10) as date) as day, sum(cast(fee as double)) as affiliate_usd
  from dune.near.dataset_near_intents_fees
  group by 1
)
select
  coalesce(p.day, a.day)          as day,
  coalesce(p.protocol_usd, 0)     as protocol_fee_usd,
  coalesce(a.affiliate_usd, 0)    as affiliate_fee_usd
from protocol p
full outer join affiliate a on a.day = p.day
where coalesce(p.day, a.day) >= current_date - interval '90' day
order by 1 desc
