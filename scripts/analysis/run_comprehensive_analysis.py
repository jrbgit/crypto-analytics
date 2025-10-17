#!/usr/bin/env python3
"""
Comprehensive Analysis Runner

This script runs analysis across all content types (websites, Medium, whitepapers, Reddit, YouTube)
using llama3.1:latest for the highest quality analysis.
"""

import os
import sys
import time
import signal
import json
import argparse
from pathlib import Path
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from scripts.path_utils import setup_project_paths, get_config_path

# Set up project paths
project_root = setup_project_paths()

from src.models.database import DatabaseManager
from src.pipelines.content_analysis_pipeline import ContentAnalysisPipeline
from src.utils.error_reporter import generate_error_report
from dotenv import load_dotenv

# Load environment variables
load_dotenv(get_config_path() / ".env")

# Global state for graceful shutdown
interrupt_requested = False
analysis_state = {
    'started_at': None,
    'interrupted_at': None,
    'current_content_type': None,
    'completed_content_types': [],
    'total_stats': {
        'successful_analyses': 0,
        'failed_analyses': 0,
        'projects_found': 0
    },
    'current_batch_stats': None
}

def signal_handler(signum, frame):
    """Handle keyboard interruption gracefully."""
    global interrupt_requested, analysis_state
    
    print("\n\n⚠️  INTERRUPT SIGNAL RECEIVED (Ctrl+C)")
    print("🔄 Gracefully shutting down... (this may take a moment)")
    print("⏱️  Please wait for current operation to complete")
    print("🚫 Press Ctrl+C again to force quit (may lose data)")
    
    interrupt_requested = True
    analysis_state['interrupted_at'] = datetime.now(timezone.utc).isoformat()
    
    # Save current state
    save_analysis_state()
    
    # Set up second interrupt handler for force quit
    signal.signal(signal.SIGINT, force_quit_handler)

def force_quit_handler(signum, frame):
    """Handle second Ctrl+C as force quit."""
    print("\n\n🚨 FORCE QUIT REQUESTED")
    print("⚠️  Terminating immediately - some data may be lost")
    save_analysis_state(force_quit=True)
    sys.exit(130)  # Standard exit code for Ctrl+C

def save_analysis_state(force_quit=False):
    """Save current analysis state to file for potential resume."""
    state_file = Path(__file__).parent / "analysis_state.json"
    
    try:
        analysis_state['force_quit'] = force_quit
        analysis_state['saved_at'] = datetime.now(timezone.utc).isoformat()
        
        with open(state_file, 'w') as f:
            json.dump(analysis_state, f, indent=2)
        
        print(f"💾 Analysis state saved to {state_file}")
        
    except Exception as e:
        print(f"⚠️  Failed to save analysis state: {e}")

def load_analysis_state():
    """Load previous analysis state if it exists."""
    state_file = Path(__file__).parent / "analysis_state.json"
    
    if not state_file.exists():
        return None
    
    try:
        with open(state_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️  Failed to load previous analysis state: {e}")
        return None

def clear_analysis_state():
    """Clear the analysis state file after successful completion."""
    state_file = Path(__file__).parent / "analysis_state.json"
    
    try:
        if state_file.exists():
            state_file.unlink()
    except Exception as e:
        print(f"⚠️  Failed to clear analysis state: {e}")

def parse_arguments():
    """Parse command line arguments for toggling analysis types."""
    parser = argparse.ArgumentParser(
        description='Run comprehensive crypto analytics processing',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
examples:
  %(prog)s                                    # Run all analysis types
  %(prog)s --disable reddit,website          # Skip reddit and website analysis
  %(prog)s --enable whitepaper,medium        # Only run whitepaper and medium analysis
  %(prog)s --disable medium --batch-size website=50 # Skip medium, use 50 websites
        '''
    )
    
    parser.add_argument(
        '--disable', 
        type=str, 
        help='Comma-separated list of analysis types to disable (website,whitepaper,medium,reddit,youtube)'
    )
    
    parser.add_argument(
        '--enable', 
        type=str, 
        help='Comma-separated list of analysis types to enable (website,whitepaper,medium,reddit,youtube) - overrides default, mutually exclusive with --disable'
    )
    
    parser.add_argument(
        '--batch-size', 
        type=str, 
        help='Set custom batch sizes as key=value pairs (e.g., website=50,reddit=30)'
    )
    
    parser.add_argument(
        '--list-types', 
        action='store_true', 
        help='List available analysis types and exit'
    )
    
    return parser.parse_args()

def validate_and_process_args(args):
    """Validate and process command line arguments."""
    available_types = {'website', 'whitepaper', 'medium', 'reddit', 'youtube'}
    
    # Handle --list-types
    if args.list_types:
        print("Available analysis types:")
        for content_type in sorted(available_types):
            print(f"  • {content_type}")
        sys.exit(0)
    
    # Handle mutually exclusive --enable and --disable
    if args.enable and args.disable:
        print("Error: --enable and --disable options are mutually exclusive")
        sys.exit(1)
    
    # Process enabled/disabled types
    enabled_types = set(available_types)  # Default: all types enabled
    
    if args.disable:
        disabled_types = set(t.strip().lower() for t in args.disable.split(','))
        invalid_types = disabled_types - available_types
        if invalid_types:
            print(f"Error: Invalid analysis types in --disable: {', '.join(sorted(invalid_types))}")
            print(f"Available types: {', '.join(sorted(available_types))}")
            sys.exit(1)
        enabled_types -= disabled_types
        
    elif args.enable:
        enabled_types = set(t.strip().lower() for t in args.enable.split(','))
        invalid_types = enabled_types - available_types
        if invalid_types:
            print(f"Error: Invalid analysis types in --enable: {', '.join(sorted(invalid_types))}")
            print(f"Available types: {', '.join(sorted(available_types))}")
            sys.exit(1)
    
    # Process custom batch sizes
    custom_batch_sizes = {}
    if args.batch_size:
        try:
            for pair in args.batch_size.split(','):
                content_type, size_str = pair.split('=')
                content_type = content_type.strip().lower()
                size = int(size_str.strip())
                
                if content_type not in available_types:
                    print(f"Error: Invalid content type in --batch-size: {content_type}")
                    print(f"Available types: {', '.join(sorted(available_types))}")
                    sys.exit(1)
                
                if size <= 0:
                    print(f"Error: Batch size must be positive, got {size} for {content_type}")
                    sys.exit(1)
                    
                custom_batch_sizes[content_type] = size
                
        except ValueError as e:
            print(f"Error: Invalid --batch-size format. Expected 'type=number', got: {args.batch_size}")
            print(f"Example: --batch-size website=50,reddit=30")
            sys.exit(1)
    
    return enabled_types, custom_batch_sizes

def run_analysis_batch(content_type, pipeline, batch_size):
    """Run analysis for a specific content type with interrupt handling."""
    global interrupt_requested, analysis_state
    
    if interrupt_requested:
        print(f"\n⏭️  Skipping {content_type} analysis due to interrupt request")
        return None
    
    print(f"\n{'='*20} {content_type.upper()} ANALYSIS {'='*20}")
    analysis_state['current_content_type'] = content_type
    
    # Check how many items need analysis
    projects = pipeline.discover_projects_for_analysis(link_types=[content_type])
    print(f"Found {len(projects)} {content_type} items ready for analysis")
    
    if len(projects) == 0:
        print(f"No {content_type} items need analysis at this time.")
        analysis_state['completed_content_types'].append(content_type)
        return None
    
    if interrupt_requested:
        print(f"\n⏭️  Interrupt received, skipping {content_type} processing")
        return None
    
    print(f"Processing first {batch_size} {content_type} items...")
    
    try:
        # Run the analysis
        stats = pipeline.run_analysis_batch(link_types=[content_type], max_projects=batch_size)
        analysis_state['current_batch_stats'] = stats
        
    except KeyboardInterrupt:
        print(f"\n⚠️  Keyboard interrupt during {content_type} analysis")
        save_analysis_state()
        raise
    
    if interrupt_requested:
        print(f"\n⏭️  Interrupt received after {content_type} analysis, finishing gracefully")
        stats = analysis_state.get('current_batch_stats') or {}
        
    # Mark content type as completed
    analysis_state['completed_content_types'].append(content_type)
    
    # Display results
    print(f"\n=== {content_type.upper()} ANALYSIS RESULTS ===")
    print(f"Projects found: {stats.get('projects_found', 0)}")
    print(f"Successful analyses: {stats.get('successful_analyses', 0)}")
    print(f"Failed analyses: {stats.get('failed_analyses', 0)}")
    
    content_key = f"{content_type}s_analyzed" if content_type == 'website' else f"{content_type}_analyzed"
    analyzed_count = stats.get(content_key, 0)
    print(f"{content_type.title()} items analyzed: {analyzed_count}")
    
    if stats.get('projects_found', 0) > 0:
        success_rate = (stats.get('successful_analyses', 0) / stats['projects_found']) * 100
        print(f"Success rate: {success_rate:.1f}%")
    
    return stats

def main():
    """Run comprehensive analysis across all content types with graceful interrupt handling."""
    global interrupt_requested, analysis_state
    
    # Parse command line arguments
    args = parse_arguments()
    enabled_types, custom_batch_sizes = validate_and_process_args(args)
    
    # Set up signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    
    # Check for previous interrupted state
    previous_state = load_analysis_state()
    if previous_state:
        print(f"\n🔄 RESUMING FROM PREVIOUS SESSION")
        print(f"Previous session started: {previous_state.get('started_at', 'unknown')}")
        if previous_state.get('interrupted_at'):
            print(f"Interrupted at: {previous_state['interrupted_at']}")
        if previous_state.get('completed_content_types'):
            print(f"Completed content types: {', '.join(previous_state['completed_content_types'])}")
        print(f"\nContinuing where we left off...\n")
        
        # Restore state
        analysis_state.update(previous_state)
        analysis_state['resumed'] = True
    
    # Initialize database
    database_url = os.getenv('DATABASE_URL', 'sqlite:///./data/crypto_analytics.db')
    db_manager = DatabaseManager(database_url)
    
    # Initialize pipeline with llama3.1:latest for all analysis
    pipeline = ContentAnalysisPipeline(
        db_manager=db_manager,
        scraper_config={
            'max_pages': 10,         # Website pages
            'max_depth': 2,         # Website depth
            'max_articles': 10,     # Medium articles (reduced)
            'max_posts': 50,        # Reddit posts
            'recent_days': 90,      # Content recency
            'timeout': 60,          # Request timeout
            'delay': 5.0            # Increased rate limiting for Medium
        },
        analyzer_config={
            'provider': 'ollama', 
            'model': 'llama3.1:latest',    # High-quality model for comprehensive analysis
            'ollama_base_url': 'http://localhost:11434'
        }
    )
    
    print("🚀 COMPREHENSIVE CRYPTO ANALYTICS PROCESSING")
    print("Using llama3.1:latest for high-quality analysis")
    
    # Initialize analysis state
    if not analysis_state.get('started_at'):
        analysis_state['started_at'] = datetime.now(timezone.utc).isoformat()
        
    print(f"Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n💡 Press Ctrl+C to gracefully stop and save progress at any time")
    
    # Default batch sizes for each content type (optimized for quality vs speed)
    default_batch_sizes = {
        'website': 30,      # Websites - good balance of speed and coverage
        'whitepaper': 15,   # Whitepapers - slower due to PDF processing
        'medium': 8,        # Medium - reduced to avoid 429 rate limits
        'reddit': 25,       # Reddit - community analysis
        'youtube': 20,      # YouTube - channel and video analysis
    }
    
    # Build batch configs based on enabled types and custom sizes
    batch_configs = []
    for content_type in ['website', 'whitepaper', 'medium', 'reddit', 'youtube']:  # Maintain order
        if content_type in enabled_types:
            batch_size = custom_batch_sizes.get(content_type, default_batch_sizes[content_type])
            batch_configs.append((content_type, batch_size))
    
    # Check if any analysis types are enabled
    if not batch_configs:
        print("\n⚠️  No analysis types are enabled. Nothing to do.")
        print("Use --enable or remove --disable to enable analysis types.")
        print("Run with --list-types to see available options.")
        sys.exit(0)
    
    # Display configuration
    if len(enabled_types) < 5:
        disabled_types = {'website', 'whitepaper', 'medium', 'reddit', 'youtube'} - enabled_types
        print(f"\n🔧 CONFIGURATION:")
        print(f"   Enabled types: {', '.join(sorted(enabled_types))}")
        if disabled_types:
            print(f"   Disabled types: {', '.join(sorted(disabled_types))}")
        for content_type, batch_size in batch_configs:
            default_size = default_batch_sizes[content_type]
            if batch_size != default_size:
                print(f"   {content_type}: {batch_size} items (default: {default_size})")
            else:
                print(f"   {content_type}: {batch_size} items")
    
    # Initialize or restore total stats
    total_stats = analysis_state.get('total_stats', {
        'successful_analyses': 0,
        'failed_analyses': 0,
        'projects_found': 0
    })
    
    try:
        # Process each content type
        for content_type, batch_size in batch_configs:
            # Skip if already completed in previous session
            if content_type in analysis_state.get('completed_content_types', []):
                print(f"\n✅ Skipping {content_type} - already completed in previous session")
                continue
                
            if interrupt_requested:
                print(f"\n⏹️  Stopping before {content_type} analysis due to interrupt")
                break
                
            stats = run_analysis_batch(content_type, pipeline, batch_size)
            
            if stats:
                total_stats['successful_analyses'] += stats.get('successful_analyses', 0)
                total_stats['failed_analyses'] += stats.get('failed_analyses', 0)
                total_stats['projects_found'] += stats.get('projects_found', 0)
                analysis_state['total_stats'] = total_stats
            
            if interrupt_requested:
                print(f"\n⏹️  Interrupt received after {content_type} processing")
                break
            
            # Brief pause between content types (longer for Medium to avoid rate limits)
            if stats and stats.get('projects_found', 0) > 0:
                wait_time = 60 if content_type == 'medium' else 15
                print(f"\nWaiting {wait_time} seconds before processing next content type...")
                
                # Sleep with interrupt checking
                for i in range(wait_time):
                    if interrupt_requested:
                        print(f"\n⏭️  Interrupt received during wait, continuing immediately...")
                        break
                    time.sleep(1)
                    
    except KeyboardInterrupt:
        print(f"\n\n⚠️  Analysis interrupted by user")
        save_analysis_state()
        
    except Exception as e:
        print(f"\n\n💥 Unexpected error during analysis: {e}")
        save_analysis_state()
        raise
    
    # Final summary
    print(f"\n{'='*60}")
    
    if interrupt_requested:
        print("⏸️ ANALYSIS INTERRUPTED - PROGRESS SAVED")
        print(f"{'='*60}")
        print(f"💾 Session state saved - you can resume by running this script again")
        print(f"🔄 Completed content types: {', '.join(analysis_state.get('completed_content_types', []))}")
    else:
        print("🎉 COMPREHENSIVE ANALYSIS COMPLETE")
        print(f"{'='*60}")
        # Clear state file on successful completion
        clear_analysis_state()
        
    print(f"Total projects processed: {total_stats.get('projects_found', 0)}")
    print(f"Total successful analyses: {total_stats.get('successful_analyses', 0)}")
    print(f"Total failed analyses: {total_stats.get('failed_analyses', 0)}")
    
    if total_stats.get('projects_found', 0) > 0:
        overall_success_rate = (total_stats.get('successful_analyses', 0) / total_stats['projects_found']) * 100
        print(f"Overall success rate: {overall_success_rate:.1f}%")
    
    print(f"Completed at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Show next steps
    print(f"\n📊 NEXT STEPS:")
    
    if interrupt_requested:
        print(f"• Run this script again to resume from where you left off")
        print(f"• Or manually delete 'analysis_state.json' to start fresh")
    else:
        print(f"• Run this script again to process more batches")
        
    print(f"• Run 'python monitor_progress.py' to see updated statistics")
    print(f"• Check 'ANALYSIS_REPORT.md' for detailed findings")
    
    # Generate comprehensive error report
    print(f"\n📈 GENERATING ERROR REPORT...")
    try:
        error_summary = generate_error_report(save_to_file=True, print_summary=True)
        print(f"\n📊 Error Report Summary:")
        print(f"  • Total errors logged: {error_summary.get('total_errors', 0)}")
        print(f"  • Estimated success rate: {error_summary.get('success_rate', 0):.1f}%")
        if error_summary.get('most_problematic_domains'):
            print(f"  • Most problematic domains: {len(error_summary['most_problematic_domains'])}")
    except Exception as e:
        print(f"\n⚠️ Failed to generate error report: {e}")
    
    # Handle exit codes
    if interrupt_requested:
        print(f"\n👋 Exiting gracefully...")
        sys.exit(130)  # Standard exit code for SIGINT

if __name__ == "__main__":
    main()