"""Invoke hourly from the deployment scheduler using an authorized API session.

Environment: SUITE_API_URL, SUITE_ACCESS_TOKEN, SUITE_BRANCH_ID.
No credentials are accepted in command arguments or printed.
"""
import os
import httpx


def main():
    base = os.environ["SUITE_API_URL"].rstrip("/")
    if not base.startswith("https://") and not base.startswith("http://127.0.0.1:"):
        raise ValueError("Use HTTPS for remote deployments")
    headers = {"Authorization": "Bearer " + os.environ["SUITE_ACCESS_TOKEN"], "X-Suite-Branch": os.environ["SUITE_BRANCH_ID"]}
    with httpx.Client(timeout=120) as client:
        response = client.post(base + "/api/v1/srm/recurring-invoices/process-due", headers=headers)
        response.raise_for_status()
        print("Recurring drafts created:", response.json()["created"])


if __name__ == "__main__":
    main()
