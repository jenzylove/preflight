"""Drive a deliverable master to VERIFIED against the deployed system.

The Gate 0 fixture is deliberately broken, which proves detection and can never
prove delivery. This runs the other case: a master built to Artdocfest's
published FullHD specification, with two faults Preflight is allowed to correct,
through to a verified package and an open delivery room.

Two requirements are set aside along the way, using the product's own rule
disposition mechanism, because extraction misread them. Each is set aside with
the reason stated, recorded against the user, and carried into the passport as a
limitation. Nothing is deleted and nothing is silently ignored.

    python scripts/e2e_verified.py
"""

from __future__ import annotations

import http.client
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

API = "https://preflight-api-584136898465.us-central1.run.app"
WEB = "https://preflight-web-584136898465.us-central1.run.app"
FIXTURE = ROOT / "packages" / "fixtures" / "deliverable"

results: dict[str, bool] = {}


def check(name: str, ok: bool, detail: str = "") -> bool:
    results[name] = ok
    print(f"  [{'x' if ok else ' '}] {name}" + (f" - {detail}" if detail else ""))
    return ok


def env(key: str) -> str:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return ""


def request(url, method="GET", body=None, token=None, timeout=300):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    last = None
    for attempt in range(3):
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
        except (TimeoutError, urllib.error.URLError, http.client.HTTPException,
                ConnectionError, OSError) as e:
            last = e
            time.sleep(2 * (attempt + 1))
    return 0, f"transport failure: {last}"


#: Requirements extraction misread, each with the reason a producer would give.
#: These are set aside through the product's own mechanism, not filtered out.
MISREADS = [
    (
        ("audio", "loudnessRangeLu"),
        "The source states 'Dynamic range 25 - 30dB', which is a peak-to-average "
        "figure in dB. Preflight measures EBU R128 Loudness Range in LU. These "
        "are different quantities and the comparison is not meaningful.",
    ),
    (
        ("package", "fileNamePattern"),
        "ISDCF is the name of a naming convention, not a filename pattern. The "
        "extracted rule compares our filename against the string 'ISDCF'.",
    ),
    (
        ("audio", "bitrateBps"),
        "The source states 'Bitrate from 320 kbit/s', which is a minimum. This "
        "rule was extracted as an exact equality.",
    ),
    (
        ("audio", "truePeakDbtp"),
        "The source states '-3 (Peak)', which is a ceiling. This rule was "
        "extracted as an exact equality.",
    ),
]


def main() -> int:
    print(f"deliverable master -> VERIFIED, against {API}\n")

    master = FIXTURE / "master.mp4"
    if not master.exists():
        raise SystemExit("run scripts/gate0/make_deliverable_fixture.py first")

    api_key = env("NEXT_PUBLIC_FIREBASE_API_KEY")
    email = f"verified-{int(time.time())}@preflight.test"
    status, body = request(
        f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={api_key}",
        "POST", {"email": email, "password": "Preflight!2026", "returnSecureToken": True},
    )
    token = body["idToken"]
    print(f"  signed up {email}")

    print("\nPROJECT")
    status, project = request(
        f"{API}/v1/projects", "POST",
        {
            "title": "A Quiet Field", "project_type": "documentary",
            "primary_language": "en", "runtime_seconds": 60,
            "country_of_origin": "GB",
            "synopsis": "A field before anyone arrives, and the sound that "
                        "builds and falls away across a single afternoon.",
        },
        token=token,
    )
    check("project created with delivery metadata", status == 201)
    project_id = project["id"]

    print("\nUPLOAD")
    for role, filename, content_type, language in [
        ("master", "master.mp4", "video/mp4", None),
        ("subtitle", "subtitles.vtt", "text/vtt", "en"),
        ("poster", "poster.jpg", "image/jpeg", None),
    ]:
        path = FIXTURE / filename
        payload = {
            "role": role, "filename": filename,
            "content_type": content_type, "byte_size": path.stat().st_size,
        }
        if language:
            payload["language"] = language
        status, intent = request(
            f"{API}/v1/projects/{project_id}/assets/upload-intent", "POST",
            payload, token=token,
        )
        put = urllib.request.Request(
            intent["upload_url"], data=path.read_bytes(),
            headers={"Content-Type": content_type}, method="PUT",
        )
        with urllib.request.urlopen(put, timeout=1800):  # noqa: S310
            pass
        status, asset = request(
            f"{API}/v1/projects/{project_id}/assets/{intent['asset_id']}/complete",
            "POST", token=token, timeout=900,
        )
        check(f"{role} uploaded and measured", status == 200 and bool(asset.get("sha256")))

    print("\nDESTINATION")
    status, destinations = request(f"{API}/v1/destinations", token=token)
    artdocfest = next(d for d in destinations if d["slug"] == "artdocfest")
    status, _ = request(
        f"{API}/v1/projects/{project_id}/destinations", "PUT",
        {"destination_ids": [artdocfest["id"]]}, token=token,
    )
    check("artdocfest selected", status == 200,
          f"v{artdocfest['rule_pack_version']}, {artdocfest['mandatory_rules']} mandatory")

    print("\nSETTING ASIDE MISREAD REQUIREMENTS")
    status, rules = request(f"{API}/v1/projects/{project_id}/rules", token=token)
    set_aside = 0
    for (asset_type, field_name), reason in MISREADS:
        targets = [
            r for r in rules
            if r["asset_type"] == asset_type and r["field"] == field_name
        ]
        for rule in targets:
            status, _ = request(
                f"{API}/v1/projects/{project_id}/rules/{rule['rule_id']}/disposition",
                "PUT", {"action": "set_aside", "reason": reason}, token=token,
            )
            if status == 200:
                set_aside += 1
    check("misread requirements set aside with a stated reason", set_aside > 0,
          f"{set_aside} rules, each recorded and carried into the passport")

    print("\nPREFLIGHT")
    status, run = request(
        f"{API}/v1/projects/{project_id}/preflight", "POST", token=token,
    )
    check("preflight ran", status == 201)
    matrix = run["destinations"][0]
    check("requirements measured against the real file", matrix["total"] > 0,
          f"{matrix['satisfied']}/{matrix['total']} satisfied")

    plan = run["plan"]
    green = [s for s in plan["steps"] if s["safety"] == "green"]
    yellow = plan.get("needs_your_decision", [])
    check("a repair plan was generated", bool(plan.get("plan_id")), plan["digest"])
    check("green operations identified", len(green) > 0, f"{len(green)}")
    if yellow:
        check("yellow operations shown but not executable",
              all(not s["executable"] for s in yellow), f"{len(yellow)} shown")

    if matrix["blocking"]:
        print(f"      still blocking: {', '.join(matrix['blocking'][:8])}")

    print("\nAPPROVAL AND EXECUTION")
    status, approval = request(
        f"{API}/v1/projects/{project_id}/repair-plans/{plan['plan_id']}/approve",
        "POST",
        {"plan_digest": plan["digest"],
         "approved_step_ids": [s["step_id"] for s in green]},
        token=token,
    )
    check("approval bound to the plan digest",
          status == 201 and approval.get("plan_digest") == plan["digest"])

    status, job = request(
        f"{API}/v1/projects/{project_id}/repair-plans/{plan['plan_id']}/execute",
        "POST", token=token,
    )
    check("job dispatched", status == 202)
    job_id = job["job_id"]

    final = ""
    for _ in range(90):
        status, s = request(f"{API}/v1/projects/{project_id}/jobs/{job_id}", token=token)
        if isinstance(s, dict):
            final = s.get("state", "")
            if final in ("SUCCEEDED", "FAILED", "CANCELLED"):
                break
        time.sleep(10)
    check("worker completed", final == "SUCCEEDED", final)

    print("\nVALIDATION")
    status, packages = request(f"{API}/v1/projects/{project_id}/packages", token=token)
    verified = [p for p in packages if p["verified"]]
    for p in packages:
        state = "VERIFIED" if p["verified"] else p["state"]
        print(f"      {p['destination_id']}: {state}, "
              f"{p['requirements_satisfied']} requirements satisfied")
        for limitation in p["limitations"][:4]:
            print(f"        - {limitation[:110]}")

    check("at least one package reached VERIFIED", len(verified) >= 1,
          f"{len(verified)}/{len(packages)}")
    if not verified:
        return report()

    package = verified[0]
    check("verified package carries a hash", bool(package["package_sha256"]))
    check("verified package records its transformations",
          len(package["transformations"]) > 0,
          ", ".join(t["operation"] for t in package["transformations"]))

    print("\nPASSPORT")
    status, passport = request(f"{API}/v1/projects/{project_id}/passport", token=token)
    report_text = passport.get("report", "")
    check("passport generated", status == 200, passport.get("digest", ""))
    check("passport names the set-aside requirements", "set aside" in report_text)
    check("passport does not claim acceptance", "not a guarantee" in report_text.lower())

    print("\nDELIVERY ROOM")
    status, room = request(
        f"{API}/v1/projects/{project_id}/packages/{package['id']}/delivery-rooms",
        "POST", {"recipient_label": "Artdocfest programming", "expires_in_hours": 72},
        token=token,
    )
    check("delivery room created for the verified package",
          status == 201 and bool(room.get("url_token")))
    room_token = room.get("url_token")

    status, public = request(f"{API}/v1/delivery/{room_token}")
    check("recipient can open the delivery room", status == 200,
          f"{public.get('project_title')} -> {public.get('destination')}")

    blob = json.dumps(public).lower()
    leaked = [
        term for term in
        ("project_id", "owner", "storage_key", "bucket", "gs://", "originals/",
         "packages/", "token_hash", "sha256_key")
        if term in blob
    ]
    check("public response exposes nothing private", not leaked, str(leaked))
    check("public response carries what a recipient needs",
          bool(public.get("package_sha256")) and public.get("file_count", 0) > 0,
          f"{public.get('file_count')} files")

    status, download = request(f"{API}/v1/delivery/{room_token}/download-intent", "POST")
    check("recipient can request the package", status == 200 and bool(download.get("url")))

    status, _ = request(f"{API}/v1/delivery/{'z' * 43}")
    check("an invalid link is indistinguishable from a missing one", status == 404)

    status, _ = request(
        f"{API}/v1/projects/{project_id}/delivery-rooms/{room['room_id']}",
        "DELETE", token=token,
    )
    check("owner can revoke the link", status == 200)
    status, _ = request(f"{API}/v1/delivery/{room_token}")
    check("a revoked link stops working immediately", status == 404)

    print("\nFRONTEND")
    for path in ("/", "/projects", f"/projects/{project_id}/packages",
                 f"/projects/{project_id}/passport", f"/delivery/{room_token}"):
        status, _ = request(f"{WEB}{path}")
        check(f"web {path}", status == 200)

    return report()


def report() -> int:
    print("\n" + "=" * 70)
    failed = [k for k, v in results.items() if not v]
    print(f"{len(results) - len(failed)}/{len(results)} checks passed")
    for name in failed:
        print(f"  FAILED: {name}")
    print("=" * 70)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
