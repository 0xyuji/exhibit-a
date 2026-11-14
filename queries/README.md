# Queries

SQL for Dune (dune.com), where NEAR publishes its own datasets and the raw NEAR chain tables live.
To run one: open Dune, start a new query, paste the file, run. A free account is enough.

| File | What it answers | Status |
|---|---|---|
| `01_public_vs_confidential.sql` | How much volume is confidential, per day | NEAR's own saved query ([5179085](https://dune.com/queries/5179085)); we read its saved result |
| `02_volume_by_token.sql` | Official volume per token, which shows it counts both sides of a swap | NEAR's own saved query ([5157527](https://dune.com/queries/5157527)); we read its saved result |
| `03_swap_counts.sql` | Official swap counts per day | NEAR's own saved query ([4374089](https://dune.com/queries/4374089)); we read its saved result |
| `04_fees_by_referral.sql` | Which front-ends the fees are attributed to, on NEAR's own fee table | Written by us, **not run** |
| `05_protocol_fee_vs_affiliate.sql` | What the protocol fee earns next to what front-ends charge | Adapted from a saved query ([9074851](https://dune.com/queries/9074851)) whose result we read |
| `06_revenue_wallet_inflows.sql` | NEAR arriving in the revenue wallets, from chain tables | Adapted from a saved query ([6740088](https://dune.com/queries/6740088)), **not run** by us; the build measures the same thing from an archive node |
| `07_what_the_contract_logged.sql` | Whether public swap events fell away when volume went confidential | Written by us, **not run** |
| `08_volume_by_chain.sql` | Which chains the volume sits on | NEAR's own saved query ([5157565](https://dune.com/queries/5157565)); not used in the thesis |

"Not run" is literal. The Dune account used for this project can read saved results but cannot
execute queries, so nothing in the thesis depends on a query we could not run. Where a file is
marked that way it is offered as the next thing to check, not as evidence.
