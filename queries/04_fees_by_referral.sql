-- Who the fees are attributed to, on NEAR's own fee table: the last 30 full days by referral.
-- This is the query that would settle how much NEAR keeps from each partner.
-- NOT RUN BY US: our Dune account is read-only. Paste it into dune.com to run it.
with fees as (
  select
    cast(substr(cast(date_at as varchar), 1, 10) as date) as day,
    lower(referral)                                        as referral,
    lower(source_type)                                     as source_type,
    cast(fee as double)                                    as fee_usd
  from dune.near.dataset_near_intents_fees
)
select
  referral,
  source_type,
  sum(fee_usd)                                   as fees_usd,
  sum(fee_usd) / sum(sum(fee_usd)) over ()       as share
from fees
where day >= current_date - interval '30' day
  and day <  current_date
group by 1, 2
order by fees_usd desc
