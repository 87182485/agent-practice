#!/usr/bin/env bash
# Milestone 3 smoke test — registration, login, and the ownership boundary.
#
# Usage:
#   rm bookmarks.db && uvicorn milestone_3:app --reload   # in another terminal
#   chmod +x smoke_test.sh && ./smoke_test.sh
#
# Expects a clean database. Needs `jq` for token extraction:
#   sudo apt install jq

set -u
API="${API:-http://127.0.0.1:8000}"

pass() { echo "  PASS  $1"; }
fail() { echo "  FAIL  $1"; }

check() {  # check <expected_code> <actual_code> <label>
  if [ "$1" = "$2" ]; then pass "$3 ($2)"; else fail "$3 (got $2, wanted $1)"; fi
}

echo
echo "=== 1. Registration ==="

code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$API/users" \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"alice-dev-pw"}')
check 201 "$code" "register alice"

code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$API/users" \
  -H "Content-Type: application/json" \
  -d '{"username":"bob","password":"bob-dev-pw"}')
check 201 "$code" "register bob"

# Duplicate username -> unique constraint -> 409
code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$API/users" \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"whatever"}')
check 409 "$code" "duplicate username rejected"

# The response must never contain the hash.
body=$(curl -s -X POST "$API/users" \
  -H "Content-Type: application/json" \
  -d '{"username":"leakcheck","password":"x"}')
if echo "$body" | grep -q "hashed_password\|argon2"; then
  fail "LEAK: response body contains the password hash -> check response_model=UserRead"
else
  pass "no password hash in response body"
fi

echo
echo "=== 2. Login (form-encoded, NOT json) ==="

# OAuth2 password flow posts FORM data — note there is no JSON header here.
ALICE=$(curl -s -X POST "$API/token" \
  -d "username=alice&password=alice-dev-pw" | jq -r '.access_token')
BOB=$(curl -s -X POST "$API/token" \
  -d "username=bob&password=bob-dev-pw" | jq -r '.access_token')

if [ -n "$ALICE" ] && [ "$ALICE" != "null" ]; then
  pass "alice got a token"
else
  fail "alice login failed — is POST /token implemented?"; exit 1
fi
[ -n "$BOB" ] && [ "$BOB" != "null" ] && pass "bob got a token" || fail "bob login failed"

# Wrong password and unknown user must look IDENTICAL (no user enumeration).
c1=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$API/token" -d "username=alice&password=wrong")
c2=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$API/token" -d "username=ghost&password=wrong")
check 401 "$c1" "wrong password rejected"
check 401 "$c2" "unknown user rejected"
m1=$(curl -s -X POST "$API/token" -d "username=alice&password=wrong" | jq -r '.detail')
m2=$(curl -s -X POST "$API/token" -d "username=ghost&password=wrong" | jq -r '.detail')
if [ "$m1" = "$m2" ]; then
  pass "identical error message for both (no user enumeration)"
else
  fail "DIFFERENT messages leak which usernames exist: '$m1' vs '$m2'"
fi

echo
echo "=== 3. Auth required ==="

code=$(curl -s -o /dev/null -w '%{http_code}' "$API/bookmarks")
check 401 "$code" "no token -> 401"

code=$(curl -s -o /dev/null -w '%{http_code}' "$API/bookmarks" -H "Authorization: Bearer garbage")
check 401 "$code" "bad token -> 401"

echo
echo "=== 4. Bookmarks, scoped per user ==="

A_ID=$(curl -s -X POST "$API/bookmarks" -H "Authorization: Bearer $ALICE" \
  -H "Content-Type: application/json" \
  -d '{"title":"alice link","url":"https://example.com"}' | jq -r '.id')
[ "$A_ID" != "null" ] && pass "alice created bookmark id=$A_ID" || fail "alice create failed"

# SAME url, DIFFERENT user -> allowed by the composite (user_id, url) constraint.
code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$API/bookmarks" \
  -H "Authorization: Bearer $BOB" -H "Content-Type: application/json" \
  -d '{"title":"bob same link","url":"https://example.com"}')
check 201 "$code" "bob can save the SAME url as alice"

# Same url, same user -> 409.
code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$API/bookmarks" \
  -H "Authorization: Bearer $ALICE" -H "Content-Type: application/json" \
  -d '{"title":"dupe","url":"https://example.com"}')
check 409 "$code" "alice cannot duplicate her own url"

# Each user sees only their own.
n=$(curl -s "$API/bookmarks" -H "Authorization: Bearer $ALICE" | jq -r '.total')
check 1 "$n" "alice's list total is only her own"

echo
echo "=== 5. THE IMPORTANT ONE: ownership boundary (IDOR) ==="
echo "  Bob tries to touch Alice's bookmark id=$A_ID. All three must be 404."

code=$(curl -s -o /dev/null -w '%{http_code}' "$API/bookmarks/$A_ID" -H "Authorization: Bearer $BOB")
check 404 "$code" "bob GET alice's bookmark"

code=$(curl -s -o /dev/null -w '%{http_code}' -X PATCH "$API/bookmarks/$A_ID" \
  -H "Authorization: Bearer $BOB" -H "Content-Type: application/json" \
  -d '{"title":"pwned"}')
check 404 "$code" "bob PATCH alice's bookmark"

code=$(curl -s -o /dev/null -w '%{http_code}' -X DELETE "$API/bookmarks/$A_ID" \
  -H "Authorization: Bearer $BOB")
check 404 "$code" "bob DELETE alice's bookmark"

# Confirm Alice's bookmark actually survived Bob's attempts.
code=$(curl -s -o /dev/null -w '%{http_code}' "$API/bookmarks/$A_ID" -H "Authorization: Bearer $ALICE")
check 200 "$code" "alice's bookmark still intact"

echo
echo "Any FAIL in section 5 is a real vulnerability, not a bug."
echo