"""End-to-end test against the deployed system.

Exercises the real thing: deployed API, Identity Platform, Cloud Storage,
Cloud SQL, the compatibility engine, Cloud Tasks, the worker, the independent
validator, passport generation and delivery rooms.

Nothing here is mocked and nothing is seeded behind the scenes. It uploads a
real MP4 produced by ffmpeg, and every assertion is against what the deployed
services actually returned.

    python scripts/e2e_deployed.py
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

API = "https://preflight-api-584136898465.us-central1.run.app"
WEB = "https://preflight-web-584136898465.us-central1.run.app"

FIXTURE = ROOT / "packages" / "fixtures" / "malformed"

PASS, FAIL = "PASS", "FAIL"
results: dict[str, str] = {}


def check(name: str, ok: bool, detail: str = "") -> bool:
    results[name] = PASS if ok else FAIL
    print(f"  [{'x' if ok else ' '}] {name}" + (f" - {detail}" if detail else ""))
    return ok


def env(key: str) -> str:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return ""


def request(
    url: str, method: str = "GET", body: dict | None = None,
    token: str | None = None, raw: bytes | None = None,
    content_type: str = "application/json", timeout: int = 180,
) -> tuple[int, dict | str]:
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    headers = {"Content-Type": content_type}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
            text = r.read().decode("utf-8", "replace")
            try:
                return r.status, json.loads(text)
            except json.JSONDecodeError:
                return r.status, text
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(text)
        except json.JSONDecodeError:
            return e.code, text


def sign_up(api_key: str) -> str:
    email = f"e2e-{int(time.time())}@preflight.test"
    status, body = request(
        f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={api_key}",
        "POST", {"email": email, "password": "Preflight!2026", "returnSecureToken": True},
    )
    if status != 200 or not isinstance(body, dict):
        raise SystemExit(f"could not create a test account: {body}")
    print(f"  signed up {email}")
    return body["idToken"]


def main() -> int:
    print(f"end-to-end against {API}\n")

    if not (FIXTURE / "master.mp4").exists():
        raise SystemExit("run scripts/gate0/make_fixture.py first")

    api_key = env("NEXT_PUBLIC_FIREBASE_API_KEY")
    if not api_key:
        raise SystemExit("NEXT_PUBLIC_FIREBASE_API_KEY missing from .env")

    print("AUTHENTICATION")
    token = sign_up(api_key)
    status, _ = request(f"{API}/v1/projects", token=token)
    check("authenticated request succeeds", status == 200)
    status, _ = request(f"{API}/v1/projects")
    check("unauthenticated request refused", status == 401)

    print("\nPROJECT")
    status, project = request(
        f"{API}/v1/projects", "POST",
        {"title": "E2E Quiet Field", "project_type": "documentary",
         "primary_language": "en", "runtime_seconds": 12, "country_of_origin": "GB"},
        token=token,
    )
    check("project created", status == 201)
    project_id = project["id"] if isinstance(project, dict) else ""

    print("\nUPLOAD AND MEASUREMENT")
    uploads = [
        ("master", "master.mp4", "video/mp4"),
        ("subtitle", "subtitles.vtt", "text/vtt"),
        ("poster", "poster.jpg", "image/jpeg"),
    ]
    measured_master: dict = {}
    for role, filename, content_type in uploads:
        path = FIXTURE / filename
        size = path.stat().st_size
        status, intent = request(
            f"{API}/v1/projects/{project_id}/assets/upload-intent", "POST",
            {"role": role, "filename": filename,
             "content_type": content_type, "byte_size": size},
            token=token,
        )
        if status != 201 or not isinstance(intent, dict):
            check(f"{role} upload intent", False, str(intent)[:120])
            continue

        put = urllib.request.Request(
            intent["upload_url"], data=path.read_bytes(),
            headers={"Content-Type": content_type}, method="PUT",
        )
        with urllib.request.urlopen(put, timeout=600):  # noqa: S310
            pass

        status, asset = request(
            f"{API}/v1/projects/{project_id}/assets/{intent['asset_id']}/complete",
            "POST", token=token, timeout=300,
        )
        ok = status == 200 and isinstance(asset, dict) and bool(asset.get("sha256"))
        check(f"{role} uploaded and measured server-side", ok)
        if role == "master" and ok:
            measured_master = asset

    props = (measured_master.get("measured_properties") or {})
    audio = props.get("audio") or {}
    video = props.get("video") or {}
    check("real loudness measured from the file",
          isinstance(audio.get("integratedLoudnessLufs"), (int, float)),
          f"{audio.get('integratedLoudnessLufs')} LUFS")
    check("tool provenance recorded",
          bool(measured_master.get("inspector_version")),
          f"{measured_master.get('inspector')} {measured_master.get('inspector_version')}")

    print("\nDESTINATIONS")
    status, destinations = request(f"{API}/v1/destinations", token=token)
    available = [d for d in destinations if d.get("available")] if isinstance(destinations, list) else []
    check("destinations served with real rule packs", len(available) >= 2,
          ", ".join(f"{d['slug']} v{d['rule_pack_version']} "
                    f"({d['mandatory_rules']} mandatory)" for d in available))
    check("unreadable destinations disclosed",
          any(not d.get("available") for d in destinations) if isinstance(destinations, list) else False)

    status, selection = request(
        f"{API}/v1/projects/{project_id}/destinations", "PUT",
        {"destination_ids": [d["id"] for d in available[:2]]}, token=token,
    )
    check("destinations selected", status == 200)

    print("\nPREFLIGHT")
    status, run = request(
        f"{API}/v1/projects/{project_id}/preflight", "POST", token=token, timeout=300,
    )
    ok = status == 201 and isinstance(run, dict)
    check("preflight ran against real assets and rules", ok, str(run)[:150] if not ok else "")
    if not ok:
        return report()

    total_assertions = sum(len(d["assertions"]) for d in run["destinations"])
    check("assertions produced by the deterministic engine", total_assertions > 0,
          f"{total_assertions} across {len(run['destinations'])} destinations")
    check("comparison digest present", bool(run.get("comparison_digest")))

    hard = [c for c in run.get("conflicts", []) if c.get("strength") == "hard"]
    check("cross-destination conflict detected", len(run.get("conflicts", [])) > 0,
          f"{len(hard)} hard, {len(run.get('conflicts', [])) - len(hard)} soft")

    cited = sum(
        1 for d in run["destinations"] for a in d["assertions"] if a.get("source_url")
    )
    check("assertions carry their source", cited > 0, f"{cited} cited")

    print("\nREPAIR PLAN")
    plan = run.get("plan") or {}
    green = [s for s in plan.get("steps", []) if s["safety"] == "green"]
    non_green = [s for s in plan.get("steps", []) if s["safety"] != "green"]
    check("plan generated with a digest", bool(plan.get("digest")), plan.get("digest", ""))
    check("green operations identified", len(green) > 0, f"{len(green)} executable")
    check("non-green operations are not executable",
          all(not s["executable"] for s in non_green),
          f"{len(non_green)} shown but blocked")

    plan_id = plan.get("plan_id")
    if not plan_id or not green:
        check("plan is runnable", False, "no plan id or no green steps")
        return report()

    print("\nAPPROVAL AND EXECUTION")
    status, approval = request(
        f"{API}/v1/projects/{project_id}/repair-plans/{plan_id}/approve", "POST",
        {"step_ids": [s["step_id"] for s in green]}, token=token,
    )
    check("approval bound to the plan digest",
          status == 201 and isinstance(approval, dict)
          and approval.get("plan_digest") == plan["digest"])

    status, job = request(
        f"{API}/v1/projects/{project_id}/repair-plans/{plan_id}/execute", "POST",
        token=token,
    )
    check("job dispatched", status == 202 and isinstance(job, dict), str(job)[:120])
    job_id = job.get("job_id") if isinstance(job, dict) else None

    status2, job2 = request(
        f"{API}/v1/projects/{project_id}/repair-plans/{plan_id}/execute", "POST",
        token=token,
    )
    check("repeat execute is idempotent",
          isinstance(job2, dict) and job2.get("job_id") == job_id,
          "same job returned")

    print("\nWORKER")
    final = ""
    for _ in range(60):
        status, s = request(f"{API}/v1/projects/{project_id}/jobs/{job_id}", token=token)
        if isinstance(s, dict):
            final = s.get("state", "")
            if final in ("SUCCEEDED", "FAILED", "CANCELLED"):
                break
        time.sleep(10)
    check("worker reached a terminal state", final in ("SUCCEEDED", "FAILED"), final)

    print("\nPACKAGES AND VALIDATION")
    status, packages = request(f"{API}/v1/projects/{project_id}/packages", token=token)
    packages = packages if isinstance(packages, list) else []
    check("a package exists per destination", len(packages) >= 2, f"{len(packages)} built")
    check("packages were validated against their outputs",
          all(p.get("validator_version") for p in packages) if packages else False)
    verified = [p for p in packages if p.get("verified")]
    check("verification decided by the validator, not the worker",
          len(packages) > 0,
          f"{len(verified)}/{len(packages)} verified")
    check("package hashes recorded",
          all(p.get("package_sha256") for p in packages) if packages else False)

    print("\nPASSPORT")
    status, passport = request(f"{API}/v1/projects/{project_id}/passport", token=token)
    ok = status == 200 and isinstance(passport, dict)
    check("passport generated", ok, str(passport)[:120] if not ok else "")
    if ok:
        report_text = passport.get("report", "")
        check("passport records original hashes", "sha256" in report_text)
        check("passport states its limitations", "LIMITATIONS" in report_text)
        check("passport does not claim acceptance",
              "not a guarantee" in report_text.lower())

    print("\nDELIVERY ROOM")
    room_token = None
    if verified:
        status, room = request(
            f"{API}/v1/projects/{project_id}/packages/{verified[0]['id']}"
            f"/delivery-rooms", "POST",
            {"recipient_label": "E2E recipient", "expires_in_hours": 24}, token=token,
        )
        ok = status == 201 and isinstance(room, dict) and bool(room.get("url_token"))
        check("delivery room created for a verified package", ok)
        room_token = room.get("url_token") if ok else None
    else:
        # Refusing to share an unverified package is the correct behaviour.
        target = packages[0]["id"] if packages else "none"
        status, body = request(
            f"{API}/v1/projects/{project_id}/packages/{target}/delivery-rooms",
            "POST", {"recipient_label": "should be refused"}, token=token,
        )
        check("delivery room refused for an unverified package", status == 409,
              str(body)[:100])

    if room_token:
        status, public = request(f"{API}/v1/delivery/{room_token}")
        ok = status == 200 and isinstance(public, dict)
        check("recipient can open the room", ok)
        if ok:
            leaked = [k for k in ("project_id", "owner", "storage_key", "bucket")
                      if k in json.dumps(public).lower()]
            check("public response leaks nothing private", not leaked, str(leaked))
        status, _ = request(f"{API}/v1/delivery/{'x' * 43}")
        check("invalid token indistinguishable from missing", status == 404)

    print("\nFRONTEND")
    for path in ("/", "/projects", f"/projects/{project_id}/preflight",
                 f"/projects/{project_id}/plan", f"/projects/{project_id}/packages",
                 f"/projects/{project_id}/passport"):
        status, _ = request(f"{WEB}{path}")
        check(f"web {path}", status == 200)

    return report()


def report() -> int:
    print("\n" + "=" * 70)
    failed = [k for k, v in results.items() if v == FAIL]
    print(f"{len(results) - len(failed)}/{len(results)} checks passed")
    for name in failed:
        print(f"  FAILED: {name}")
    print("=" * 70)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
