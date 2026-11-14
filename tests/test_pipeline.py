"""Checks of the counting rules and the model. Run:  python3 -m unittest discover tests"""
import unittest

from pipeline import assemble, model, official, swaps

BTC, ZEC, USDC, USDT, ETH, USDC_ARB = "btc", "zec", "usdc", "usdt", "eth", "usdc-arb"
swaps._tokens.update({
    BTC: {"symbol": "BTC", "same": "bitcoin"},
    ZEC: {"symbol": "ZEC", "same": "zcash"},
    USDC: {"symbol": "USDC", "same": "usd-coin"},
    USDC_ARB: {"symbol": "USDC", "same": "usd-coin"},
    USDT: {"symbol": "USDT", "same": "tether"},
    ETH: {"symbol": "ETH", "same": "ethereum"},
})


def swap(a, b, usd, fees=(), status="SUCCESS", referral="app", out=None):
    return {
        "status": status, "originAsset": a, "destinationAsset": b, "referral": referral,
        "amountInUsd": str(usd), "amountOutUsd": str(usd if out is None else out),
        "appFees": [{"recipient": r, "fee": bps} for r, bps in fees], "refundReason": None,
    }


class Counting(unittest.TestCase):
    def day(self, *records):
        totals = swaps.Day()
        for record in records:
            totals.add(record)
        return totals.result()

    def test_fee_is_basis_points_of_the_dollars_in(self):
        got = self.day(swap(BTC, USDC, 1000, [("partner.near", 75)]))
        self.assertAlmostEqual(got["fees"], 7.5)
        self.assertAlmostEqual(got["volume"], 1000)

    def test_only_near_wallets_count_as_named_to_near(self):
        got = self.day(swap(ETH, USDC, 2000, [("buybacks.multisignature.near", 5), ("lifi_int.near", 5)]))
        self.assertAlmostEqual(got["fees"], 2.0)
        self.assertAlmostEqual(got["fees_to_near"], 1.0)
        self.assertAlmostEqual(got["front_ends"]["app"]["fees_to_near"], 1.0)

    def test_groups(self):
        got = self.day(
            swap(USDC, USDT, 100),          # both sides stable
            swap(USDC, USDC_ARB, 100),      # the same stablecoin on two chains is still a stable pair
            swap(BTC, ZEC, 100),            # Bitcoin wins over Zcash
            swap(ZEC, USDC, 100),
            swap(ETH, USDC, 100),
        )
        self.assertEqual(got["kind"]["Stablecoin pair"]["swaps"], 2)
        self.assertEqual(got["kind"]["Bitcoin"]["swaps"], 1)
        self.assertEqual(got["kind"]["Zcash"]["swaps"], 1)
        self.assertEqual(got["kind"]["Everything else"]["swaps"], 1)
        self.assertAlmostEqual(sum(k["volume"] for k in got["kind"].values()), got["volume"])

    def test_failed_and_refunded_swaps_carry_no_volume(self):
        got = self.day(swap(BTC, USDC, 500, status="REFUNDED"), swap(BTC, USDC, 500, status="FAILED"), swap(BTC, USDC, 500))
        self.assertEqual(got["swaps"], 3)
        self.assertEqual(got["status"], {"REFUNDED": 1, "FAILED": 1, "SUCCESS": 1})
        self.assertAlmostEqual(got["volume"], 500)

    def test_a_swap_with_no_app_fee_is_counted_as_unpaid(self):
        got = self.day(swap(ETH, USDC, 300), swap(ETH, USDC, 700, [("partner.near", 10)]))
        self.assertAlmostEqual(got["no_fee_volume"], 300)

    def test_size_buckets_hold_every_swap(self):
        got = self.day(swap(ETH, USDC, 0.5), swap(ETH, USDC, 50), swap(ETH, USDC, 250000))
        self.assertEqual(sum(count for count, _ in got["sizes"]), 3)
        self.assertEqual(got["sizes"][0][0], 1)
        self.assertEqual(got["sizes"][-1][0], 1)

    def test_days_add_up(self):
        one = self.day(swap(BTC, USDC, 100, [("partner.near", 50)]))
        two = self.day(swap(BTC, USDC, 300, [("partner.near", 50)]), swap(ZEC, USDC, 100))
        both = assemble.merged([one, two])
        self.assertAlmostEqual(both["volume"], 500)
        self.assertAlmostEqual(both["fees"], 2.0)
        self.assertEqual(both["kind"]["Bitcoin"]["swaps"], 2)
        self.assertEqual(sum(count for count, _ in both["sizes"]), 3)


class Official(unittest.TestCase):
    def test_confidential_volume_is_added_before_the_change_and_not_after(self):
        volumes, last = official.split({"2026-08-15": 31_744_839.0, "2026-09-15": 131_467_577.0})
        before, after = volumes["2026-08-15"], volumes["2026-09-15"]
        self.assertAlmostEqual(before["public"], 31_744_839.0)
        self.assertAlmostEqual(before["total"], before["public"] + before["confidential"])
        self.assertAlmostEqual(after["total"], 131_467_577.0)
        self.assertAlmostEqual(after["public"] + after["confidential"], after["total"])
        self.assertGreater(before["confidential"], 0)

    def test_days_after_the_last_split_reading_are_marked_unknown(self):
        volumes, last = official.split({last_day: 1.0 for last_day in ("2026-11-12", "2099-01-01")})
        self.assertIsNotNone(volumes[last]["confidential"])
        self.assertIsNone(volumes["2099-01-01"]["confidential"])
        self.assertEqual(volumes["2099-01-01"]["total"], 1.0)


class Model(unittest.TestCase):
    inputs = {"days": 30, "partner_fees": 5_000_000, "fees_to_near": 400_000, "revenue": 1_800_000,
              "rest_volume": 2_700_000_000, "supply": 1_300_000_000, "max_inflation": 0.025, "price": 3.0}

    def test_today_reproduces_measured_revenue(self):
        self.assertAlmostEqual(model.run(self.inputs)["revenue"], 1_800_000)

    def test_published_half(self):
        self.assertAlmostEqual(model.run(self.inputs, cut=0.5)["revenue"], 1_800_000 - 400_000 + 2_500_000)

    def test_one_basis_point_on_the_rest(self):
        self.assertAlmostEqual(model.run(self.inputs, rest_bps=1)["revenue"], 1_800_000 + 270_000)

    def test_issuance(self):
        self.assertAlmostEqual(model.run(self.inputs)["issuance"], 1_300_000_000 * 0.025 * 30 / 365 * 3.0)

    def test_measured_issuance_replaces_the_setting(self):
        measured = dict(self.inputs, issued_near=2_000_000)
        self.assertAlmostEqual(model.run(measured)["issuance"], 6_000_000)

    def test_the_lower_cap_scales_issuance(self):
        self.assertAlmostEqual(model.run(self.inputs, cap=0.016)["issuance"], model.run(self.inputs)["issuance"] * 0.016 / 0.025)

    def test_losing_an_integrator_removes_its_fees_and_only_what_named_near(self):
        gone = model.run(self.inputs, lost_fees=3_000_000, lost_to_near=0)
        self.assertAlmostEqual(gone["partner_fees"], 2_000_000)
        self.assertAlmostEqual(gone["revenue"], 1_800_000)
        half = model.run(self.inputs, cut=0.5, lost_fees=3_000_000)
        self.assertAlmostEqual(half["revenue"], 1_800_000 - 400_000 + 1_000_000)

    def test_multiple_is_supply_at_price_over_a_year_of_revenue(self):
        got = model.run(self.inputs)
        self.assertAlmostEqual(got["multiple"], 1_300_000_000 * 3.0 / (1_800_000 * 365 / 30))

    def test_breakeven(self):
        even = model.breakeven(self.inputs)
        issued = model.run(self.inputs)["issuance"]
        self.assertAlmostEqual(model.run(self.inputs, cut=even["cut"])["revenue"], issued)
        self.assertAlmostEqual(model.run(self.inputs, cut=0.5, growth=even["growth_at_half"])["revenue"], issued)


class ChainHistory(unittest.TestCase):
    saved = {"tokens": [["wrap.near", "wNEAR (near)", 24, 3.0]], "days": {
        "2026-01-01": {"wallets": {"a": 100.0}, "state_bytes": 1000, "supply": 5000.0, "holdings": {"wrap.near": 10.0}},
        "2026-01-02": {"wallets": {"a": 130.0}, "state_bytes": 1500, "supply": 5040.0, "holdings": {"wrap.near": 12.0}},
        "2026-01-03": {"wallets": {"a": 150.0}, "state_bytes": 1900, "supply": 5100.0, "holdings": {"wrap.near": 11.0}},
    }}

    def test_daily_changes_and_window_totals(self):
        got = assemble.chain_history(self.saved, ["2026-01-02", "2026-01-03"])
        self.assertEqual([row.get("inflow") for row in got["days"]], [None, 30.0, 20.0])
        self.assertAlmostEqual(got["inflow_window"], 50.0)
        self.assertAlmostEqual(got["issued_window"], 100.0)
        self.assertEqual(got["state_growth_window"], 900)
        self.assertAlmostEqual(got["holdings_usd"], 33.0)

    def test_a_window_with_missing_days_gives_no_total(self):
        got = assemble.chain_history(self.saved, ["2026-01-03", "2026-01-04"])
        self.assertIsNone(got["inflow_window"])


class History(unittest.TestCase):
    def test_history_stops_before_the_window(self):
        days = assemble.history_days("2026-10-14")
        self.assertEqual(days[0], "2025-06-05")
        self.assertEqual(days[-1], "2026-10-05")
        self.assertTrue(all(day < "2026-10-14" for day in days))


class Recipients(unittest.TestCase):
    def test_addresses_and_small_recipients_are_folded_into_others(self):
        from pipeline import swaps
        fees = {"partner.near": 900.0, "0x" + "ab" * 20: 60.0, "f" * 64: 30.0, "tiny.near": 1.0,
                "buybacks.multisignature.near": 2.0, "(others)": 7.0}
        kept = swaps.named_recipients(fees)
        self.assertEqual(set(kept), {"partner.near", "buybacks.multisignature.near", "(others)"})
        self.assertAlmostEqual(sum(kept.values()), 1000.0)
        self.assertAlmostEqual(kept["(others)"], 98.0)


if __name__ == "__main__":
    unittest.main()
