"""Agent nodes for the alternate history workflow."""
from workflows.state import WorkflowState
from agents.historian_agent import get_historical_context
from agents.dreamer_agent import make_decision
from agents.geographer_agent import interpret_territorial_changes
from util.scenario import get_scenario_tags
from workflows.nodes.memory import get_province_memory
from util.workflow_logger import workflow_logger, get_state_summary


def _print_separator(title: str):
    """Print a formatted separator with title."""
    print("\n" + "="*60)
    print(title)
    print("="*60)


def historian_node(state: WorkflowState) -> dict:
    """
    Historian Agent: Provide real historical context for the period.
    
    The Historian does NOT see current alternate state - only provides
    the baseline of what ACTUALLY happened in real history.
    """
    current_year = state.get("current_year", state.get("start_year"))
    years_to_progress = state.get("years_to_progress", 20)
    
    _print_separator("HISTORIAN AGENT")
    print(f"Period: {current_year}-{current_year + years_to_progress} AD")
    print("(Reporting REAL history only - no alternate timeline knowledge)")
    print("-"*40)
    
    workflow_logger.node_start("historian", {
        "period": f"{current_year}-{current_year + years_to_progress}"
    })
    
    try:
        # NOTE: We intentionally do NOT pass rulers or any alternate timeline info
        # The Historian only knows real history
        historian_output = get_historical_context(
            start_year=current_year,
            years_to_progress=years_to_progress
        )
        
        # Print detailed output
        print("\nHistorian Output:")
        print(f"  Period: {historian_output.get('period')}")
        print("\n  Conditional Events:")
        for cond in historian_output.get("conditional_events", []):
            print(f"    IF: {cond.get('condition')}")
            print(f"    THEN: {cond.get('outcome')}")
            print()
        
        workflow_logger.node_end("historian", {
            "period": historian_output.get("period"),
            "conditional_events": len(historian_output.get("conditional_events", []))
        })
        
        return {
            "historian_output": historian_output
        }
    except Exception as e:
        print(f"\n❌ Historian Error: {e}")
        workflow_logger.node_error("historian", e)
        return {
            "historian_output": {
                "period": f"{current_year}-{current_year + years_to_progress}",
                "conditional_events": []
            },
            "error": str(e),
            "error_node": "historian"
        }


def dreamer_node(state: WorkflowState) -> dict:
    """
    Dreamer Agent: Make creative decisions based on divergences.
    
    Synthesizes divergences + historian context to decide what actually happens.
    Only allows nation tags defined in the scenario metadata.
    """
    historian_output = state.get("historian_output", {})
    divergences = state.get("divergences", [])
    condensed_logs = state.get("condensed_logs", "")
    logs = state.get("logs", [])
    rulers = state.get("rulers", {})
    current_year = state.get("current_year", state.get("start_year"))
    years_to_progress = state.get("years_to_progress", 20)
    scenario_id = state.get("scenario_id", "rome")
    
    _print_separator("DREAMER AGENT")
    print(f"Period: {current_year}-{current_year + years_to_progress} AD")
    print(f"Divergences: {divergences}")
    print(f"Current Rulers: {list(rulers.keys())}")
    print("-"*40)
    
    workflow_logger.node_start("dreamer", {
        "period": f"{current_year}-{current_year + years_to_progress}",
        "divergences": divergences[:3] if len(divergences) > 3 else divergences,
        "rulers": list(rulers.keys())
    })
    
    # Get available nation tags from scenario metadata
    available_tags = get_scenario_tags(scenario_id)
    print(f"Available tags: {list(available_tags.keys())}")
    
    try:
        # Call the actual Dreamer agent
        dreamer_output = make_decision(
            historian_output=historian_output,
            divergences=divergences,
            condensed_logs=condensed_logs,
            recent_logs=logs,
            rulers=rulers,
            current_year=current_year,
            years_to_progress=years_to_progress,
            available_tags=available_tags
        )
        
        # Print detailed output
        print("\nDreamer Output:")
        print("\n  Rulers:")
        for tag, info in dreamer_output.get("rulers", {}).items():
            print(f"    {tag}: {info.get('name')}, {info.get('title')}, age {info.get('age')}, {info.get('dynasty')} dynasty")
        
        print(f"\n  Narrative:")
        narrative = dreamer_output.get('narrative', 'No narrative')
        # Print narrative with word wrap
        for i in range(0, len(narrative), 80):
            print(f"    {narrative[i:i+80]}")
        
        print(f"\n  Territorial Changes:")
        territorial = dreamer_output.get('territorial_changes_description', 'None')
        for i in range(0, len(territorial), 80):
            print(f"    {territorial[i:i+80]}")
        
        print(f"\n  Updated Divergences:")
        for div in dreamer_output.get("updated_divergences", []):
            print(f"    • {div}")
        
        print(f"\n  Merged: {dreamer_output.get('merged', False)}")
        
        workflow_logger.node_end("dreamer", {
            "rulers": list(dreamer_output.get("rulers", {}).keys()),
            "merged": dreamer_output.get("merged", False),
            "divergences": len(dreamer_output.get("updated_divergences", []))
        })
        
        return {
            "dreamer_output": dreamer_output
        }
    except Exception as e:
        print(f"\n❌ Dreamer Error: {e}")
        workflow_logger.node_error("dreamer", e)
        return {
            "dreamer_output": {
                "rulers": rulers,
                "narrative": f"[Error in Dreamer agent: {str(e)}]",
                "territorial_changes_description": "",
                "updated_divergences": divergences,
                "merged": False
            },
            "error": str(e),
            "error_node": "dreamer"
        }


def geographer_node(state: WorkflowState) -> dict:
    """
    Geographer Agent: Translate territorial descriptions to province updates.
    
    Interprets Dreamer's prose and converts to OWNER/CONTROL changes.
    Uses tools to query regions and find province IDs.
    """
    dreamer_output = state.get("dreamer_output", {})
    territorial_description = dreamer_output.get("territorial_changes_description", "")
    scenario_id = state.get("scenario_id", "rome")
    
    _print_separator("GEOGRAPHER AGENT")
    print(f"Input territorial description:")
    desc_preview = territorial_description[:200] + "..." if len(territorial_description) > 200 else territorial_description
    print(f"  {desc_preview}")
    print("-"*40)
    
    workflow_logger.node_start("geographer", {
        "description_length": len(territorial_description),
        "scenario": scenario_id
    })
    
    # Get current province state for context
    memory = get_province_memory()
    current_provinces = memory.get_all_provinces_as_dicts()
    
    try:
        # Call the Geographer agent to interpret territorial changes
        geographer_output = interpret_territorial_changes(
            territorial_description=territorial_description,
            scenario_id=scenario_id,
            current_provinces=current_provinces
        )
        
        # Extract province updates
        province_updates = geographer_output.get("province_updates", [])
        reasoning = geographer_output.get("reasoning", "")
        
        # Print detailed output
        print("\nGeographer Output:")
        print(f"  Reasoning: {reasoning}")
        
        print(f"\n  Province Updates ({len(province_updates)} total):")
        if province_updates:
            for update in province_updates[:20]:  # Show first 20
                control_str = f", control: {update['control']}" if update.get('control') else ""
                print(f"    ID {update['id']} ({update['name']}): owner={update['owner']}{control_str}")
            if len(province_updates) > 20:
                print(f"    ... and {len(province_updates) - 20} more")
        else:
            print("    No province updates needed")
        
        workflow_logger.node_end("geographer", {
            "province_updates": len(province_updates),
            "reasoning": reasoning[:100] if reasoning else "none"
        })
        
        return {
            "territorial_changes": province_updates
        }
    except Exception as e:
        print(f"\n❌ Geographer Error: {e}")
        workflow_logger.node_error("geographer", e)
        return {
            "territorial_changes": [],
            "error": str(e),
            "error_node": "geographer"
        }
