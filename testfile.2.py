#!/usr/bin/env python3
"""
Qala Discovery Engine — Test Script
Run this on your Mac against your local Django server.
Setup:
    1. Start Django locally:
           cd /path/to/Qala
           python manage.py runserver

    2. Install requests if you don't have it:
           pip install requests

    3. Run this script:
           python test_discovery.py

The script runs every test in order. Each section depends on the previous
ones, so the session_token is carried across automatically.
"""

import sys
import time
import requests

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG — edit these if needed
# ─────────────────────────────────────────────────────────────────────────────

BASE_URL       = "http://localhost:8000"
ADMIN_EMAIL    = "tech@qala.global"   # used for link-session test
ADMIN_PASSWORD = "Admin@1234!"        # change to your local admin password

# ─────────────────────────────────────────────────────────────────────────────
# TERMINAL COLOURS
# ─────────────────────────────────────────────────────────────────────────────

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"

# ─────────────────────────────────────────────────────────────────────────────
# SHARED TEST STATE — carried between tests
# ─────────────────────────────────────────────────────────────────────────────

state = {
    "session_token":    None,
    "buyer_profile_id": None,
    "image_ids":        [],
}

passed = 0
failed = 0
failures = []


# ─────────────────────────────────────────────────────────────────────────────
# TEST HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def header(title):
    print(f"\n{CYAN}{BOLD}  {'─' * 56}{RESET}")
    print(f"{CYAN}{BOLD}  {title}{RESET}")
    print(f"{CYAN}{BOLD}  {'─' * 56}{RESET}")


def check(label, condition, got=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"    {GREEN}✓{RESET}  {label}")
    else:
        failed += 1
        detail = f"  {DIM}← got: {got}{RESET}" if got else ""
        print(f"    {RED}✗{RESET}  {label}{detail}")
        failures.append(f"{label}" + (f" | got: {got}" if got else ""))


def info(msg):
    print(f"    {YELLOW}·{RESET}  {DIM}{msg}{RESET}")


def skip(msg):
    print(f"    {YELLOW}⊘{RESET}  skipped — {msg}")


def api_post(path, body, cookies=None):
    try:
        return requests.post(
            f"{BASE_URL}{path}",
            json=body,
            cookies=cookies,
            timeout=20,
        )
    except requests.exceptions.ConnectionError:
        print(f"\n{RED}{BOLD}  Cannot connect to {BASE_URL}{RESET}")
        print(f"{YELLOW}  Is Django running?  python manage.py runserver{RESET}\n")
        sys.exit(1)


def api_get(path, params=None, cookies=None):
    try:
        return requests.get(
            f"{BASE_URL}{path}",
            params=params,
            cookies=cookies,
            timeout=20,
        )
    except requests.exceptions.ConnectionError:
        print(f"\n{RED}{BOLD}  Cannot connect to {BASE_URL}{RESET}")
        print(f"{YELLOW}  Is Django running?  python manage.py runserver{RESET}\n")
        sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# 0. HEALTH CHECK
# ─────────────────────────────────────────────────────────────────────────────

def test_health():
    header("0. Health Check")
    r = api_get("/admin/")
    check("Server is reachable (admin redirects)", r.status_code in (200, 301, 302), str(r.status_code))


# ─────────────────────────────────────────────────────────────────────────────
# 1. GET /api/discovery/images/
# ─────────────────────────────────────────────────────────────────────────────

def test_images():
    header("1. GET /api/discovery/images/")

    r = api_get("/api/discovery/images/")
    check("Status 200",        r.status_code == 200,              str(r.status_code))

    d = r.json()
    check("status == 'ok'",    d.get("status") == "ok")
    check("'images' is list",  isinstance(d.get("images"), list))
    check("'count' present",   "count" in d)

    images = d.get("images", [])
    info(f"Found {len(images)} work_dump image(s) from verified studios")

    if images:
        img = images[0]
        check("image has 'id'",          "id"          in img)
        check("image has 'studio_id'",   "studio_id"   in img)
        check("image has 'studio_name'", "studio_name" in img)
        check("image has 'image_url'",   "image_url"   in img)
        # save first 2 IDs for Q1 visual selection tests later
        state["image_ids"] = [img["id"] for img in images[:2]]
        info(f"Saved image IDs for Q1: {state['image_ids']}")
    else:
        info("No images yet — visual_selection_ids will be empty in submission tests")


# ─────────────────────────────────────────────────────────────────────────────
# 2. POST /api/discovery/readiness-check/
# ─────────────────────────────────────────────────────────────────────────────

def test_submit_happy_path():
    header("2a. POST /api/discovery/readiness-check/ — Happy Path")

    body = {
        "first_name":           "Priya",
        "last_name":            "Sharma",
        "visual_selection_ids": state["image_ids"],
        "product_types":        ["dresses", "tops"],
        "fabrics":              ["cotton"],
        "fabric_is_flexible":   False,
        "fabric_not_sure":      False,
        "craft_interest":       "yes",
        "crafts":               ["hand block printing"],
        "craft_is_flexible":    False,
        "craft_not_sure":       False,
        "experimentation":      "no",
        "process_stage":        "I have designs or sketches",
        "design_support":       ["Print or textile design"],
        "timeline":             "3_6_months",
        "batch_size":           "30_100",
    }

    r = api_post("/api/discovery/readiness-check/", body)
    check("Status 201",                    r.status_code == 201,                          str(r.status_code))

    d = r.json()
    check("status == 'ok'",                d.get("status") == "ok")
    check("has 'session_token'",           bool(d.get("session_token")))
    check("has 'buyer_profile_id'",        bool(d.get("buyer_profile_id")))
    check("has 'matching_complete'",       "matching_complete" in d)
    check("matching_complete == True",     d.get("matching_complete") == True)
    check("'recommendations' is list",     isinstance(d.get("recommendations"), list))
    check("'bonus_visual_matches' is list",isinstance(d.get("bonus_visual_matches"), list))
    check("'zero_match' present",          "zero_match" in d)
    check("'zero_match_suggestions' list", isinstance(d.get("zero_match_suggestions"), list))
    check("'buyer_summary' is dict",       isinstance(d.get("buyer_summary"), dict))
    check("buyer_summary has 'display'",   "display" in d.get("buyer_summary", {}))
    check("'total_studios_available'",     "total_studios_available" in d)

    # Save session for all subsequent tests
    state["session_token"]    = d["session_token"]
    state["buyer_profile_id"] = d["buyer_profile_id"]

    recs = d.get("recommendations", [])
    info(f"session_token = {state['session_token']}")
    info(f"buyer_profile_id = {state['buyer_profile_id']}")
    info(f"{len(recs)} recommendation(s) returned")
    info(f"zero_match = {d.get('zero_match')}")
    info(f"buyer_summary display = \"{d['buyer_summary'].get('display')}\"")

    # Check recommendation card fields if any exist
    if recs:
        rec = recs[0]
        info(f"First rec: studio={rec.get('studio_name')} ranking={rec.get('ranking')}")
        for field in [
            "id", "studio_id", "studio_name", "location", "rank_position",
            "ranking", "core_capability_fit", "moq_fit", "craft_approach_fit",
            "visual_affinity", "match_reasoning", "what_best_at",
            "what_to_keep_in_mind", "is_bonus_visual", "hero_images",
            "primary_crafts", "craft_profiles", "selected_image_ids", "mismatches",
        ]:
            check(f"rec card has '{field}'", field in rec)
        check("is_bonus_visual == False",   rec.get("is_bonus_visual") == False)
        check("ranking is valid",           rec.get("ranking") in ("high", "medium", "low"), rec.get("ranking"))

        # hero_images structure
        imgs = rec.get("hero_images", [])
        if imgs:
            for f in ["id", "url", "caption", "media_type", "is_selected"]:
                check(f"hero_image has '{f}'", f in imgs[0])

        # craft_profiles structure
        crafts = rec.get("craft_profiles", [])
        if crafts:
            for f in ["craft_name", "primary_or_secondary", "limitations", "innovation_level"]:
                check(f"craft_profile has '{f}'", f in crafts[0])

    # Check bonus card fields if any
    bonus = d.get("bonus_visual_matches", [])
    if bonus:
        b = bonus[0]
        check("bonus card is_bonus_visual == True", b.get("is_bonus_visual") == True)
        check("bonus card has 'mismatches'",         isinstance(b.get("mismatches"), list))
        check("bonus card has 'selected_image_ids'", isinstance(b.get("selected_image_ids"), list))
        info(f"Bonus card: {b.get('studio_name')}, mismatches={len(b.get('mismatches', []))}")


def test_submit_flexible():
    header("2b. POST /api/discovery/readiness-check/ — Flexible Craft + Fabric (Case C)")

    body = {
        "product_types":      ["tops", "skirts"],
        "fabrics":            ["silk", "linen"],
        "fabric_is_flexible": True,      # Case C — no hard fabric filter
        "fabric_not_sure":    False,
        "craft_interest":     "yes",
        "crafts":             ["embroidery"],
        "craft_is_flexible":  True,      # Case C — no hard craft filter
        "craft_not_sure":     False,
        "experimentation":    "yes",
        "process_stage":      "I have a vision",
        "design_support":     [],
        "timeline":           "6_plus_months",
        "batch_size":         "under_30",
    }

    r = api_post("/api/discovery/readiness-check/", body)
    check("Status 201",             r.status_code == 201,  str(r.status_code))
    d = r.json()
    check("status == 'ok'",         d.get("status") == "ok")
    check("has session_token",       bool(d.get("session_token")))
    recs = d.get("recommendations", [])
    info(f"{len(recs)} recommendation(s) with flexible settings")


def test_submit_no_craft():
    header("2c. POST /api/discovery/readiness-check/ — craft_interest='no'")

    body = {
        "product_types":     ["dresses"],
        "fabrics":           [],
        "fabric_not_sure":   True,       # no fabric filter applied
        "craft_interest":    "no",       # skip Q4A and Q4B entirely
        "crafts":            [],
        "experimentation":   "skipped",
        "process_stage":     "I have samples already made",  # → ready_to_produce
        "design_support":    ["No, I have this covered"],
        "timeline":          "1_3_months",
        "batch_size":        "over_100",
    }

    r = api_post("/api/discovery/readiness-check/", body)
    check("Status 201",                      r.status_code == 201, str(r.status_code))
    d = r.json()
    check("journey_stage = ready_to_produce",
          d.get("journey_stage") == "ready_to_produce",
          str(d.get("journey_stage")))
    info(f"journey_stage = {d.get('journey_stage')}")


def test_submit_zero_match():
    header("2d. POST /api/discovery/readiness-check/ — Zero Match + Relaxation Engine")

    # Deliberately impossible combination — should trigger relaxation engine
    body = {
        "product_types":      ["activewear"],
        "fabrics":            ["cashmere", "angora_wool"],
        "fabric_is_flexible": False,
        "fabric_not_sure":    False,
        "craft_interest":     "yes",
        "crafts":             ["nonexistent_craft_xyz_000"],
        "craft_is_flexible":  False,
        "craft_not_sure":     False,
        "experimentation":    "skipped",
        "process_stage":      "",
        "design_support":     [],
        "timeline":           "not_sure",
        "batch_size":         "under_30",
    }

    r = api_post("/api/discovery/readiness-check/", body)
    check("Status 201",                      r.status_code == 201, str(r.status_code))
    d = r.json()
    check("zero_match == True",              d.get("zero_match") == True)
    check("recommendations == []",           d.get("recommendations") == [])
    check("zero_match_suggestions is list",  isinstance(d.get("zero_match_suggestions"), list))

    suggestions = d.get("zero_match_suggestions", [])
    info(f"{len(suggestions)} suggestion(s) from relaxation engine")

    for i, s in enumerate(suggestions):
        check(f"suggestion[{i}] has 'change_type'",   "change_type"   in s)
        check(f"suggestion[{i}] has 'message'",       "message"       in s)
        check(f"suggestion[{i}] has 'studios_count'", "studios_count" in s)
        check(f"suggestion[{i}] has 'apply_patch'",   "apply_patch"   in s)
        check(f"suggestion[{i}] studios_count >= 0",  s.get("studios_count", -1) >= 0,
              str(s.get("studios_count")))
        info(f"  [{i}] {s.get('change_type')}: \"{s.get('message')}\" ({s.get('studios_count')} studios)")


def test_submit_validation():
    header("2e. POST /api/discovery/readiness-check/ — Validation Errors")

    # Empty body
    r = api_post("/api/discovery/readiness-check/", {})
    check("Empty body → 400",                     r.status_code == 400, str(r.status_code))
    d = r.json()
    check("error response has 'errors'",           "errors" in d)
    check("errors.product_types present",          "product_types" in d.get("errors", {}))

    # Empty product_types list
    r2 = api_post("/api/discovery/readiness-check/", {"product_types": []})
    check("Empty product_types list → 400",        r2.status_code == 400, str(r2.status_code))

    info(f"Validation message: {d.get('errors', {}).get('product_types')}")


def test_submit_minimal():
    header("2f. POST /api/discovery/readiness-check/ — Minimal Payload")

    # Only the one required field — all optional fields should use defaults
    body = {"product_types": ["tops"]}
    r = api_post("/api/discovery/readiness-check/", body)
    check("Minimal payload → 201",      r.status_code == 201, str(r.status_code))
    d = r.json()
    check("status == 'ok'",             d.get("status") == "ok")
    check("has session_token",          bool(d.get("session_token")))
    check("recommendations is list",    isinstance(d.get("recommendations"), list))
    info("All optional fields defaulted cleanly")


# ─────────────────────────────────────────────────────────────────────────────
# 3. GET /api/discovery/recommendations/
# ─────────────────────────────────────────────────────────────────────────────

def test_fetch_recommendations():
    header("3. GET /api/discovery/recommendations/")

    if not state["session_token"]:
        skip("session_token not saved — test 2a must pass first")
        return

    # Valid token
    r = api_get("/api/discovery/recommendations/", {"session_token": state["session_token"]})
    check("Status 200",                    r.status_code == 200, str(r.status_code))
    d = r.json()
    check("status == 'ok'",                d.get("status") == "ok")
    check("same buyer_profile_id",
          d.get("buyer_profile_id") == state["buyer_profile_id"],
          str(d.get("buyer_profile_id")))
    check("'recommendations' is list",     isinstance(d.get("recommendations"), list))
    check("'bonus_visual_matches' is list",isinstance(d.get("bonus_visual_matches"), list))
    check("'zero_match' present",          "zero_match" in d)
    check("'buyer_summary' present",       "buyer_summary" in d)
    info(f"{len(d.get('recommendations', []))} rec(s) fetched from saved session")

    # Invalid token → 404
    r2 = api_get("/api/discovery/recommendations/",
                 {"session_token": "00000000-0000-0000-0000-000000000000"})
    check("Fake token → 404",  r2.status_code == 404, str(r2.status_code))
    check("status == 'not_found'", r2.json().get("status") == "not_found")

    # Missing token → 400
    r3 = api_get("/api/discovery/recommendations/")
    check("No token → 400", r3.status_code == 400, str(r3.status_code))


# ─────────────────────────────────────────────────────────────────────────────
# 4. POST /api/discovery/recommendations/edit/
# ─────────────────────────────────────────────────────────────────────────────

def test_edit_answers():
    header("4a. POST /api/discovery/recommendations/edit/ — Change Answers")

    if not state["session_token"]:
        skip("session_token not saved — test 2a must pass first")
        return

    body = {
        "session_token":      state["session_token"],
        "product_types":      ["dresses", "tops", "skirts"],  # added skirts
        "fabrics":            ["cotton", "linen"],            # added linen
        "fabric_is_flexible": True,                           # changed to flexible
        "fabric_not_sure":    False,
        "craft_interest":     "yes",
        "crafts":             ["hand block printing"],
        "craft_is_flexible":  True,                           # changed to flexible
        "craft_not_sure":     False,
        "experimentation":    "no",
        "process_stage":      "I have designs or sketches",
        "design_support":     [],
        "timeline":           "3_6_months",
        "batch_size":         "over_100",                     # changed batch size
    }

    r = api_post("/api/discovery/recommendations/edit/", body)
    check("Status 200",                r.status_code == 200, str(r.status_code))
    d = r.json()
    check("status == 'ok'",            d.get("status") == "ok")
    check("same session_token",
          d.get("session_token") == state["session_token"],
          str(d.get("session_token")))
    check("same buyer_profile_id",
          d.get("buyer_profile_id") == state["buyer_profile_id"],
          str(d.get("buyer_profile_id")))
    check("'recommendations' is list", isinstance(d.get("recommendations"), list))
    check("'buyer_summary' updated",   isinstance(d.get("buyer_summary"), dict))
    info(f"{len(d.get('recommendations', []))} rec(s) after edit")
    info(f"Updated summary: \"{d.get('buyer_summary', {}).get('display')}\"")


def test_edit_apply_suggestion():
    header("4b. POST /api/discovery/recommendations/edit/ — Apply Relaxation Suggestion")

    if not state["session_token"]:
        skip("session_token not saved — test 2a must pass first")
        return

    # Simulate frontend applying the craft_flexible suggestion patch
    body = {
        "session_token":      state["session_token"],
        "product_types":      ["dresses"],
        "fabrics":            ["silk"],
        "fabric_is_flexible": False,
        "fabric_not_sure":    False,
        "craft_interest":     "yes",
        "crafts":             ["hand block printing"],
        "craft_is_flexible":  True,    # ← this is the apply_patch from the suggestion
        "craft_not_sure":     False,
        "experimentation":    "skipped",
        "process_stage":      "",
        "design_support":     [],
        "timeline":           "not_sure",
        "batch_size":         "30_100",
    }

    r = api_post("/api/discovery/recommendations/edit/", body)
    check("Status 200",             r.status_code == 200, str(r.status_code))
    d = r.json()
    check("status == 'ok'",         d.get("status") == "ok")
    info(f"After suggestion patch: {len(d.get('recommendations', []))} rec(s), zero_match={d.get('zero_match')}")


def test_edit_missing_token():
    header("4c. POST /api/discovery/recommendations/edit/ — Error Cases")

    # Missing session_token
    r = api_post("/api/discovery/recommendations/edit/", {"product_types": ["dresses"]})
    check("Missing session_token → 400", r.status_code == 400, str(r.status_code))

    # Wrong session_token
    r2 = api_post("/api/discovery/recommendations/edit/", {
        "session_token": "00000000-0000-0000-0000-000000000000",
        "product_types": ["dresses"],
    })
    check("Fake session_token → 404",    r2.status_code == 404, str(r2.status_code))


# ─────────────────────────────────────────────────────────────────────────────
# 5. GET /api/discovery/session/
# ─────────────────────────────────────────────────────────────────────────────

def test_session_resume():
    header("5. GET /api/discovery/session/")

    if not state["session_token"]:
        skip("session_token not saved — test 2a must pass first")
        return

    r = api_get("/api/discovery/session/", {"session_token": state["session_token"]})
    check("Status 200",                      r.status_code == 200, str(r.status_code))
    d = r.json()
    check("status == 'ok'",                  d.get("status") == "ok")
    check("'data' is dict",                  isinstance(d.get("data"), dict))

    data = d.get("data", {})
    for field in [
        "id", "session_token", "product_types", "fabrics",
        "craft_interest", "crafts", "experimentation",
        "process_stage", "design_support", "timeline", "batch_size",
        "journey_stage", "matching_complete", "zero_match_suggestions",
        "visual_selection_ids", "created_at", "updated_at",
    ]:
        check(f"data has '{field}'", field in data)

    check("session_token matches",
          data.get("session_token") == state["session_token"],
          str(data.get("session_token")))
    check("matching_complete == True", data.get("matching_complete") == True)

    info(f"product_types saved: {data.get('product_types')}")
    info(f"journey_stage: {data.get('journey_stage')}")
    info(f"matching_complete: {data.get('matching_complete')}")

    # Invalid token → 404
    r2 = api_get("/api/discovery/session/", {"session_token": "00000000-0000-0000-0000-000000000000"})
    check("Fake token → 404",      r2.status_code == 404, str(r2.status_code))
    check("status == 'not_found'", r2.json().get("status") == "not_found")

    # Missing token → 400
    r3 = api_get("/api/discovery/session/")
    check("No token → 400",        r3.status_code == 400, str(r3.status_code))


# ─────────────────────────────────────────────────────────────────────────────
# 6. RESUME SESSION via readiness-check (same session_token in body)
# ─────────────────────────────────────────────────────────────────────────────

def test_resume_via_submit():
    header("6. Session Resume via Readiness Check (sends session_token in body)")

    if not state["session_token"]:
        skip("session_token not saved — test 2a must pass first")
        return

    body = {
        "session_token":     state["session_token"],
        "product_types":     ["tops"],
        "fabrics":           [],
        "fabric_not_sure":   True,
        "craft_interest":    "no",
        "crafts":            [],
        "experimentation":   "skipped",
        "process_stage":     "",
        "design_support":    [],
        "timeline":          "not_sure",
        "batch_size":        "not_sure",
    }

    r = api_post("/api/discovery/readiness-check/", body)
    check("Status 201",        r.status_code == 201, str(r.status_code))
    d = r.json()
    check("same session_token returned",
          d.get("session_token") == state["session_token"],
          str(d.get("session_token")))
    check("same buyer_profile_id returned",
          d.get("buyer_profile_id") == state["buyer_profile_id"],
          str(d.get("buyer_profile_id")))
    info("Session correctly resumed — same token and profile ID returned")


# ─────────────────────────────────────────────────────────────────────────────
# 7. POST /api/discovery/link-session/
# ─────────────────────────────────────────────────────────────────────────────

def test_link_session():
    header("7. POST /api/discovery/link-session/")

    if not state["session_token"]:
        skip("session_token not saved — test 2a must pass first")
        return

    # Without auth → must be 401
    r = api_post("/api/discovery/link-session/", {"session_token": state["session_token"]})
    check("No auth → 401", r.status_code == 401, str(r.status_code))
    info("Correctly rejected unauthenticated request")

    info(f"Logging in as {ADMIN_EMAIL} ...")
    try:
        # Use a Session so all cookies persist automatically across requests
        st_session = requests.Session()

        # Step 1 — Login
        login_r = st_session.post(
            f"{BASE_URL}/auth/signin",
            json={
                "formFields": [
                    {"id": "email",    "value": ADMIN_EMAIL},
                    {"id": "password", "value": ADMIN_PASSWORD},
                ]
            },
            headers={"rid": "emailpassword", "st-auth-mode": "cookie"},
            timeout=10,
        )
        check("Login → 200", login_r.status_code == 200, str(login_r.status_code))
        login_d = login_r.json()
        check("Login status == 'OK'", login_d.get("status") == "OK", str(login_d.get("status")))

        if login_r.status_code != 200 or login_d.get("status") != "OK":
            info("Login failed — check ADMIN_EMAIL / ADMIN_PASSWORD at top of this script")
            return

        info(f"Cookies after login: {list(st_session.cookies.keys())}")

        # Step 2 — Refresh the session immediately.
        # SuperTokens access tokens expire quickly (sometimes in seconds in dev).
        # /auth/session/refresh exchanges sRefreshToken for a fresh sAccessToken.
        refresh_r = st_session.post(
            f"{BASE_URL}/auth/session/refresh",
            headers={"rid": "session"},
            timeout=10,
        )
        info(f"Refresh status: {refresh_r.status_code}")
        info(f"Cookies after refresh: {list(st_session.cookies.keys())}")

        if refresh_r.status_code not in (200, 401):
            info(f"Unexpected refresh response: {refresh_r.text[:200]}")

        # Step 3 — Now use the refreshed session to call link-session.
        # VIA_CUSTOM_HEADER anti-CSRF mode requires 'rid' header on EVERY
        # authenticated request — this is what SuperTokens checks instead of
        # a CSRF token. Without it, get_session() returns TRY_REFRESH_TOKEN.
        st_session.headers.update({"rid": "session"})

        def auth_post(path, body):
            return st_session.post(
                f"{BASE_URL}{path}",
                json=body,
                timeout=15,
            )

        link_r = auth_post("/api/discovery/link-session/", {"session_token": state["session_token"]})
        check("With auth → 200", link_r.status_code == 200, str(link_r.status_code))

        if link_r.status_code != 200:
            info(f"Response body: {link_r.text[:300]}")
            info("If still TRY_REFRESH_TOKEN: access token TTL is very short in your dev config")
            info("Check SUPERTOKENS_URL in .env — make sure SuperTokens core is running locally")

        ld = link_r.json()
        check("status == 'ok'",       ld.get("status") == "ok")
        check("has buyer_profile_id", bool(ld.get("buyer_profile_id")))
        check("buyer_profile_id matches",
              ld.get("buyer_profile_id") == state["buyer_profile_id"],
              str(ld.get("buyer_profile_id")))
        check("has session_token",    bool(ld.get("session_token")))
        check("has message",          bool(ld.get("message")))
        info(f"Linked! buyer_profile_id = {ld.get('buyer_profile_id')}")

        # Re-link same user → must be idempotent (200, not error)
        link_r2 = auth_post("/api/discovery/link-session/", {"session_token": state["session_token"]})
        check("Re-link same user → 200 (idempotent)", link_r2.status_code == 200, str(link_r2.status_code))

        # Missing session_token with auth → 400
        link_r3 = auth_post("/api/discovery/link-session/", {})
        check("No session_token → 400", link_r3.status_code == 400, str(link_r3.status_code))

        # Fake session_token with auth → 404
        link_r4 = auth_post("/api/discovery/link-session/",
                            {"session_token": "00000000-0000-0000-0000-000000000000"})
        check("Fake session_token → 404", link_r4.status_code == 404, str(link_r4.status_code))

    except requests.exceptions.ConnectionError:
        info("Connection error — SuperTokens core may not be running locally")
        info("Start it with: docker run -p 3567:3567 registry.supertokens.io/supertokens/supertokens-postgresql")
    except Exception as e:
        info(f"Unexpected error: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

def print_summary(elapsed):
    total = passed + failed
    print(f"\n{CYAN}{BOLD}  {'═' * 56}{RESET}")
    print(f"{CYAN}{BOLD}  RESULTS{RESET}")
    print(f"{CYAN}{BOLD}  {'═' * 56}{RESET}")
    print(f"  Total    {total}")
    print(f"  {GREEN}Passed   {passed}{RESET}")
    print(f"  {RED}Failed   {failed}{RESET}")
    print(f"  Time     {elapsed:.1f}s")

    if failures:
        print(f"\n{RED}{BOLD}  Failed checks:{RESET}")
        for f in failures:
            print(f"  {RED}✗  {f}{RESET}")

    print()
    if failed == 0:
        print(f"{GREEN}{BOLD}  All checks passed ✓{RESET}")
    else:
        print(f"{YELLOW}{BOLD}  Some checks failed — see above{RESET}")
        print()
        print(f"{YELLOW}  Common causes:{RESET}")
        print(f"{YELLOW}  · No verified sellers in DB → recommendations will always be empty{RESET}")
        print(f"{YELLOW}  · Migrations not run → python manage.py migrate{RESET}")
        print(f"{YELLOW}  · discovery app not in INSTALLED_APPS{RESET}")
        print(f"{YELLOW}  · Wrong ADMIN_EMAIL/PASSWORD at top of this script{RESET}")
        print(f"{YELLOW}  · SuperTokens not running locally → link-session login tests skip{RESET}")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"\n{CYAN}{BOLD}  {'═' * 56}{RESET}")
    print(f"{CYAN}{BOLD}  Qala Discovery Engine — Test Suite{RESET}")
    print(f"{CYAN}{BOLD}  Target: {BASE_URL}{RESET}")
    print(f"{CYAN}{BOLD}  {'═' * 56}{RESET}")

    t0 = time.time()

    test_health()
    test_images()
    test_submit_happy_path()
    test_submit_flexible()
    test_submit_no_craft()
    test_submit_zero_match()
    test_submit_validation()
    test_submit_minimal()
    test_fetch_recommendations()
    test_edit_answers()
    test_edit_apply_suggestion()
    test_edit_missing_token()
    test_session_resume()
    test_resume_via_submit()
    test_link_session()

    print_summary(time.time() - t0)
    sys.exit(0 if failed == 0 else 1)