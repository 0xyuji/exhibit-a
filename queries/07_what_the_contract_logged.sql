-- An independent look at the switch to confidential settlement: how many events of each kind
-- the intents contract logged per day. If swaps moved off the public ledger in early November
-- 2026, the public swap events (dip4 / token_diff) should fall away while volume holds.
-- NOT RUN BY US: our Dune account is read-only, and the public block feed rate-limited our own
-- sampler (an earlier block sampler, since removed). Paste it into dune.com to run it.
select
  block_date,
  json_extract_scalar(event, '$.standard')   as standard,
  json_extract_scalar(event, '$.event')      as event,
  count(*)                                    as events
from near.logs
where executor_account_id = 'intents.near'
  and block_date >= date '2026-10-01'
  and event is not null
group by 1, 2, 3
order by 1 desc, events desc
