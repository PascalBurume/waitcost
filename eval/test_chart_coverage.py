"""Gate: every benchmark question must yield a render-ready graphic (or be a
no-chart decline). Proves the viz path holds for ALL question types, not just the
demo five. Builds each distinct chart once (small Monte Carlo) to stay fast.
"""
from eval import chart_coverage as cc


def test_every_question_yields_a_buildable_chart():
    r = cc.sweep(n_mc=12)
    fails = [(q, intent, chart, err) for (q, intent, chart, ok, err) in r["rows"] if not ok]
    assert not fails, f"{len(fails)} questions produced no valid chart: {fails[:5]}"


def test_chart_specs_are_json_serializable_and_nonempty():
    import json
    from analysis.viz import VizAgent, CHART_CATALOG
    va = VizAgent()
    for c in CHART_CATALOG:
        spec = va.build(c["name"], coc="CA-600", n_mc=12)
        assert spec["series"], c["name"]
        json.dumps(spec)


def test_city_brief_intents_map_to_a_real_chart():
    from analysis.viz import VizAgent, _BUILDERS
    va = VizAgent()
    for intent in ("city_situation", "care_plan", "city_context"):
        chart = va.recommend(intent)
        assert chart in _BUILDERS, (intent, chart)
