#!/usr/bin/env bash
# Generates a random flag per burrow and assemble the scoreboard's
# challenge registry. Run ONCE before the first `docker compose up`.
#
# Re-running rotates flags, which invalidates every already-submitted flag, so
# this refuses to clobber existing flags unless you pass --force.
set -euo pipefail

cd "$(dirname "$0")"

# Burrow registry: id | dir | display name | points | difficulty
# One line per burrow. This is the single source of truth init.sh iterates.
BURROWS=(
  "burrow1|burrow1-pathtraversal|Burrow 1 - Burrow Library|100|Easy"
  "burrow2|burrow2-marshal|Burrow 2 - Warren Lounge|150|Medium"
)

FORCE=0
[[ "${1:-}" == "--force" ]] && FORCE=1

random_flag() {
  # flag{<id>_<12 hex>}
  printf 'flag{%s_%s}' "$1" "$(head -c 6 /dev/urandom | od -An -tx1 | tr -d ' \n')"
}

SEED_DIR="scoreboard/seed"
SEED_FILE="$SEED_DIR/challenges.json"
mkdir -p "$SEED_DIR"

# Refuse to clobber existing flags unless --force
if [[ $FORCE -eq 0 ]]; then
  for row in "${BURROWS[@]}"; do
    IFS='|' read -r id dir _ _ _ <<<"$row"
    if [[ -f "burrows/$dir/.flag.env" ]]; then
      echo "error: burrows/$dir/.flag.env already exists." >&2
      echo "       Flags are already generated. Re-running rotates them and" >&2
      echo "       invalidates submitted flags. Pass --force to regenerate." >&2
      exit 1
    fi
  done
fi

entries=()
for row in "${BURROWS[@]}"; do
  IFS='|' read -r id dir name points difficulty <<<"$row"
  flag="$(random_flag "$id")"

  # Each burrow receives only its own flag.
  printf 'FLAG=%s\n' "$flag" > "burrows/$dir/.flag.env"

  # Accumulate a JSON object for the full registry (scoreboard only).
  entries+=("$(printf '  {"id": "%s", "name": "%s", "flag": "%s", "points": %s, "difficulty": "%s"}' \
    "$id" "$name" "$flag" "$points" "$difficulty")")

  echo "generated flag for $id ($name)"
done

# Join the entries with commas into a JSON array.
{
  echo "["
  for i in "${!entries[@]}"; do
    sep=","
    [[ $i -eq $((${#entries[@]} - 1)) ]] && sep=""
    printf '%s%s\n' "${entries[$i]}" "$sep"
  done
  echo "]"
} > "$SEED_FILE"

echo "wrote $SEED_FILE"
echo "done. Next: export ADMIN_PASSWORD=<something> && docker compose up --build"
