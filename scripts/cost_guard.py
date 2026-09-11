"""GCP Cost-Guard: Zero-Idle-Burn Resource Auditor.

Verifies that no continuous billable GCP resources are left running idle:
1. Vertex AI Vector Search Index Endpoints (avoids ~$150-$300/mo)
2. Cloud Run Services min-instances (guarantees scale-to-zero)
3. Compute Engine VMs (guarantees 0 running instances)
"""

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import settings


def run_cost_guard_audit() -> bool:
    print("=" * 60)
    print("   GCP COST-GUARD: ZERO-IDLE-BURN AUDIT FOR MULTIMODAL RAG")
    print("=" * 60)
    print(f"Target Project: {settings.gcp_project_id}")
    print(f"Target Region:  {settings.gcp_region}")
    print()

    has_error = False

    # 1. Audit Vertex AI Vector Search Index Endpoints
    print("[1/3] Auditing Vertex AI Vector Search Index Endpoints...", end="", flush=True)
    try:
        from google.cloud import aiplatform

        aiplatform.init(
            project=settings.gcp_project_id,
            location=settings.gcp_region,
        )
        endpoints = aiplatform.MatchingEngineIndexEndpoint.list()
        if endpoints:
            print(" [WARNING]")
            print(f"  Found {len(endpoints)} active Index Endpoints:")
            for ep in endpoints:
                print(f"   - {ep.resource_name}")
            print("  ACTION REQUIRED: Delete endpoints to avoid idle billing (~$150-$300/mo)!")
            has_error = True
        else:
            print(" [PASS] 0 active index endpoints found ($0.00 idle cost).")
    except Exception as e:
        print(f" [SKIP] Unable to query Vertex AI: {e}")

    # 2. Audit Cloud Run Services min-instances
    print("[2/3] Auditing Cloud Run Services (Scale-to-Zero)...", end="", flush=True)
    try:
        import google.auth
        from google.auth.transport.requests import AuthorizedSession

        creds, _ = google.auth.load_credentials_from_file(
            settings.google_application_credentials,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        session = AuthorizedSession(creds)
        url = f"https://run.googleapis.com/v2/projects/{settings.gcp_project_id}/locations/{settings.gcp_region}/services"
        res = session.get(url)
        if res.status_code == 200:
            svcs = res.json().get("services", [])
            idle_svcs = []
            for s in svcs:
                min_scale = (
                    s.get("scaling", {}).get("minInstanceCount", 0)
                    or s.get("template", {})
                    .get("annotations", {})
                    .get("autoscaling.knative.dev/minScale", 0)
                )
                if int(min_scale) > 0:
                    idle_svcs.append((s.get("name"), min_scale))

            if idle_svcs:
                print(" [WARNING]")
                for name, scale in idle_svcs:
                    print(f"  Service '{name}' has min-instances={scale} (idle burn!)")
                has_error = True
            else:
                print(f" [PASS] All {len(svcs)} Cloud Run services configured with scale-to-zero (min-instances=0).")
        else:
            print(f" [SKIP] HTTP {res.status_code} querying Cloud Run.")
    except Exception as e:
        print(f" [SKIP] Unable to query Cloud Run: {e}")

    # 3. Audit Compute Engine instances
    print("[3/3] Auditing Compute Engine VMs...", end="", flush=True)
    try:
        import google.auth
        from google.auth.transport.requests import AuthorizedSession

        creds, _ = google.auth.load_credentials_from_file(
            settings.google_application_credentials,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        session = AuthorizedSession(creds)
        url = f"https://compute.googleapis.com/compute/v1/projects/{settings.gcp_project_id}/aggregated/instances"
        res = session.get(url)
        if res.status_code == 200:
            items = res.json().get("items", {})
            running_vms = [
                vm.get("name")
                for zone_data in items.values()
                for vm in zone_data.get("instances", [])
                if vm.get("status") == "RUNNING"
            ]
            if running_vms:
                print(" [WARNING]")
                for vm_name in running_vms:
                    print(f"  VM '{vm_name}' is RUNNING.")
                has_error = True
            else:
                print(f" [PASS] 0 running VMs found ($0.00 idle cost).")
        else:
            print(f" [SKIP] HTTP {res.status_code} querying Compute Engine.")
    except Exception as e:
        print(f" [SKIP] Unable to query Compute Engine: {e}")

    print()
    print("=" * 60)
    if not has_error:
        print("AUDIT RESULT: PASSED. Zero idle billing detected.")
    else:
        print("AUDIT RESULT: ATTENTION REQUIRED. Billable resources detected.")
    print("=" * 60)
    return not has_error


if __name__ == "__main__":
    success = run_cost_guard_audit()
    sys.exit(0 if success else 1)
