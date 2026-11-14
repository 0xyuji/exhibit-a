-- NEAR arriving in the three revenue wallets per day, straight from chain tables:
-- native transfers plus wrapped NEAR. The build reads the same thing from an archive node
-- (pipeline/history.py); this is the SQL form.
-- Adapted from a third party's saved query: https://dune.com/queries/6740088
-- NOT RUN BY US: our Dune account is read-only. Paste it into dune.com to run it.
with wallets as (
  select wallet from (values
    ('fefundsadmin.sputnik-dao.near'),
    ('1csfundsadmin.sputnik-dao.near'),
    ('buybacks.multisignature.near')
  ) as t(wallet)
),
native as (
  select
    date_trunc('day', block_time)                          as day,
    receipt_receiver_account_id                            as wallet,
    sum(cast(action_transfer_deposit as double) / 1e24)    as near_in
  from near.actions
  where block_date >= date '2026-08-01'
    and action_kind = 'TRANSFER'
    and execution_status = 'SUCCESS_VALUE'
    and receipt_receiver_account_id in (select wallet from wallets)
  group by 1, 2
),
wrapped as (
  select
    date_trunc('day', block_time)                as day,
    affected_account_id                          as wallet,
    sum(cast(delta_amount as double) / 1e24)     as near_in
  from near.ft_transfers
  where block_date >= date '2026-08-01'
    and contract_account_id = 'wrap.near'
    and delta_amount > 0
    and affected_account_id in (select wallet from wallets)
  group by 1, 2
)
select day, wallet, sum(near_in) as near_in
from (select * from native union all select * from wrapped) t
group by 1, 2
order by 1 desc, 2
