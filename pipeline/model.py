"""The model: how much of NEAR's new issuance its Intents revenue could buy back.

Everything is per window (30 days). Inputs are measured by the build; the levers are
assumptions the reader sets. The page runs the same sum in the browser.

    revenue  = (revenue_now - cut_now * partner_fees) * growth  # what NEAR earns outside partner fees
             + cut * partner_fees * growth                      # its share of what partners charge
             + rest_bps / 10000 * rest_volume * growth          # an extra fee on swap value outside the partner API
    issuance = NEAR issued in the window * price                # measured from total supply when the
                                                                # chain history is there, else the setting
    covered  = revenue / issuance

Run it yourself, after a build:

    python3 -m pipeline.model                        # the scenarios
    python3 -m pipeline.model --cut 0.5 --growth 2   # your own levers
"""
import argparse
import json
import os


# House of Stake proposal HSP-029 (passed 2 November 2026) lowers the cap from 2.5% to 1.6% over 24 months.
CAP_AFTER_HSP_029 = 0.016


def issuance(inputs, cap=None):
    """Dollars of new NEAR in the window. `cap` rescales it to another maximum issuance rate."""
    issued = inputs.get("issued_near") or inputs["supply"] * inputs["max_inflation"] * inputs["days"] / 365
    if cap is not None:
        issued *= cap / inputs["max_inflation"]
    return issued * inputs["price"]


def run(inputs, cut=None, rest_bps=0.0, growth=1.0, lost_fees=0.0, lost_to_near=0.0, cap=None):
    """lost_fees / lost_to_near: partner fees (and the part of them named to NEAR) that go away."""
    fees = inputs["partner_fees"] - lost_fees
    named = inputs["fees_to_near"] - lost_to_near
    cut_now = inputs["fees_to_near"] / inputs["partner_fees"]
    outside = inputs["revenue"] - inputs["fees_to_near"]
    share = cut_now if cut is None else cut
    partner = named if cut is None else share * fees
    revenue = outside * growth + partner * growth + rest_bps / 1e4 * inputs["rest_volume"] * growth
    issued = issuance(inputs, cap)
    return {
        "cut": share,
        "rest_bps": rest_bps,
        "growth": growth,
        "partner_fees": fees * growth,
        "revenue": revenue,
        "revenue_year": revenue * 365 / inputs["days"],
        "issuance": issued,
        "covered": revenue / issued,
        # every NEAR in existence at today's price, over a year of this revenue
        "multiple": inputs["supply"] * inputs["price"] / (revenue * 365 / inputs["days"]) if revenue > 0 else None,
    }


def breakeven(inputs):
    """What it would take for revenue to match issuance."""
    issued = issuance(inputs)
    outside = inputs["revenue"] - inputs["fees_to_near"]
    cut = (issued - outside) / inputs["partner_fees"]           # NEAR's share of partner fees, volume as today
    growth_now = issued / inputs["revenue"]                      # volume multiple, cut as today
    growth_half = issued / (outside + 0.5 * inputs["partner_fees"])  # volume multiple at the published half
    return {"cut": cut, "growth_at_todays_cut": growth_now, "growth_at_half": growth_half}


def scenarios(inputs):
    rows = [
        ("Today", {}),
        ("NEAR takes its published half of partner fees", {"cut": 0.5}),
        ("Swaps outside the partner API pay 1 bp more", {"rest_bps": 1}),
        ("Swaps outside the partner API pay 5 bps more", {"rest_bps": 5}),
        ("Published half, and volume triples", {"cut": 0.5, "growth": 3}),
        ("Nothing changes but volume halves", {"growth": 0.5}),
        ("Issuance at the 1.6% cap already voted in", {"cap": CAP_AFTER_HSP_029}),
        ("Published half, at the 1.6% cap", {"cut": 0.5, "cap": CAP_AFTER_HSP_029}),
    ]
    out = [dict(run(inputs, **levers), name=name) for name, levers in rows]
    top = inputs.get("top_front")
    if top:
        out.append(dict(run(inputs, lost_fees=top["fees"], lost_to_near=top["to_near"]),
                        name=f"The largest integrator ({ {'swapkit': 'SwapKit', 'lifi': 'LI.FI'}.get(top['name'], top['name']) }) leaves"))
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cut", type=float, help="NEAR's share of partner fees, 0 to 1")
    parser.add_argument("--rest-bps", type=float, default=0.0, help="extra fee, in bps, on swap value outside the partner API")
    parser.add_argument("--growth", type=float, default=1.0, help="volume against today")
    parser.add_argument("--cap", type=float, help="maximum issuance rate, e.g. 0.016")
    args = parser.parse_args()
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "data.json")
    inputs = json.load(open(path))["model"]["inputs"]
    custom = any(value is not None and value != default for value, default in ((args.cut, None), (args.rest_bps, 0.0), (args.growth, 1.0), (args.cap, None)))
    rows = [dict(run(inputs, cut=args.cut, rest_bps=args.rest_bps, growth=args.growth, cap=args.cap), name="Your levers")] if custom else scenarios(inputs)
    for row in rows:
        print(f"{row['name']:<52} revenue ${row['revenue']:>12,.0f}   a year ${row['revenue_year']:>13,.0f}   covers {row['covered']:6.1%} of issuance   {row['multiple']:5.0f}x revenue")
    even = breakeven(inputs)
    print(f"\nTo match issuance: NEAR's share of partner fees would need to be {even['cut']:.0%} at today's volume,")
    print(f"or volume {even['growth_at_half']:.1f}x at the published half, or {even['growth_at_todays_cut']:.1f}x at today's cut.")


if __name__ == "__main__":
    main()
