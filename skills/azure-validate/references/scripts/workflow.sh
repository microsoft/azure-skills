#!/usr/bin/env bash
# workflow.sh
# Walks the agent through the azure-validate workflow, one step at a time.
#
# Usage:
#   ./workflow.sh --workspace-path <path> [--completed-step <step>]
#
# Options:
#   --workspace-path <path>    Path to the workspace being validated (required).
#   --completed-step <step>    The workflow step the agent just completed. Omit
#                              on the first call to start the workflow. The
#                              script records the value in
#                              .azure/validate-status.json and returns the next
#                              action to take, along with the value to pass as
#                              --completed-step on the next call.
#
# Exit codes:
#   0 - next action emitted (or workflow complete)
#   2 - usage / argument error (missing workspace path or invalid step)

set -uo pipefail

# Valid workflow steps, in order.
VALID_STEPS=(None LoadPlan AddValidationSteps RunValidation BuildVerification \
    StaticRoleVerification RecordProof ResolveErrors UpdateStatus)

# Ensure an option that consumes a value actually has one ($@ = remaining args).
need_val() {
    [ "$#" -ge 2 ] || { echo "ERROR: $1 requires a value." >&2; exit 2; }
}

WORKSPACE_PATH=""
COMPLETED_STEP=""

while [ $# -gt 0 ]; do
    case "$1" in
        --workspace-path) need_val "$@"; WORKSPACE_PATH="$2"; shift 2 ;;
        --completed-step) need_val "$@"; COMPLETED_STEP="$2"; shift 2 ;;
        -h|--help)
            grep '^#' "$0" | grep -v '^#!' | sed 's/^# \{0,1\}//'
            exit 0 ;;
        *)
            echo "Unknown argument: $1" >&2
            exit 2 ;;
    esac
done

if [ -z "$WORKSPACE_PATH" ]; then
    echo "ERROR: --workspace-path is required." >&2
    exit 2
fi

if [ ! -d "$WORKSPACE_PATH" ]; then
    echo "Error: --workspace-path '$WORKSPACE_PATH' does not exist or is not a directory." >&2
    exit 2
fi

# Resolve the step the agent just completed (case-insensitive).
# Omitting --completed-step signals the start of the workflow (None).
STEP="None"
if [ -n "$COMPLETED_STEP" ]; then
    STEP=""
    for valid in "${VALID_STEPS[@]}"; do
        if [ "$(printf '%s' "$COMPLETED_STEP" | tr '[:upper:]' '[:lower:]')" = \
             "$(printf '%s' "$valid" | tr '[:upper:]' '[:lower:]')" ]; then
            STEP="$valid"
            break
        fi
    done
    if [ -z "$STEP" ]; then
        printf 'Error: '\''--completed-step %s'\'' is not a valid step. Valid values: %s\n' \
            "$COMPLETED_STEP" "$(printf '%s, ' "${VALID_STEPS[@]}" | sed 's/, $//')" >&2
        exit 2
    fi
fi

# Record progress in .azure/validate-status.json (creating it if needed).
AZURE_DIR="$WORKSPACE_PATH/.azure"
mkdir -p "$AZURE_DIR"
VALIDATE_STATUS_PATH="$AZURE_DIR/validate-status.json"
printf '{\n  "completedStep": "%s"\n}\n' "$STEP" > "$VALIDATE_STATUS_PATH"

# Emit the next action based on the step just completed.
case "$STEP" in
    None)
        # Step 1: Load Plan
        echo "Action: Read \`.azure/deployment-plan.md\` for recipe and configuration. If missing, run azure-prepare first, then come back to workflow.sh."
        echo "Next: re-run workflow.sh with --completed-step LoadPlan after completing the action."
        echo "Reference: \`.azure/deployment-plan.md"
        ;;
    LoadPlan)
        # Step 2: Add Validation Steps
        echo "Action: Copy the recipe's \`Validation Steps\` into \`.azure/deployment-plan.md\` as children of \`All validation checks pass\`."
        echo "Next: re-run workflow.sh with --completed-step AddValidationSteps after completing the action."
        echo "Reference: references/recipes/README.md, \`.azure/deployment-plan.md"
        ;;
    AddValidationSteps)
        # Step 3: Run Validation
        echo "Action: Execute the recipe-specific validation commands."
        echo "Next: re-run workflow.sh with --completed-step RunValidation after completing the action."
        echo "Reference: references/recipes/README.md"
        ;;
    RunValidation)
        # Step 4: Build Verification
        echo "Action: Build the project and fix any errors before proceeding."
        echo "Next: re-run workflow.sh with --completed-step BuildVerification after completing the action."
        echo "Reference: See the recipe for build details."
        ;;
    BuildVerification)
        # Step 5: Static Role Verification
        echo "Action: Review the Bicep/Terraform for correct RBAC role assignments in code."
        echo "Next: re-run workflow.sh with --completed-step StaticRoleVerification after completing the action."
        echo "Reference: references/role-verification.md"
        ;;
    StaticRoleVerification)
        # Step 6: Record Proof
        echo "Action: Populate **Section 7: Validation Proof** in the plan with the commands run and their results."
        echo "Next: re-run workflow.sh with --completed-step RecordProof after completing the action."
        echo "Reference: \`.azure/deployment-plan.md"
        ;;
    RecordProof)
        # Step 7: Resolve Errors
        echo "Action: Fix any validation failures before proceeding."
        echo "Next: re-run workflow.sh with --completed-step ResolveErrors after completing the action."
        echo "Reference: See the recipe's errors.md."
        ;;
    ResolveErrors)
        # Step 8: Update Status
        echo "Action: Only after ALL checks pass, set the plan status to \`Validated\`."
        echo "Next: re-run workflow.sh with --completed-step UpdateStatus after completing the action."
        echo "Reference: \`.azure/deployment-plan.md"
        ;;
    UpdateStatus)
        # Step 9: Deploy (workflow complete)
        echo "Action: The azure-validate workflow is complete. If the user explicitly requested deployment, invoke azure-deploy. Otherwise STOP and report the validation results."
        ;;
esac

exit 0
