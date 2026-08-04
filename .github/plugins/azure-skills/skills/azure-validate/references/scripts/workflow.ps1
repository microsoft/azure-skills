<#
.SYNOPSIS
    Walks the agent through the azure-validate workflow, one step at a time.
.PARAMETER WorkspacePath
    Path to the workspace being validated (required).
.PARAMETER CompletedStep
    The workflow step the agent just completed. Omit this on the first call to
    start the workflow. The script records the value in
    .azure/validate-status.json and returns the next action to take, along with
    the value to pass as -CompletedStep on the next call.
#>
param(
    [string]$WorkspacePath,
    [string]$CompletedStep
)

enum ValidationStep {
    None
    LoadPlan
    AddValidationSteps
    RunValidation
    BuildVerification
    StaticRoleVerification
    RecordProof
    ResolveErrors
    UpdateStatus
}

if (-not $WorkspacePath) {
    Write-Error "WorkspacePath is required."
    exit 2
}

if (-not (Test-Path -Path $WorkspacePath -PathType Container)) {
    Write-Error "Error: WorkspacePath '$WorkspacePath' does not exist or is not a directory."
    exit 2
}

# Resolve the step the agent just completed.
# Omitting -CompletedStep signals the start of the workflow (None).
$step = [ValidationStep]::None
if (-not [string]::IsNullOrEmpty($CompletedStep)) {
    if (-not [enum]::TryParse([ValidationStep], $CompletedStep, $true, [ref]$step)) {
        $validValues = ([enum]::GetNames([ValidationStep])) -join ", "
        Write-Error "Error: '-CompletedStep $CompletedStep' is not a valid step. Valid values: $validValues"
        exit 2
    }
}

# Record progress in .azure/validate-status.json (creating it if needed).
$azureDir = Join-Path -Path $WorkspacePath -ChildPath ".azure"
if (-not (Test-Path -Path $azureDir)) {
    New-Item -ItemType Directory -Path $azureDir | Out-Null
}
$validateStatusPath = Join-Path -Path $azureDir -ChildPath "validate-status.json"
$validateStatusJson = @{ completedStep = $step.ToString() } | ConvertTo-Json
[System.IO.File]::WriteAllText($validateStatusPath, $validateStatusJson + [Environment]::NewLine, (New-Object System.Text.UTF8Encoding($false)))

# Emit the next action based on the step just completed.

# Step 1: Load Plan
if ($step -eq [ValidationStep]::None) {
    Write-Output 'Action: Read `.azure/deployment-plan.md` for recipe and configuration. If missing, run azure-prepare first, then come back to workflow.ps1.'
    Write-Output "Next: re-run workflow.ps1 with -CompletedStep LoadPlan after completing the action."
    Write-Output 'Reference: `.azure/deployment-plan.md'
    exit 0
}

# Step 2: Add Validation Steps
if ($step -eq [ValidationStep]::LoadPlan) {
    Write-Output 'Action: Copy the recipe''s `Validation Steps` into `.azure/deployment-plan.md` as children of `All validation checks pass`.'
    Write-Output "Next: re-run workflow.ps1 with -CompletedStep AddValidationSteps after completing the action."
    Write-Output 'Reference: references/recipes/README.md, `.azure/deployment-plan.md'
    exit 0
}

# Step 3: Run Validation
if ($step -eq [ValidationStep]::AddValidationSteps) {
    Write-Output "Action: Execute the recipe-specific validation commands."
    Write-Output "Next: re-run workflow.ps1 with -CompletedStep RunValidation after completing the action."
    Write-Output "Reference: references/recipes/README.md"
    exit 0
}

# Step 4: Build Verification
if ($step -eq [ValidationStep]::RunValidation) {
    Write-Output "Action: Build the project and fix any errors before proceeding."
    Write-Output "Next: re-run workflow.ps1 with -CompletedStep BuildVerification after completing the action."
    Write-Output "Reference: See the recipe for build details."
    exit 0
}

# Step 5: Static Role Verification
if ($step -eq [ValidationStep]::BuildVerification) {
    Write-Output "Action: Review the Bicep/Terraform for correct RBAC role assignments in code."
    Write-Output "Next: re-run workflow.ps1 with -CompletedStep StaticRoleVerification after completing the action."
    Write-Output "Reference: references/role-verification.md"
    exit 0
}

# Step 6: Record Proof
if ($step -eq [ValidationStep]::StaticRoleVerification) {
    Write-Output "Action: Populate **Section 7: Validation Proof** in the plan with the commands run and their results."
    Write-Output "Next: re-run workflow.ps1 with -CompletedStep RecordProof after completing the action."
    Write-Output 'Reference: `.azure/deployment-plan.md'
    exit 0
}

# Step 7: Resolve Errors
if ($step -eq [ValidationStep]::RecordProof) {
    Write-Output "Action: Fix any validation failures before proceeding."
    Write-Output "Next: re-run workflow.ps1 with -CompletedStep ResolveErrors after completing the action."
    Write-Output "Reference: See the recipe's errors.md."
    exit 0
}

# Step 8: Update Status
if ($step -eq [ValidationStep]::ResolveErrors) {
    Write-Output 'Action: Only after ALL checks pass, set the plan status to `Validated`.'
    Write-Output "Next: re-run workflow.ps1 with -CompletedStep UpdateStatus after completing the action."
    Write-Output 'Reference: `.azure/deployment-plan.md'
    exit 0
}

# Step 9: Deploy (workflow complete)
if ($step -eq [ValidationStep]::UpdateStatus) {
    Write-Output "Action: The azure-validate workflow is complete. If the user explicitly requested deployment, invoke azure-deploy. Otherwise STOP and report the validation results."
    exit 0
}
