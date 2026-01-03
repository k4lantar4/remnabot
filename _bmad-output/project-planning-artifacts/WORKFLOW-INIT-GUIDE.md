# BMAD Workflow Initialization Guide

This guide explains how to use the BMAD Workflow Initialization System to manage your project workflow status.

## Overview

The workflow initialization system helps you:
- Track progress through BMAD BMM methodology phases
- Monitor required vs optional workflows
- Generate status reports
- Update workflow completion status

## Files

- **`workflow-init.yaml`** - Configuration file defining all workflows and their initial status
- **`bmm-workflow-status.yaml`** - Current workflow status (auto-generated/updated)
- **`workflow_init.py`** - Python script for managing workflows

## Quick Start

### 1. Initialize Workflow

Initialize the workflow system from the configuration:

```bash
cd _bmad-output/project-planning-artifacts
python workflow_init.py init
```

Or from project root:

```bash
python _bmad-output/project-planning-artifacts/workflow_init.py init --project-root .
```

### 2. Check Status

View current workflow status:

```bash
python workflow_init.py status
```

### 3. Generate Report

Generate a detailed markdown report:

```bash
python workflow_init.py report
```

### 4. Check Required Workflows

See which required workflows are pending:

```bash
python workflow_init.py check
```

### 5. Update Workflow Status

Mark a workflow as completed:

```bash
python workflow_init.py update --workflow create-epics-and-stories --status completed --file "_bmad-output/epics-and-stories.md"
```

Mark a workflow as skipped:

```bash
python workflow_init.py update --workflow test-design --status skipped
```

## Status Types

### Initial Status (Before Completion)
- **`required`** - Must be completed to progress
- **`optional`** - Can be completed but not required
- **`recommended`** - Strongly suggested but not required
- **`conditional`** - Required only if certain conditions are met

### Completion Status
- **`{file-path}`** - File created/found (e.g., `"docs/product-brief.md"`)
- **`skipped`** - Optional/conditional workflow that was skipped

## Workflow Phases

The BMAD BMM methodology includes these phases:

1. **Prerequisite** - Documentation
2. **Discovery** - Optional research and brainstorming
3. **Planning** - PRD and UX design
4. **Solutioning** - Architecture, epics, and readiness
5. **Implementation** - Sprint planning and execution

## Python API Usage

You can also use the workflow system programmatically:

```python
from workflow_init import WorkflowInitializer

# Initialize
initializer = WorkflowInitializer(project_root=".")

# Initialize workflow
result = initializer.initialize_workflow()
print(result)

# Get status
status = initializer.get_workflow_status()
print(f"Completion: {status['completion_percentage']}%")

# Update a workflow
initializer.update_workflow(
    "create-epics-and-stories",
    "completed",
    "_bmad-output/epics-and-stories.md"
)

# Check required workflows
required = initializer.check_required_workflows()
print(f"All required complete: {required['all_required_complete']}")

# Generate report
report = initializer.generate_report()
print(report)
```

## Configuration File Structure

The `workflow-init.yaml` file defines:

```yaml
project: "remnabot"
project_type: "saas-multi-tenant"
selected_track: "method"
field_type: "brownfield"

phases:
  prerequisite:
    name: "Prerequisite - Documentation"
    workflows:
      - document-project:
          status: "completed"
          file: "docs/index.md"
          required: true
  # ... more phases
```

## Status File Structure

The `bmm-workflow-status.yaml` file tracks:

```yaml
generated: "2025-12-26"
project: "remnabot"
project_type: "saas-multi-tenant"
selected_track: "method"
field_type: "brownfield"
workflow_path: "method-brownfield.yaml"

workflow_status:
  document-project: "docs/index.md"  # Completed
  create-epics-and-stories: "required"  # Pending
  test-design: "recommended"  # Pending
```

## Best Practices

1. **Initialize Early** - Run `init` at the start of your project
2. **Update Regularly** - Mark workflows as completed when done
3. **Check Before Proceeding** - Use `check` to see if required workflows are complete
4. **Generate Reports** - Use `report` for documentation and status updates
5. **Keep Files in Sync** - Update `workflow-init.yaml` when adding new workflows

## Troubleshooting

### "Workflow not initialized"
Run `python workflow_init.py init` first.

### "No workflow initialization configuration found"
Create or check `workflow-init.yaml` exists.

### "Workflow status already exists"
Use `--force` flag to overwrite, or use `update` command to modify existing status.

## Integration with BMAD Workflows

This system integrates with BMAD workflow commands:

- `@workflow-init` - Initializes the workflow system
- `@workflow-status` - Checks current workflow status
- Other BMAD workflows can update status automatically

## Example Workflow

```bash
# 1. Initialize
python workflow_init.py init

# 2. Check what's required
python workflow_init.py check

# 3. Complete a workflow
python workflow_init.py update --workflow create-epics-and-stories --status completed --file "_bmad-output/epics.md"

# 4. Check status again
python workflow_init.py status

# 5. Generate report for documentation
python workflow_init.py report > workflow-status-report.md
```

## Next Steps

After initializing:
1. Review the generated `bmm-workflow-status.yaml`
2. Check which required workflows are pending
3. Complete workflows in order
4. Update status as you progress
5. Generate reports for stakeholders
