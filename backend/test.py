from workflows.nodes.agents import historian_node, dreamer_node

# Test Historian Agent
state = {
    "scenario_id": "rome",
    "current_year": 630,
    "years_to_progress": 20,
    "rulers": {"BYZ": {"name": "Heraclius", "title": "Emperor", "age": 56, "dynasty": "Heraclian"}}
}
print("=== Testing Historian Agent ===")
historian_result = historian_node(state)
print(historian_result)

# Test Dreamer Agent
print("\n=== Testing Dreamer Agent ===")
state.update({
    "historian_output": historian_result["historian_output"],
    "divergences": ["Sassanid Empire collapsed 10 years earlier due to internal rebellion"],
    "condensed_logs": "",
    "logs": [{
        "year_range": "-630 AD",
        "narrative": "The Byzantine Empire under Heraclius has just concluded a devastating war with Persia. However, in this timeline, the Sassanid Empire collapsed earlier due to internal strife, leaving Byzantium less exhausted.",
        "divergences": ["Sassanid Empire collapsed 10 years earlier due to internal rebellion"],
        "territorial_changes_summary": "At 630 AD, the Byzantine Empire controls its traditional eastern territories including Egypt, Syria, Palestine, and Anatolia. The former Sassanid territories are in chaos with no central authority."
    }]
})
dreamer_result = dreamer_node(state)
print(dreamer_result)

# Show what tags are used
print("\n=== Rulers in response (should only be ROM, BYZ, or ROW) ===")
print(list(dreamer_result["dreamer_output"]["rulers"].keys()))
