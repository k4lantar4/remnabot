#!/usr/bin/env python3
"""
BMAD Workflow Initialization System
Manages workflow status tracking and initialization for BMAD BMM methodology
"""

import yaml
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum


class WorkflowStatus(Enum):
    """Workflow status types"""
    REQUIRED = "required"
    OPTIONAL = "optional"
    RECOMMENDED = "recommended"
    CONDITIONAL = "conditional"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    IN_PROGRESS = "in-progress"


class WorkflowInitializer:
    """Initialize and manage BMAD workflow status"""
    
    def __init__(self, project_root: str = None):
        """
        Initialize the workflow system
        
        Args:
            project_root: Root directory of the project (defaults to current directory)
        """
        if project_root is None:
            project_root = os.getcwd()
        
        self.project_root = Path(project_root)
        self.output_dir = self.project_root / "_bmad-output" / "project-planning-artifacts"
        self.status_file = self.output_dir / "bmm-workflow-status.yaml"
        self.init_file = self.output_dir / "workflow-init.yaml"
        
        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def load_status(self) -> Dict[str, Any]:
        """Load existing workflow status file"""
        if not self.status_file.exists():
            return {}
        
        with open(self.status_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    
    def load_init_config(self) -> Dict[str, Any]:
        """Load workflow initialization configuration"""
        if not self.init_file.exists():
            return {}
        
        with open(self.init_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    
    def save_status(self, status: Dict[str, Any]) -> None:
        """Save workflow status to file"""
        with open(self.status_file, 'w', encoding='utf-8') as f:
            yaml.dump(status, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    
    def initialize_workflow(self, force: bool = False) -> Dict[str, Any]:
        """
        Initialize workflow status from init configuration
        
        Args:
            force: If True, overwrite existing status file
        
        Returns:
            Dictionary with initialization results
        """
        init_config = self.load_init_config()
        if not init_config:
            return {
                "success": False,
                "error": "No workflow initialization configuration found",
                "suggestion": f"Create {self.init_file}"
            }
        
        existing_status = self.load_status()
        if existing_status and not force:
            return {
                "success": False,
                "error": "Workflow status already exists",
                "suggestion": "Use force=True to overwrite or update_workflow() to update"
            }
        
        # Build workflow status from init config
        workflow_status = {}
        
        # Add metadata
        workflow_status["generated"] = datetime.now().strftime("%Y-%m-%d")
        workflow_status["project"] = init_config.get("project", "unknown")
        workflow_status["project_type"] = init_config.get("project_type", "unknown")
        workflow_status["selected_track"] = init_config.get("selected_track", "method")
        workflow_status["field_type"] = init_config.get("field_type", "brownfield")
        workflow_status["workflow_path"] = init_config.get("workflow_path", "method-brownfield.yaml")
        
        # Build workflow_status section
        workflow_status["workflow_status"] = {}
        
        phases = init_config.get("phases", {})
        for phase_key, phase_data in phases.items():
            workflows = phase_data.get("workflows", [])
            for workflow in workflows:
                for workflow_name, workflow_info in workflow.items():
                    if isinstance(workflow_info, dict):
                        status = workflow_info.get("status", "required")
                        if status == "completed" and "file" in workflow_info:
                            workflow_status["workflow_status"][workflow_name] = workflow_info["file"]
                        elif status == "skipped":
                            workflow_status["workflow_status"][workflow_name] = "skipped"
                        else:
                            workflow_status["workflow_status"][workflow_name] = status
        
        # Save status
        self.save_status(workflow_status)
        
        return {
            "success": True,
            "message": "Workflow initialized successfully",
            "workflows_initialized": len(workflow_status.get("workflow_status", {})),
            "status_file": str(self.status_file)
        }
    
    def update_workflow(self, workflow_name: str, status: str, file_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Update a specific workflow status
        
        Args:
            workflow_name: Name of the workflow to update
            status: New status (completed, skipped, required, etc.)
            file_path: Optional file path if status is completed
        
        Returns:
            Dictionary with update results
        """
        status_data = self.load_status()
        if not status_data:
            return {
                "success": False,
                "error": "No workflow status found. Run initialize_workflow() first."
            }
        
        if "workflow_status" not in status_data:
            status_data["workflow_status"] = {}
        
        # Update status
        if status == "completed" and file_path:
            status_data["workflow_status"][workflow_name] = file_path
        elif status == "skipped":
            status_data["workflow_status"][workflow_name] = "skipped"
        else:
            status_data["workflow_status"][workflow_name] = status
        
        # Update last modified
        status_data["last_updated"] = datetime.now().strftime("%Y-%m-%d")
        
        # Save
        self.save_status(status_data)
        
        return {
            "success": True,
            "message": f"Workflow '{workflow_name}' updated to '{status}'",
            "workflow": workflow_name,
            "status": status
        }
    
    def get_workflow_status(self) -> Dict[str, Any]:
        """
        Get current workflow status summary
        
        Returns:
            Dictionary with workflow status summary
        """
        status_data = self.load_status()
        if not status_data:
            return {
                "initialized": False,
                "message": "Workflow not initialized"
            }
        
        workflow_status = status_data.get("workflow_status", {})
        
        # Count by status type
        completed = sum(1 for v in workflow_status.values() 
                       if isinstance(v, str) and not v in ["required", "optional", "recommended", "conditional", "skipped"])
        skipped = sum(1 for v in workflow_status.values() if v == "skipped")
        required = sum(1 for v in workflow_status.values() if v == "required")
        optional = sum(1 for v in workflow_status.values() if v == "optional")
        recommended = sum(1 for v in workflow_status.values() if v == "recommended")
        
        # Calculate completion percentage
        total = len(workflow_status)
        completion_pct = (completed / total * 100) if total > 0 else 0
        
        return {
            "initialized": True,
            "project": status_data.get("project", "unknown"),
            "generated": status_data.get("generated", "unknown"),
            "total_workflows": total,
            "completed": completed,
            "skipped": skipped,
            "pending_required": required,
            "pending_optional": optional,
            "pending_recommended": recommended,
            "completion_percentage": round(completion_pct, 1),
            "workflows": workflow_status
        }
    
    def check_required_workflows(self) -> Dict[str, Any]:
        """
        Check which required workflows are not yet completed
        
        Returns:
            Dictionary with required workflows status
        """
        status_data = self.load_status()
        if not status_data:
            return {
                "error": "Workflow not initialized"
            }
        
        workflow_status = status_data.get("workflow_status", {})
        
        required_not_completed = []
        required_completed = []
        
        for workflow_name, status in workflow_status.items():
            if status == "required":
                required_not_completed.append(workflow_name)
            elif isinstance(status, str) and status not in ["required", "optional", "recommended", "conditional", "skipped"]:
                # This is a file path, meaning completed
                required_completed.append(workflow_name)
        
        return {
            "required_completed": required_completed,
            "required_pending": required_not_completed,
            "all_required_complete": len(required_not_completed) == 0,
            "total_required": len(required_completed) + len(required_not_completed)
        }
    
    def generate_report(self) -> str:
        """
        Generate a human-readable workflow status report
        
        Returns:
            Markdown formatted report
        """
        summary = self.get_workflow_status()
        required_check = self.check_required_workflows()
        
        if not summary.get("initialized"):
            return "# Workflow Status Report\n\nWorkflow not initialized."
        
        report = f"""# BMAD Workflow Status Report

**Project:** {summary['project']}  
**Generated:** {summary['generated']}  
**Last Updated:** {summary.get('last_updated', 'N/A')}

## Summary

- **Total Workflows:** {summary['total_workflows']}
- **Completed:** {summary['completed']} ✅
- **Skipped:** {summary['skipped']} ⏭️
- **Completion:** {summary['completion_percentage']}%

## Status Breakdown

- **Pending (Required):** {summary['pending_required']} 🔴
- **Pending (Recommended):** {summary['pending_recommended']} 🟡
- **Pending (Optional):** {summary['pending_optional']} 🟢

## Required Workflows Status

"""
        
        if required_check.get("all_required_complete"):
            report += "✅ **All required workflows are complete!**\n\n"
        else:
            report += f"⚠️ **{len(required_check['required_pending'])} required workflow(s) pending:**\n\n"
            for workflow in required_check['required_pending']:
                report += f"- ❌ {workflow}\n"
            report += "\n"
        
        if required_check['required_completed']:
            report += "**Completed required workflows:**\n\n"
            for workflow in required_check['required_completed']:
                report += f"- ✅ {workflow}\n"
            report += "\n"
        
        report += "## All Workflows\n\n"
        for workflow_name, status in summary['workflows'].items():
            if isinstance(status, str) and status not in ["required", "optional", "recommended", "conditional", "skipped"]:
                report += f"- ✅ **{workflow_name}** → `{status}`\n"
            elif status == "skipped":
                report += f"- ⏭️ **{workflow_name}** → skipped\n"
            elif status == "required":
                report += f"- 🔴 **{workflow_name}** → required (pending)\n"
            elif status == "recommended":
                report += f"- 🟡 **{workflow_name}** → recommended\n"
            elif status == "optional":
                report += f"- 🟢 **{workflow_name}** → optional\n"
            else:
                report += f"- ❓ **{workflow_name}** → {status}\n"
        
        return report


def main():
    """CLI entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="BMAD Workflow Initialization System")
    parser.add_argument("command", choices=["init", "status", "update", "report", "check"], 
                       help="Command to execute")
    parser.add_argument("--workflow", help="Workflow name (for update command)")
    parser.add_argument("--status", help="Status value (for update command)")
    parser.add_argument("--file", help="File path (for update command when status=completed)")
    parser.add_argument("--force", action="store_true", help="Force initialization (overwrite existing)")
    parser.add_argument("--project-root", help="Project root directory")
    
    args = parser.parse_args()
    
    initializer = WorkflowInitializer(project_root=args.project_root)
    
    if args.command == "init":
        result = initializer.initialize_workflow(force=args.force)
        print(f"Success: {result.get('success')}")
        if result.get("success"):
            print(f"Message: {result.get('message')}")
            print(f"Workflows initialized: {result.get('workflows_initialized')}")
        else:
            print(f"Error: {result.get('error')}")
            print(f"Suggestion: {result.get('suggestion')}")
    
    elif args.command == "status":
        summary = initializer.get_workflow_status()
        if summary.get("initialized"):
            print(f"Project: {summary['project']}")
            print(f"Completion: {summary['completion_percentage']}%")
            print(f"Completed: {summary['completed']}/{summary['total_workflows']}")
        else:
            print(summary.get("message", "Unknown error"))
    
    elif args.command == "update":
        if not args.workflow or not args.status:
            print("Error: --workflow and --status are required for update command")
            return
        result = initializer.update_workflow(args.workflow, args.status, args.file)
        print(f"Success: {result.get('success')}")
        if result.get("success"):
            print(f"Message: {result.get('message')}")
        else:
            print(f"Error: {result.get('error')}")
    
    elif args.command == "report":
        report = initializer.generate_report()
        print(report)
    
    elif args.command == "check":
        required = initializer.check_required_workflows()
        if "error" in required:
            print(f"Error: {required['error']}")
        else:
            print(f"All required complete: {required['all_required_complete']}")
            print(f"Pending: {len(required['required_pending'])}")
            print(f"Completed: {len(required['required_completed'])}")
            if required['required_pending']:
                print("\nPending workflows:")
                for wf in required['required_pending']:
                    print(f"  - {wf}")


if __name__ == "__main__":
    main()
