"""
Qala Backend — Full API Test Suite
Run with: python test_all_apis.py
Make sure Django server is running on http://127.0.0.1:8000
"""
import requests
import json
import sys

BASE = "http://127.0.0.1:8000"
VM_IP = "34.169.72.66"
API_KEY = "70031101955ba2c956c9f6dd5469fa65a85bc91d"

# ─── Colours ────────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

passed = []
failed = []

def ok(name):
    passed.append(name)
    print(f"  {GREEN}✅ PASS{RESET} — {name}")

def fail(name, reason):
    failed.append(name)
    print(f"  {RED}❌ FAIL{RESET} — {name}")
    print(f"         {YELLOW}{reason}{RESET}")

def section(title):
    print(f"\n{BOLD}{BLUE}{'─'*60}{RESET}")
    print(f"{BOLD}{BLUE}  {title}{RESET}")
    print(f"{BOLD}{BLUE}{'─'*60}{RESET}")

def check(name, resp, expected_status, check_fn=None):
    try:
        if resp.status_code != expected_status:
            fail(name, f"Expected {expected_status}, got {resp.status_code} — {resp.text[:300]}")
            return None
        data = resp.json() if resp.text else {}
        if check_fn:
            result = check_fn(data)
            if result is not True:
                fail(name, result or "check failed")
                return None
        ok(name)
        return data
    except Exception as e:
        fail(name, str(e))
        return None

# ─── State ──────────────────────────────────────────────────────────────────
state = {}

def auth_headers(token):
    return {"authorization": f"Bearer {token}", "Content-Type": "application/json"}

def st_headers():
    return {"Content-Type": "application/json", "rid": "emailpassword"}

# ════════════════════════════════════════════════════════════════════════════
section("PHASE 1 — Customer Auth")
# ════════════════════════════════════════════════════════════════════════════

# 1. Customer Signup (ignore EMAIL_ALREADY_EXISTS)
r = requests.post(f"{BASE}/auth/signup", headers=st_headers(), json={
    "formFields": [
        {"id": "email",    "value": "customer1@test.com"},
        {"id": "password", "value": "Test1234!"}
    ]
})
if r.status_code == 200 and r.json().get("status") in ("OK", "EMAIL_ALREADY_EXISTS_ERROR"):
    ok("1. Customer Signup")
else:
    fail("1. Customer Signup", f"{r.status_code} — {r.text[:200]}")

# 2. Customer Signin
r = requests.post(f"{BASE}/auth/signin", headers=st_headers(), json={
    "formFields": [
        {"id": "email",    "value": "customer1@test.com"},
        {"id": "password", "value": "Test1234!"}
    ]
})
data = check("2. Customer Signin", r, 200, lambda d: True if d.get("status") == "OK" else f"status={d.get('status')}")
if data:
    state["customer_token"] = r.headers.get("st-access-token", "")
    if not state["customer_token"]:
        fail("2a. Customer Token in Header", "st-access-token header missing")
    else:
        ok("2a. Customer Token in Header")

# 3. GET /api/me/ as customer
if state.get("customer_token"):
    r = requests.get(f"{BASE}/api/me/", headers={"authorization": f"Bearer {state['customer_token']}"})
    data = check("3. GET /api/me/ (customer)", r, 200, lambda d: True if d.get("role") == "customer" else f"role={d.get('role')}")

# 4. GET /api/me/customer/
if state.get("customer_token"):
    r = requests.get(f"{BASE}/api/me/customer/", headers={"authorization": f"Bearer {state['customer_token']}"})
    check("4. GET /api/me/customer/", r, 200, lambda d: True if "email" in d or "full_name" in d else f"unexpected: {d}")

# ════════════════════════════════════════════════════════════════════════════
section("PHASE 2 — Admin Signin + Create Seller")
# ════════════════════════════════════════════════════════════════════════════

# 5. Admin Signin
r = requests.post(f"{BASE}/auth/signin", headers=st_headers(), json={
    "formFields": [
        {"id": "email",    "value": "sankalpgupta444@gmail.com"},
        {"id": "password", "value": "Admin1234!"}
    ]
})
data = check("5. Admin Signin", r, 200, lambda d: True if d.get("status") == "OK" else f"status={d.get('status')}")
if data:
    state["admin_token"] = r.headers.get("st-access-token", "")
    if not state["admin_token"]:
        fail("5a. Admin Token", "st-access-token header missing")
    else:
        ok("5a. Admin Token in Header")

# 6. GET /api/me/ as admin
if state.get("admin_token"):
    r = requests.get(f"{BASE}/api/me/", headers={"authorization": f"Bearer {state['admin_token']}"})
    check("6. GET /api/me/ (admin)", r, 200, lambda d: True if d.get("role") == "admin" else f"role={d.get('role')} — admin SuperTokens ID may not match Django user")

# 7. Admin Create Seller
if state.get("admin_token"):
    r = requests.post(f"{BASE}/api/admin/sellers/", headers=auth_headers(state["admin_token"]), json={
        "email":                "seller1@test.com",
        "password":             "Seller1234!",
        "business_name":        "Craft Studio by Priya",
        "business_email":       "studio@priya.com",
        "initial_profile_name": "Main Store"
    })
    data = check("7. Admin Create Seller", r, 201, lambda d: True if "profiles" in d else f"missing profiles key: {list(d.keys())}")
    if data and data.get("profiles"):
        state["seller_profile_id"] = str(data["profiles"][0]["id"])
        ok(f"7a. seller_profile_id captured: {state['seller_profile_id']}")

# 8. Seller Signin
r = requests.post(f"{BASE}/auth/signin", headers=st_headers(), json={
    "formFields": [
        {"id": "email",    "value": "seller1@test.com"},
        {"id": "password", "value": "Seller1234!"}
    ]
})
data = check("8. Seller Signin", r, 200, lambda d: True if d.get("status") == "OK" else f"status={d.get('status')}")
if data:
    state["seller_token"] = r.headers.get("st-access-token", "")
    if not state["seller_token"]:
        fail("8a. Seller Token", "st-access-token header missing")
    else:
        ok("8a. Seller Token in Header")

# 9. GET /api/me/ as seller
if state.get("seller_token"):
    r = requests.get(f"{BASE}/api/me/", headers={"authorization": f"Bearer {state['seller_token']}"})
    data = check("9. GET /api/me/ (seller)", r, 200, lambda d: True if d.get("role") == "seller" else f"role={d.get('role')}")
    if data and data.get("profiles") and not state.get("seller_profile_id"):
        state["seller_profile_id"] = str(data["profiles"][0]["id"])

# ════════════════════════════════════════════════════════════════════════════
section("PHASE 3 — Onboarding Snapshot + Section A (Studio)")
# ════════════════════════════════════════════════════════════════════════════

def seller_headers():
    h = {"authorization": f"Bearer {state.get('seller_token','')}", "Content-Type": "application/json"}
    if state.get("seller_profile_id"):
        h["X-Profile-Id"] = state["seller_profile_id"]
    return h

if state.get("seller_token"):

    # 10. GET full onboarding snapshot (empty)
    r = requests.get(f"{BASE}/api/seller/onboarding/", headers=seller_headers())
    check("10. GET Onboarding Snapshot (empty)", r, 200,
          lambda d: True if "status" in d else f"missing 'status' key: {list(d.keys())}")

    # 11. PUT Studio Details
    r = requests.put(f"{BASE}/api/seller/onboarding/studio/", headers=seller_headers(), json={
        "studio_name":       "Priya Craft Studio",
        "location_city":     "Jaipur",
        "location_state":    "Rajasthan",
        "years_in_operation": 5.5,
        "website_url":       "https://priyacraft.com",
        "instagram_url":     "https://instagram.com/priyacraft",
        "poc_working_style": "I prefer detailed briefs upfront and weekly check-ins."
    })
    check("11. PUT Studio Details", r, 200,
          lambda d: True if d.get("studio_name") == "Priya Craft Studio" else f"studio_name={d.get('studio_name')}")

    # 12. GET Studio Details
    r = requests.get(f"{BASE}/api/seller/onboarding/studio/", headers=seller_headers())
    check("12. GET Studio Details", r, 200,
          lambda d: True if d.get("location_city") == "Jaipur" else f"location_city={d.get('location_city')}")

    # 13. PATCH Studio Details (autosave)
    r = requests.patch(f"{BASE}/api/seller/onboarding/studio/", headers=seller_headers(),
                       json={"years_in_operation": 6})
    check("13. PATCH Studio Details (autosave)", r, 200)

    # 14. POST Studio Contact
    r = requests.post(f"{BASE}/api/seller/onboarding/studio/contacts/", headers=seller_headers(), json={
        "name": "Priya Sharma", "role": "Founder",
        "email": "priya@priyacraft.com", "phone": "+919876543210", "order": 1
    })
    data = check("14. POST Studio Contact", r, 201, lambda d: True if "id" in d else "missing id")
    if data:
        state["contact_id"] = str(data["id"])

    # 15. PUT Studio USPs
    r = requests.put(f"{BASE}/api/seller/onboarding/studio/usps/", headers=seller_headers(), json=[
        {"order": 1, "strength": "Specialise in natural dyes and hand block printing"},
        {"order": 2, "strength": "5+ years working with luxury fashion brands"},
        {"order": 3, "strength": "Flexible MOQ from 30 pieces per style"}
    ])
    check("15. PUT Studio USPs (3 items)", r, 200,
          lambda d: True if isinstance(d, list) and len(d) == 3 else f"expected list of 3, got {d}")

    # 16. DELETE Studio Contact
    if state.get("contact_id"):
        r = requests.delete(
            f"{BASE}/api/seller/onboarding/studio/contacts/{state['contact_id']}/",
            headers=seller_headers()
        )
        check("16. DELETE Studio Contact", r, 204)

# ════════════════════════════════════════════════════════════════════════════
section("PHASE 4 — Section B (Products + Fabrics + Brands + Awards)")
# ════════════════════════════════════════════════════════════════════════════

if state.get("seller_token"):

    # 17. PUT Product Types
    r = requests.put(f"{BASE}/api/seller/onboarding/products/", headers=seller_headers(), json={
        "dresses": True, "tops": True, "tunics_kurtas": True,
        "coord_sets": True, "kaftans": True
    })
    check("17. PUT Product Types", r, 200,
          lambda d: True if d.get("dresses") is True else f"dresses={d.get('dresses')}")

    # 18. PUT Fabric Answers (bulk)
    r = requests.put(f"{BASE}/api/seller/onboarding/fabrics/", headers=seller_headers(), json=[
        {"category": "cotton", "fabric_name": "Mulmul",       "works_with": True, "is_primary": True,  "innovation_note": "Hand-spun from Rajasthan weavers"},
        {"category": "cotton", "fabric_name": "Cambric",      "works_with": True, "is_primary": False, "innovation_note": None},
        {"category": "silk",   "fabric_name": "Chanderi Silk","works_with": True, "is_primary": True,  "innovation_note": "Natural dye experiments"}
    ])
    check("18. PUT Fabric Answers (bulk)", r, 200,
          lambda d: True if isinstance(d, list) and len(d) >= 2 else f"expected list, got {d}")

    # 19. POST Brand Experience
    r = requests.post(f"{BASE}/api/seller/onboarding/brands/", headers=seller_headers(), json={
        "brand_name": "Good Earth",
        "scope":      "200 units of hand-block printed kurtas for Festive 2023",
        "order":      1
    })
    data = check("19. POST Brand Experience", r, 201, lambda d: True if "id" in d else "missing id")
    if data:
        state["brand_id"] = str(data["id"])

    # 20. PATCH Brand Experience
    if state.get("brand_id"):
        r = requests.patch(
            f"{BASE}/api/seller/onboarding/brands/{state['brand_id']}/",
            headers=seller_headers(),
            json={"scope": "Updated: 300 units for Festive 2023 collection"}
        )
        check("20. PATCH Brand Experience", r, 200)

    # 21. POST Award Mention
    r = requests.post(f"{BASE}/api/seller/onboarding/awards/", headers=seller_headers(), json={
        "award_name": "Best Sustainable Craft Studio — Vogue India 2023",
        "link":       "https://vogue.in/awards/2023",
        "order":      1
    })
    data = check("21. POST Award Mention", r, 201, lambda d: True if "id" in d else "missing id")
    if data:
        state["award_id"] = str(data["id"])

# ════════════════════════════════════════════════════════════════════════════
section("PHASE 5 — Section C (Crafts)")
# ════════════════════════════════════════════════════════════════════════════

if state.get("seller_token"):

    # 22. POST Craft Detail
    r = requests.post(f"{BASE}/api/seller/onboarding/crafts/", headers=seller_headers(), json={
        "craft_name":                          "Hand Block Printing",
        "specialization":                      "Dabu and Bagru resist printing on natural fabrics",
        "is_primary":                          True,
        "innovation_level":                    "high",
        "limitations":                         "Not suitable for synthetic blends",
        "sampling_time_weeks":                 2.0,
        "production_timeline_months_50units":  1.5,
        "delay_likelihood":                    "low",
        "delay_common_reasons":                "Occasional monsoon delays in drying",
        "order":                               1
    })
    data = check("22. POST Craft Detail", r, 201, lambda d: True if "id" in d else "missing id")
    if data:
        state["craft_id"] = str(data["id"])

    # 23. PATCH Craft Detail
    if state.get("craft_id"):
        r = requests.patch(
            f"{BASE}/api/seller/onboarding/crafts/{state['craft_id']}/",
            headers=seller_headers(),
            json={"sampling_time_weeks": 2.5}
        )
        check("23. PATCH Craft Detail", r, 200,
              lambda d: True if str(d.get("sampling_time_weeks")) == "2.5" else f"sampling_time_weeks={d.get('sampling_time_weeks')}")

    # 24. GET Crafts List
    r = requests.get(f"{BASE}/api/seller/onboarding/crafts/", headers=seller_headers())
    check("24. GET Crafts List", r, 200,
          lambda d: True if isinstance(d, list) and len(d) >= 1 else f"expected non-empty list, got {d}")

    # 25. POST Submit Section C
    r = requests.post(f"{BASE}/api/seller/onboarding/crafts/submit/", headers=seller_headers())
    check("25. POST Submit Section C", r, 200,
          lambda d: True if "submitted" in str(d).lower() else f"unexpected: {d}")

# ════════════════════════════════════════════════════════════════════════════
section("PHASE 6 — Sections D, E, F")
# ════════════════════════════════════════════════════════════════════════════

if state.get("seller_token"):

    # 26. PUT Collab Design
    r = requests.put(f"{BASE}/api/seller/onboarding/collab/", headers=seller_headers(), json={
        "has_fashion_designer":         True,
        "can_develop_from_references":  True,
        "max_sampling_iterations":      3
    })
    check("26. PUT Collab Design (Section D)", r, 200)

    # 27. PUT Buyer Requirements
    r = requests.put(f"{BASE}/api/seller/onboarding/collab/buyer-requirements/", headers=seller_headers(), json=[
        {"order": 1, "question": "What is your target retail price point per garment?"},
        {"order": 2, "question": "Do you have existing tech packs or only mood boards?"}
    ])
    check("27. PUT Buyer Requirements", r, 200,
          lambda d: True if isinstance(d, list) and len(d) == 2 else f"expected 2 items, got {d}")

    # 28. PUT Production Scale
    r = requests.put(f"{BASE}/api/seller/onboarding/production/", headers=seller_headers(), json={
        "monthly_capacity_units": 500,
        "has_strict_minimums":    True
    })
    check("28. PUT Production Scale (Section E)", r, 200)

    # 29. PUT MOQ Entries
    r = requests.put(f"{BASE}/api/seller/onboarding/production/moq/", headers=seller_headers(), json=[
        {"order": 1, "craft_or_category": "Hand Block Printing", "moq_condition": "Min 30 pieces per colorway"},
        {"order": 2, "craft_or_category": "Embroidery",          "moq_condition": "Min 50 pieces per design"}
    ])
    check("29. PUT MOQ Entries", r, 200,
          lambda d: True if isinstance(d, list) and len(d) == 2 else f"expected 2 items, got {d}")

    # 30. PUT Process Readiness
    r = requests.put(f"{BASE}/api/seller/onboarding/process/", headers=seller_headers(), json={
        "production_steps": "1. Design brief\n2. Fabric sourcing\n3. Sampling\n4. Approval\n5. Bulk production\n6. QC\n7. Dispatch"
    })
    check("30. PUT Process Readiness (Section F)", r, 200)

    # 31. GET Process Readiness
    r = requests.get(f"{BASE}/api/seller/onboarding/process/", headers=seller_headers())
    check("31. GET Process Readiness", r, 200,
          lambda d: True if d.get("production_steps") else "production_steps missing")

# ════════════════════════════════════════════════════════════════════════════
section("PHASE 7 — Admin Flag + Resolve")
# ════════════════════════════════════════════════════════════════════════════

if state.get("admin_token") and state.get("seller_profile_id"):
    pid = state["seller_profile_id"]

    # 32. GET Admin Seller Profiles List
    r = requests.get(f"{BASE}/api/admin/seller-profiles/",
                     headers={"authorization": f"Bearer {state['admin_token']}"})
    check("32. GET Admin Seller Profiles List", r, 200,
          lambda d: True if isinstance(d, list) and len(d) >= 1 else f"expected list, got {d}")

    # 33. GET Admin Full Onboarding View
    r = requests.get(f"{BASE}/api/admin/seller-profiles/{pid}/onboarding/",
                     headers={"authorization": f"Bearer {state['admin_token']}"})
    check("33. GET Admin Full Onboarding View", r, 200,
          lambda d: True if "studio_details" in d else f"missing studio_details: {list(d.keys())}")

    # 34. POST Admin Flag a field
    r = requests.post(
        f"{BASE}/api/admin/seller-profiles/{pid}/flag/",
        headers={"authorization": f"Bearer {state['admin_token']}", "Content-Type": "application/json"},
        json={
            "model":  "studio_details",
            "field":  "studio_name",
            "reason": "Please provide your actual registered business name."
        }
    )
    check("34. POST Admin Flag Field", r, 200,
          lambda d: True if d.get("status") == "flagged" else f"status={d.get('status')}")

    # 35. GET Seller Flag Summary (should have 1 flag)
    r = requests.get(f"{BASE}/api/seller/onboarding/flags/", headers=seller_headers())
    check("35. GET Seller Flag Summary (1 flag)", r, 200,
          lambda d: True if d.get("total_flags", 0) >= 1 else f"total_flags={d.get('total_flags')} — expected >= 1")

    # 36. POST Admin Resolve Flag
    r = requests.post(
        f"{BASE}/api/admin/seller-profiles/{pid}/resolve-flag/",
        headers={"authorization": f"Bearer {state['admin_token']}", "Content-Type": "application/json"},
        json={"model": "studio_details", "field": "studio_name"}
    )
    check("36. POST Admin Resolve Flag", r, 200,
          lambda d: True if d.get("status") == "resolved" else f"status={d.get('status')}")

    # 37. GET Seller Flag Summary (should be 0 now)
    r = requests.get(f"{BASE}/api/seller/onboarding/flags/", headers=seller_headers())
    check("37. GET Seller Flag Summary (0 flags)", r, 200,
          lambda d: True if d.get("total_flags", 1) == 0 else f"total_flags={d.get('total_flags')} — expected 0")

# ════════════════════════════════════════════════════════════════════════════
section("PHASE 8 — Final Snapshot")
# ════════════════════════════════════════════════════════════════════════════

if state.get("seller_token"):

    # 38. GET Full Onboarding Snapshot (populated)
    r = requests.get(f"{BASE}/api/seller/onboarding/", headers=seller_headers())
    data = check("38. GET Full Onboarding Snapshot (final)", r, 200,
                 lambda d: True if d.get("studio_details") and d.get("crafts") else
                 f"missing data — studio_details={bool(d.get('studio_details'))} crafts={bool(d.get('crafts'))}")
    if data and data.get("status"):
        pct = data["status"].get("completion_percentage", 0)
        print(f"  {BLUE}📊 Completion: {pct}%{RESET}")
        sections = {
            "A (Studio)":     data["status"].get("section_a_status"),
            "B (Products)":   data["status"].get("section_b_status"),
            "C (Crafts)":     data["status"].get("section_c_status"),
            "D (Collab)":     data["status"].get("section_d_status"),
            "E (Production)": data["status"].get("section_e_status"),
            "F (Process)":    data["status"].get("section_f_status"),
        }
        for sec, status in sections.items():
            icon = "✅" if status == "submitted" else "🔄" if status == "in_progress" else "⬜"
            print(f"     {icon} Section {sec}: {status}")

    # 39. Seller Profile Switch
    r = requests.get(f"{BASE}/api/seller/profiles/", headers={"authorization": f"Bearer {state.get('seller_token','')}"})
    check("39. GET Seller Profile List", r, 200,
          lambda d: True if isinstance(d, list) else f"expected list, got {type(d)}")

# ════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ════════════════════════════════════════════════════════════════════════════
print(f"\n{BOLD}{'═'*60}{RESET}")
print(f"{BOLD}  TEST SUMMARY{RESET}")
print(f"{BOLD}{'═'*60}{RESET}")
print(f"  {GREEN}Passed: {len(passed)}{RESET}")
print(f"  {RED}Failed: {len(failed)}{RESET}")
print(f"  Total:  {len(passed) + len(failed)}")
if failed:
    print(f"\n{RED}  Failed tests:{RESET}")
    for f in failed:
        print(f"    • {f}")
print(f"{BOLD}{'═'*60}{RESET}\n")

sys.exit(0 if not failed else 1)