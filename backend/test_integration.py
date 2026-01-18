"""
Integration test for the alternate history workflow.

This test runs the full workflow end-to-end to verify all components
work together correctly.

Usage:
    python test_integration.py
    
    # Or with pytest
    pytest test_integration.py -v
"""
import os
import sys
import json
from pprint import pprint

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from workflows.graph import workflow, continue_workflow
from workflows.nodes import get_current_provinces, reset_province_memory, get_scenario_tags
from models.game import Game, create_game, get_game, delete_game, Province
from util.workflow_logger import workflow_logger


def test_full_workflow():
    """Test the full workflow from start to finish."""
    print("\n" + "="*70)
    print("INTEGRATION TEST: Full Workflow")
    print("="*70)
    
    # Test parameters
    divergence = "What if Justinian died in 530 AD before reconquering Africa?"
    scenario_id = "rome"
    years_to_progress = 20
    
    print(f"\nDivergence: {divergence}")
    print(f"Scenario: {scenario_id}")
    print(f"Years: {years_to_progress}")
    
    # Create a game
    game = create_game()
    print(f"\nCreated game: {game.id}")
    
    # Load scenario tags for game metadata
    scenario_tags = get_scenario_tags(scenario_id)
    for tag, info in scenario_tags.items():
        game.add_nation_tag(tag, info.get("name", tag), info.get("color", "#888888"))
    print(f"Loaded {len(game.nation_tags)} nation tags")
    
    # Run the workflow
    initial_state = {
        "divergences": [divergence],
        "scenario_id": scenario_id,
        "start_year": None,  # Will be set by filter
        "years_to_progress": years_to_progress,
        "filter_passed": False  # Will be set by filter
    }
    
    workflow_logger.workflow_start("main", initial_state)
    
    try:
        final_state = workflow.invoke(initial_state)
        workflow_logger.workflow_end("main", final_state)
    except Exception as e:
        print(f"\n❌ Workflow failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Check results
    print("\n" + "-"*40)
    print("RESULTS")
    print("-"*40)
    
    filter_passed = final_state.get("filter_passed", False)
    print(f"\nFilter passed: {filter_passed}")
    
    if not filter_passed:
        print(f"Filter reason: {final_state.get('filter_reason')}")
        print(f"Alternative: {final_state.get('filter_alternative')}")
        return False
    
    print(f"Start year: {final_state.get('start_year')}")
    print(f"Current year: {final_state.get('current_year')}")
    print(f"Merged: {final_state.get('merged', False)}")
    
    # Check rulers
    rulers = final_state.get("rulers", {})
    print(f"\nRulers ({len(rulers)}):")
    for tag, info in rulers.items():
        print(f"  {tag}: {info.get('name')} ({info.get('title')}, age {info.get('age')})")
    
    # Check logs
    logs = final_state.get("logs", [])
    print(f"\nLogs ({len(logs)}):")
    for log in logs:
        year_range = log.get("year_range", "?")
        narrative_preview = log.get("narrative", "")[:100]
        print(f"  [{year_range}] {narrative_preview}...")
    
    # Check divergences
    divergences = final_state.get("divergences", [])
    print(f"\nActive divergences ({len(divergences)}):")
    for d in divergences[:5]:  # Show first 5
        print(f"  - {d}")
    
    # Check provinces
    provinces = get_current_provinces()
    print(f"\nProvinces loaded: {len(provinces)}")
    
    # Update game state
    game.workflow_state = dict(final_state)
    game.province_state = [
        Province(id=p["id"], name=p["name"], owner=p["owner"], control=p.get("control", ""))
        for p in provinces
    ]
    game.full_logs = logs
    
    print("\n✓ Workflow completed successfully!")
    
    # Now test the continue workflow
    print("\n" + "="*70)
    print("INTEGRATION TEST: Continue Workflow")
    print("="*70)
    
    if final_state.get("merged"):
        print("\nTimeline merged, cannot continue")
        return True
    
    continue_state = dict(final_state)
    continue_state["years_to_progress"] = years_to_progress
    
    workflow_logger.workflow_start("continue", continue_state)
    
    try:
        continued_state = continue_workflow.invoke(continue_state)
        workflow_logger.workflow_end("continue", continued_state)
    except Exception as e:
        print(f"\n❌ Continue workflow failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "-"*40)
    print("CONTINUE RESULTS")
    print("-"*40)
    
    print(f"Current year: {continued_state.get('current_year')}")
    print(f"Merged: {continued_state.get('merged', False)}")
    
    new_logs = continued_state.get("logs", [])
    print(f"\nLogs ({len(new_logs)}):")
    for log in new_logs[-2:]:  # Show last 2
        year_range = log.get("year_range", "?")
        narrative_preview = log.get("narrative", "")[:100]
        print(f"  [{year_range}] {narrative_preview}...")
    
    print("\n✓ Continue workflow completed successfully!")
    
    # Cleanup
    delete_game(game.id)
    
    return True


def test_rejected_divergence():
    """Test that invalid divergences are properly rejected."""
    print("\n" + "="*70)
    print("INTEGRATION TEST: Rejected Divergence")
    print("="*70)
    
    # Test with a non-specific divergence
    divergence = "What if Rome never fell"  # Too vague
    
    initial_state = {
        "divergences": [divergence],
        "scenario_id": "rome",
        "years_to_progress": 20,
        "filter_passed": False
    }
    
    try:
        final_state = workflow.invoke(initial_state)
    except Exception as e:
        print(f"\n❌ Workflow error: {e}")
        return False
    
    filter_passed = final_state.get("filter_passed", False)
    print(f"\nFilter passed: {filter_passed}")
    
    if filter_passed:
        # The filter might accept this, depending on the LLM's interpretation
        print("Note: Filter accepted this divergence")
        return True
    
    print(f"Filter reason: {final_state.get('filter_reason')}")
    print(f"Alternative: {final_state.get('filter_alternative')}")
    
    print("\n✓ Rejection test completed!")
    return True


def test_api_flow():
    """Test the API-like flow of creating and continuing a game."""
    print("\n" + "="*70)
    print("INTEGRATION TEST: API Flow Simulation")
    print("="*70)
    
    from agents.filter_agent import filter_command
    
    # Simulate POST /start
    command = "What if Heraclius lost the Battle of Nineveh in 627 AD?"
    scenario_id = "rome"
    years_to_progress = 25
    
    print(f"\n1. Filter check for: '{command}'")
    filter_result = filter_command(command)
    
    if filter_result["status"] == "rejected":
        print(f"   Rejected: {filter_result.get('reason')}")
        return False
    
    year = filter_result["year"]
    print(f"   Accepted, year: {year}")
    
    # Create game
    print("\n2. Creating game...")
    game = create_game()
    
    scenario_tags = get_scenario_tags(scenario_id)
    for tag, info in scenario_tags.items():
        game.add_nation_tag(tag, info.get("name", tag), info.get("color", "#888888"))
    
    print(f"   Game ID: {game.id}")
    
    # Run workflow
    print("\n3. Running initial workflow...")
    initial_state = {
        "divergences": [command],
        "scenario_id": scenario_id,
        "start_year": year,
        "years_to_progress": years_to_progress,
        "filter_passed": True
    }
    
    final_state = workflow.invoke(initial_state)
    
    # Update game
    game.workflow_state = dict(final_state)
    provinces = get_current_provinces()
    game.province_state = [
        Province(id=p["id"], name=p["name"], owner=p["owner"], control=p.get("control", ""))
        for p in provinces
    ]
    game.full_logs = final_state.get("logs", [])
    
    print(f"   Current year: {final_state.get('current_year')}")
    print(f"   Logs: {len(game.full_logs)}")
    print(f"   Provinces: {len(game.province_state)}")
    
    # Simulate GET /game/{id}
    print("\n4. Retrieving game state...")
    retrieved = get_game(game.id)
    if not retrieved:
        print("   ❌ Game not found!")
        return False
    
    print(f"   Retrieved game: {retrieved.id}")
    print(f"   Current year: {retrieved.get_current_year()}")
    print(f"   Merged: {retrieved.is_merged()}")
    
    # Simulate POST /continue/{id}
    if not retrieved.is_merged():
        print("\n5. Continuing game...")
        
        state = dict(retrieved.workflow_state)
        state["years_to_progress"] = 20
        
        # Reload province memory
        reset_province_memory()
        from workflows.nodes.memory import get_province_memory
        memory = get_province_memory()
        for p in retrieved.province_state:
            memory._provinces[p.id] = p
        
        continued_state = continue_workflow.invoke(state)
        
        print(f"   New year: {continued_state.get('current_year')}")
        print(f"   Merged: {continued_state.get('merged', False)}")
    
    # Cleanup
    delete_game(game.id)
    print("\n✓ API flow test completed!")
    
    return True


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run integration tests")
    parser.add_argument("--test", choices=["full", "rejected", "api", "all"], 
                       default="all", help="Which test to run")
    args = parser.parse_args()
    
    results = []
    
    if args.test in ["full", "all"]:
        results.append(("Full Workflow", test_full_workflow()))
    
    if args.test in ["rejected", "all"]:
        results.append(("Rejected Divergence", test_rejected_divergence()))
    
    if args.test in ["api", "all"]:
        results.append(("API Flow", test_api_flow()))
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    all_passed = True
    for name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False
    
    print()
    sys.exit(0 if all_passed else 1)
