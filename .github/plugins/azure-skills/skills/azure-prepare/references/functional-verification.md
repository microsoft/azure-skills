# Functional Verification

Verify that the application works correctly — both UI and backend — before proceeding to validation and deployment. This step prevents deploying broken or incomplete functionality to Azure.

## When to Verify

After generating all artifacts (code, infrastructure, configuration) and applying security hardening — but **before** marking the plan as `Ready for Validation`.

## Verification Checklist

Use `ask_user` to confirm functional testing with the user:

```
"Before we proceed to deploy, would you like to verify the app works as expected?
We can test both the UI and backend to catch issues before they reach Azure."
```

### Backend Verification

| Check | How |
|-------|-----|
| **App starts without errors** | Run the app and confirm no startup crashes or missing dependencies |
| **API endpoints respond** | Test core routes (e.g., `curl` health, list, create endpoints) |
| **Data operations work** | Verify CRUD operations against storage, database, or other services |
| **Authentication flows** | Confirm auth works (tokens, managed identity fallback, login/logout) |
| **Error handling** | Verify error responses are meaningful (not unhandled exceptions) |

### UI Verification

| Check | How |
|-------|-----|
| **Page loads** | Open the app in a browser and confirm the UI renders |
| **Interactive elements work** | Test buttons, forms, file inputs, navigation links |
| **Data displays correctly** | Verify lists, images, and dynamic content render from the backend |
| **User workflows complete** | Walk through the core user journey end-to-end (e.g., upload → view → delete) |

## Decision Tree

```
App artifacts generated?
├── Yes → Ask user: "Would you like to verify functionality?"
│   ├── User says yes
│   │   ├── App can run locally? → Run locally, verify backend + UI
│   │   ├── API-only / no UI? → Test endpoints with curl or similar
│   │   └── Static site? → Open in browser, verify rendering
│   │   Then:
│   │   ├── Works → Proceed to Update Plan (step 6)
│   │   └── Issues found → Fix issues, re-test
│   └── User says no / skip → Proceed to Update Plan (step 6)
└── No → Go back to Generate Artifacts (step 3)
```

## Running Locally

For apps that can run locally, help the user start the app based on the detected runtime:

| Runtime | Command | Notes |
|---------|---------|-------|
| Node.js | `npm install && npm start` | Set `PORT=3000` if not configured |
| Python | `pip install -r requirements.txt && python app.py` | Use virtual environment |
| .NET | `dotnet run` | Check `launchSettings.json` for port |
| Java | `mvn spring-boot:run` or `gradle bootRun` | Check `application.properties` |

> ⚠️ **Warning:** For apps using Azure services (e.g., Blob Storage, Cosmos DB), local testing requires the user to be authenticated via `az login` with sufficient RBAC roles, or to have local emulators configured (e.g., Azurite for Storage).

## Record in Plan

After functional verification, add a note to `.azure/plan.md`:

```markdown
## Functional Verification
- Status: Verified / Skipped
- Backend: Tested / Not applicable
- UI: Tested / Not applicable
- Notes: <any issues found and resolved>
```
