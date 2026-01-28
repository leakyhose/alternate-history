"""
Interactive test script for the alternate history workflow.

Usage:
  python test_workflow.py
  
Then enter a divergence prompt when asked. The script will:
1. Run the filter agent (accepted/rejected + year)
2. If accepted, run the writer agent
3. Then run the cartographer agent
4. Then run the ruler updates agent
5. Display all outputs
"""
import json
import os
from pprint import pprint

from agents.filter_agent import filter_command
from agents.writer_agent import write_narrative
from agents.cartographer_agent import extract_territorial_changes
from agents.ruler_updates_agent import update_rulers
from agents.geographer_agent import interpret_territorial_changes
from util.scenario import get_scenario_tags

# Get the backend directory path
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))


def load_rulers_for_year(scenario_id: str, year: int) -> dict:
    """Load rulers from rulers.json for a given year.
    
    Returns a dict mapping TAG -> ruler info (lowercase keys).
    """
    rulers_path = os.path.join(BACKEND_DIR, "static", "scenarios", scenario_id, "rulers.json")
    
    try:
        with open(rulers_path, 'r') as f:
            all_rulers = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Warning: Could not load rulers.json: {e}")
        return {}
    
    # Find the closest year that exists
    year_str = str(year)
    if year_str in all_rulers:
        rulers_list = all_rulers[year_str]
    else:
        # Find nearest year
        available_years = sorted([int(y) for y in all_rulers.keys()])
        nearest = min(available_years, key=lambda y: abs(y - year))
        rulers_list = all_rulers[str(nearest)]
        print(f"Note: No rulers for year {year}, using year {nearest}")
    
    # Convert to dict keyed by TAG with lowercase keys
    rulers = {}
    for ruler in rulers_list:
        tag = ruler.get("TAG")
        if tag:
            rulers[tag] = {
                "name": ruler.get("NAME", "Unknown"),
                "title": ruler.get("TITLE", "Ruler"),
                "age": ruler.get("AGE", 40),
                "dynasty": ruler.get("DYNASTY", "Unknown")
            }
    
    return rulers


def load_scenario_tags(scenario_id: str) -> dict:
    """Load available tags from scenario metadata."""
    metadata_path = os.path.join(BACKEND_DIR, "static", "scenarios", scenario_id, "metadata.json")
    
    try:
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
            return metadata.get("tags", {})
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Warning: Could not load metadata.json: {e}")
        return {}


def test_workflow(divergence: str, years_to_progress: int = 20):
    """Run the full workflow and print results at each step."""
    
    print("\n" + "="*60)
    print("STEP 1: FILTER AGENT")
    print("="*60)
    print(f"Input: \"{divergence}\"")
    print("-"*40)
    
    filter_result = filter_command(divergence)
    print("Filter Result:")
    pprint(filter_result)
    
    if filter_result.get("status") != "accepted":
        print("\n❌ Divergence REJECTED")
        print(f"   Reason: {filter_result.get('reason')}")
        print(f"   Try instead: {filter_result.get('alternative')}")
        if "raw_response" in filter_result:
            print(f"\n   Raw response for debugging:")
            print(f"   {filter_result.get('raw_response')}")
        return
    
    start_year = filter_result.get("year")
    print(f"\n✓ Divergence ACCEPTED")
    print(f"  Start year: {start_year} AD")
    
    # Set up initial state
    scenario_id = "rome"
    available_tags = load_scenario_tags(scenario_id)
    
    # Load initial rulers from rulers.json
    rulers = load_rulers_for_year(scenario_id, start_year)
    
    print(f"\nLoaded {len(rulers)} ruler(s):")
    for tag, info in rulers.items():
        print(f"  {tag}: {info['name']} ({info['title']})")
    
    print("\n" + "="*60)
    print("STEP 2: WRITER AGENT")
    print("="*60)
    print(f"Period: {start_year}-{start_year + years_to_progress} AD")
    print(f"Divergence: {divergence}")
    print("-"*40)
    
    # Create initial log
    initial_log = {
        "year_range": f"-{start_year} AD",
        "narrative": f"History up to {start_year} AD proceeded as in our timeline.",
        "divergences": [divergence],
    }
    
    writer_output = write_narrative(
        divergences=[divergence],
        condensed_logs="",
        recent_logs=[initial_log],
        current_year=start_year,
        years_to_progress=years_to_progress,
        available_tags=available_tags
    )
    
    print("\nWriter Output:")
    print(f"\nNarrative:")
    print(f"  {writer_output.get('narrative', 'No narrative')}")
    
    print(f"\nKept Divergences:")
    for div in writer_output.get("updated_divergences", []):
        print(f"  • {div}")
    
    print(f"\nNew Divergences (butterfly effects):")
    for div in writer_output.get("new_divergences", []):
        print(f"  • {div}")
    
    print(f"\nMerged: {writer_output.get('merged', False)}")
    
    # Step 3: Cartographer Agent
    narrative = writer_output.get("narrative", "")
    year_range = f"{start_year}-{start_year + years_to_progress}"
    
    print("\n" + "="*60)
    print("STEP 3: CARTOGRAPHER AGENT")
    print("="*60)
    print(f"Extracting territorial changes from narrative...")
    print(f"Available tags: {list(available_tags.keys())}")
    print("-"*40)
    
    cartographer_output = extract_territorial_changes(
        narrative=narrative,
        year_range=year_range,
        available_tags=list(available_tags.keys())
    )
    
    territorial_changes = cartographer_output.get("territorial_changes", [])
    print(f"\nTerritorial Changes ({len(territorial_changes)} total):")
    for change in territorial_changes:
        change_type = change.get('change_type')
        location = change.get('location')
        from_n = change.get('from_nation', '-')
        to_n = change.get('to_nation', '-')
        print(f"  • {change_type}: {location} (from: {from_n}, to: {to_n})")
    
    # Step 4: Ruler Updates Agent
    print("\n" + "="*60)
    print("STEP 4: RULER UPDATES AGENT")
    print("="*60)
    print(f"Updating rulers based on narrative...")
    print("-"*40)
    
    ruler_output = update_rulers(
        current_rulers=rulers,
        narrative=narrative,
        current_year=start_year,
        years_to_progress=years_to_progress
    )
    
    print(f"\nUpdated Rulers:")
    for tag, info in ruler_output.get("rulers", {}).items():
        print(f"  {tag}: {info.get('name')}, {info.get('title')}, age {info.get('age')}, {info.get('dynasty', '')} dynasty")
    
    # Step 5: Geographer Agent (microservice preview)
    print("\n" + "="*60)
    print("STEP 5: GEOGRAPHER AGENT (microservice)")
    print("="*60)
    print(f"Input territorial changes: {len(territorial_changes)} structured change(s)")
    for i, change in enumerate(territorial_changes):
        print(f"  [{i}] {change.get('change_type')}: {change.get('location')}")
    print("-"*40)
    
    geographer_output = interpret_territorial_changes(
        territorial_changes=territorial_changes,
        scenario_id=scenario_id,
        current_provinces=None  # In full workflow, this would be from province memory
    )
    
    print("\nGeographer Output:")
    
    province_updates = geographer_output.get("province_updates", [])
    print(f"\nProvince Updates ({len(province_updates)} total):")
    if province_updates:
        for update in province_updates[:20]:  # Show first 20
            print(f"  ID {update['id']} ({update['name']}): owner={update['owner']}")
        if len(province_updates) > 20:
            print(f"  ... and {len(province_updates) - 20} more")
    else:
        print("  No province updates needed")

    print("\n" + "="*60)
    print("WORKFLOW COMPLETE")
    print("="*60)
    
    return {
        "filter": filter_result,
        "writer": writer_output,
        "cartographer": cartographer_output,
        "ruler_updates": ruler_output,
        "geographer": geographer_output
    }


def main():
    print("="*60)
    print("ALTERNATE HISTORY WORKFLOW TESTER")
    print("="*60)
    print("Enter a divergence prompt to test the full workflow.")
    print("Type 'quit' or 'exit' to stop.")
    print("Type 'years=N' to change years_to_progress (default: 20)")
    print()
    
    years = 20
    
    while True:
        try:
            prompt = input("\n📜 Enter divergence: ").strip()
            
            if not prompt:
                continue
            
            if prompt.lower() in ("quit", "exit", "q"):
                print("Goodbye!")
                break
            
            if prompt.lower().startswith("years="):
                try:
                    years = int(prompt.split("=")[1])
                    print(f"Years to progress set to: {years}")
                except ValueError:
                    print("Invalid number. Usage: years=20")
                continue
            
            test_workflow(prompt, years)
            
        except KeyboardInterrupt:
            print("\n\nInterrupted. Type 'quit' to exit or enter another prompt.")
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
