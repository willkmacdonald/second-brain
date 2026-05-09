# Config + env-var deltas for Phase 24

**Source of truth:** [docs/superpowers/specs/2026-05-05-foundry-ga-migration-design.md](../../../docs/superpowers/specs/2026-05-05-foundry-ga-migration-design.md) Section "Phase 23.0 deliverables" item 6 + Section "Phase 24 Deploy sequence".
**Applied by:** Phase 24 task groups 23.1 (config.py additions) and 23.3 (Container App env vars + orphan cleanup) per design.
**NOT applied in Phase 23:** every change below is documentation-only at the close of Phase 23.

## Phase 24 task group 23.1 --- config.py additions

File: `backend/src/second_brain/config.py`

| Setting | Default | Purpose | Source |
|---|---|---|---|
| `foundry_model: str = "gpt-4o"` | `"gpt-4o"` | Model deployment name passed to `FoundryChatClient(model=...)`. Reads from `FOUNDRY_MODEL` env var via pydantic-settings convention. | Design Section "Phase 23.0 deliverables" item 6 |

Diff (illustrative --- Phase 24 task group 23.1 applies):
```python
class Settings(BaseSettings):
    # ... existing ...
    azure_ai_project_endpoint: str = ""        # KEEP --- reused by FoundryChatClient
    azure_ai_classifier_agent_id: str = ""     # KEEP for now (Phase 24 task group 23.3 removes)
    azure_ai_admin_agent_id: str = ""          # KEEP for now (Phase 24 task group 23.3 removes)
    azure_ai_investigation_agent_id: str = ""  # KEEP for now (Phase 24 task group 23.3 removes)
    foundry_model: str = "gpt-4o"              # NEW --- Phase 24 task group 23.1
```

Note on `FoundryChatClient` constructor: per FOUNDRY-PROBE-FINDINGS.md Probe 5, the GA constructor takes `project_endpoint` (not `endpoint`) and `model` (not `model_deployment_name`). Phase 24 task group 23.1 wires:
```python
client = FoundryChatClient(
    project_endpoint=settings.azure_ai_project_endpoint,
    model=settings.foundry_model,
    credential=ManagedIdentityCredential(),
)
```

## Phase 24 deploy step --- Container App env vars

Per design Section "Deploy sequence (deterministic, env vars before image)", these are set via `az containerapp update --set-env-vars` against the EXISTING RC revision FIRST, then the image is pushed. The RC code ignores GA-only vars; the GA code finds them already in place when it starts.

Operator-side `az` command (Phase 24 task group 23.3 final pre-push step):
```bash
az containerapp update \
  --name second-brain-api \
  --resource-group shared-services-rg \
  --set-env-vars \
    FOUNDRY_MODEL=gpt-4o \
    ENABLE_INSTRUMENTATION=true \
    ENABLE_SENSITIVE_DATA=false
```

| Env var | Value | Reason | Already present in RC env? |
|---|---|---|---|
| `FOUNDRY_MODEL` | `gpt-4o` (or whichever deployment is current --- verify with `az cognitiveservices account deployment list`) | GA `FoundryChatClient` requires explicit deployment name via `model=` param | NO --- added by deploy step |
| `ENABLE_INSTRUMENTATION` | `true` | GA framework emits OTel spans + GenAI usage metrics when set. Already called in `main.py:31` via `enable_instrumentation()` at import time; this env var enables the framework-level span emission for `invoke_agent` / `execute_tool` spans. | Verify via `az containerapp show --name second-brain-api --resource-group shared-services-rg --query "properties.template.containers[0].env[?name=='ENABLE_INSTRUMENTATION']"` --- may already be present from Phase 17.4. If already set, the deploy step is idempotent. |
| `ENABLE_SENSITIVE_DATA` | `false` | Design Section "Observability --- Configure" --- keeps prompt content out of spans by default. When `false`, `invoke_agent` / `execute_tool` spans contain metadata (agent name, tool name, token counts) but NOT the full prompt or response text. | NO --- added by deploy step. Setting `false` is the safe default; operator can toggle to `true` for debugging sessions and revert. |

Verify before push:
```bash
az containerapp revision list --name second-brain-api --resource-group shared-services-rg \
  --query "[?properties.active].{name:name, env:properties.template.containers[0].env}" -o json \
  | jq '.[0].env | map(select(.name | test("FOUNDRY|ENABLE_INSTRUMENTATION|ENABLE_SENSITIVE_DATA"))) '
```
Output must show all three vars set with the expected values BEFORE `git push origin main`.

## Phase 24 task group 23.3 --- config.py orphan cleanup

Final cleanup commit at end of task group 23.3 removes settings made obsolete by D-02 (instructions in repo, no portal agent IDs needed):

| Setting | Action | Reason |
|---|---|---|
| `azure_ai_classifier_agent_id` | DELETE | Classifier agent constructed via `Agent(client=FoundryChatClient(...), instructions=load_instructions("classifier"), tools=[file_capture])` --- no portal agent ID consumed |
| `azure_ai_admin_agent_id` | DELETE | Admin agent constructed similarly |
| `azure_ai_investigation_agent_id` | DELETE | Investigation agent constructed similarly |
| `azure_ai_project_endpoint` | KEEP | Reused as endpoint URL passed to `FoundryChatClient(project_endpoint=...)` |

### Safe deploy sequence (NON-NEGOTIABLE)

> **DO NOT remove the `AZURE_AI_*_AGENT_ID` env vars before the GA image is deployed.** The currently-deployed RC image's `backend/src/second_brain/main.py` reads `settings.azure_ai_classifier_agent_id` at lifespan startup (`main.py:514`), `settings.azure_ai_admin_agent_id` at `main.py:596`, and `settings.azure_ai_investigation_agent_id` at `main.py:687`. If any of those settings is empty when an RC revision boots, the corresponding `ensure_*_agent` helper falls through to creating a brand-new BLANK portal agent (see `backend/src/second_brain/agents/classifier.py:40` and the symmetric `agents/admin.py` / `agents/investigation.py` paths), causing live agent drift in the Foundry portal BEFORE the intended cutover. **Removing those env vars against the RC image is a forbidden destructive action.**

The deploy must be staged in three steps. Each step is its own `az containerapp update` invocation --- orphan cleanup is moved to a SEPARATE post-deploy step.

**Step A --- Pre-deploy env-var add (Phase 24 task group 23.3, BEFORE `git push origin main`):**

Add the GA-only env vars to the existing RC revision. Do NOT remove anything --- the RC code still reads `AZURE_AI_*_AGENT_ID` at startup. The new env vars are simply ignored by RC code (they're not referenced anywhere in the RC `main.py`).

```bash
az containerapp update \
  --name second-brain-api \
  --resource-group shared-services-rg \
  --set-env-vars \
    FOUNDRY_MODEL=gpt-4o \
    ENABLE_INSTRUMENTATION=true \
    ENABLE_SENSITIVE_DATA=false
```

Verify the revision boots cleanly with all old vars still present:
```bash
az containerapp revision list -n second-brain-api -g shared-services-rg \
  --query "[?properties.active].{name:name, healthState:properties.healthState}" -o table
az containerapp show -n second-brain-api -g shared-services-rg \
  --query "properties.template.containers[0].env[?name=='AZURE_AI_CLASSIFIER_AGENT_ID' || name=='FOUNDRY_MODEL']" -o table
# MUST show BOTH AZURE_AI_CLASSIFIER_AGENT_ID and FOUNDRY_MODEL present.
```

**Step B --- GA image push (Phase 24 task group 23.3, the `git push` itself):**

`git push origin main` triggers GitHub Actions OIDC build -> ACR -> Container Apps deploy of the GA image. The GA image's `main.py` no longer references `settings.azure_ai_classifier_agent_id` / `settings.azure_ai_admin_agent_id` / `settings.azure_ai_investigation_agent_id` (Phase 24 task group 23.3's final cleanup commit removes those reads --- the corresponding `azure_ai_*_agent_id` fields are also removed from `config.py` in that same commit). The GA revision starts up with `FOUNDRY_MODEL` / `ENABLE_INSTRUMENTATION` / `ENABLE_SENSITIVE_DATA` already in place from Step A AND with the orphaned `AZURE_AI_*_AGENT_ID` env vars still present --- orphaned env vars are harmless because the GA code never references them.

Confirm the GA revision is healthy and serving traffic before proceeding to Step C:
```bash
curl -s -H "X-API-Key: $API_KEY" https://brain.willmacdonald.com/api/health | jq '.'
az containerapp logs show -n second-brain-api -g shared-services-rg --tail 50
```

**Step C --- Post-deploy orphan removal (Phase 24, AFTER successful UAT):**

Once the GA image has been observed healthy through the post-deploy UAT (capture flow, errands processing, investigation chat all passing), remove the orphaned env vars in a separate `az containerapp update` call:

```bash
az containerapp update \
  --name second-brain-api \
  --resource-group shared-services-rg \
  --remove-env-vars \
    AZURE_AI_CLASSIFIER_AGENT_ID \
    AZURE_AI_ADMIN_AGENT_ID \
    AZURE_AI_INVESTIGATION_AGENT_ID
```

This causes a new revision to start with the orphan vars absent. The GA code does not read them, so this is safe. The `azure_ai_*_agent_id` fields are also already removed from `backend/src/second_brain/config.py` (Phase 24 task group 23.3 final cleanup commit, in the same commit as the `main.py` lifespan-read removals). The portal-side agent records (`asst_Fnjkq5RVrvdFIOSqbreAwxuq`, the admin agent, `asst_5feSWWTMA8rBSUyQo6aSCsEJ`) become unreferenced; they can be left in the portal as orphaned-but-harmless or deleted manually. Document the choice in the Phase 24 task group 23.3 SUMMARY.

### NEGATIVE assertion (do not violate)

**NEVER** run any variant of the following before Step B (GA image push) is observed healthy:

```bash
# FORBIDDEN before GA image is deployed:
az containerapp update --name second-brain-api --resource-group shared-services-rg \
  --remove-env-vars AZURE_AI_CLASSIFIER_AGENT_ID AZURE_AI_ADMIN_AGENT_ID AZURE_AI_INVESTIGATION_AGENT_ID

# ALSO FORBIDDEN: setting any of those agent ID vars to empty string against the RC image
az containerapp update --name second-brain-api --resource-group shared-services-rg \
  --set-env-vars AZURE_AI_CLASSIFIER_AGENT_ID=
```

Doing so against the RC image will cause the classifier/admin/investigation agents to either fail startup (unlikely --- current code falls through gracefully) or, more dangerously, fall through to creating new BLANK portal agents per `agents/classifier.py:40` / `agents/admin.py` / `agents/investigation.py`. That creates live agent drift in the Foundry portal BEFORE the intended cutover and silently changes which agent ID the production system addresses. Recovery requires re-pinning the original agent IDs and possibly deleting the stray blank portal agents --- a 15-minute incident at minimum.

## Credential class change

Per design D-07a + auth_probe finding (PLAN-02): the deployed Container App uses `ManagedIdentityCredential`, not `AzureCliCredential`. Phase 24 task group 23.1 wires `FoundryChatClient(credential=ManagedIdentityCredential())` in `main.py` lifespan. The probe validated the credential class shape (FoundryChatClient accepts an azure-credential object) and the RBAC role assignment shape (the role names that work for `az login` are the role names the Container App managed identity needs).

Required RBAC roles to assign to Container App managed identity (from PLAN-02 `auth_probe.json`):
- **Azure AI User** (subscription-scoped) --- confirmed working for agent invocation via the auth_probe. The probe's `az login` identity also had **Owner** at subscription scope, but Owner is overly broad for a managed identity; **Azure AI User** alone should suffice for agent invocation. Verify minimal RBAC during day-after UAT.

These role assignments may already be in place from the RC era (the current Container App managed identity uses `DefaultAzureCredential` which chains through managed identity). Verify via:
```bash
az role assignment list \
  --assignee $(az containerapp show -n second-brain-api -g shared-services-rg --query identity.principalId -o tsv) \
  --scope /subscriptions/24ee21b9-$(az account show --query id -o tsv | cut -c10-) \
  -o table
```

If **Azure AI User** is missing, assign it as part of Phase 24 task group 23.3 deploy step BEFORE the env-var update:
```bash
az role assignment create \
  --assignee $(az containerapp show -n second-brain-api -g shared-services-rg --query identity.principalId -o tsv) \
  --role "Azure AI User" \
  --scope /subscriptions/$(az account show --query id -o tsv)
```

## Phase 23 boundary respected

None of the changes above are applied in Phase 23. Verify:
```bash
grep -q "foundry_model" backend/src/second_brain/config.py   # MUST return non-zero (foundry_model NOT yet added)
grep -q "azure_ai_classifier_agent_id" backend/src/second_brain/config.py   # MUST return zero (still present)
```

As of Phase 23 closeout:
- `backend/src/second_brain/config.py` is unchanged --- `foundry_model` is NOT present, all three `azure_ai_*_agent_id` settings are still present
- No Container App env vars have been added or removed
- No RBAC role assignments have been changed
- All changes documented above are Phase 24 work items, organized by task group
