#!/usr/bin/env bash
set -euo pipefail
umask 027

archive="${1:?Missing archive path}"
sha="${2:?Missing commit SHA}"

root="/opt/homework-portal"
releases="$root/releases"
release="$releases/$sha"

if [[ ! "$sha" =~ ^[0-9a-f]{40}$ ]]; then
  echo "Invalid Git commit SHA" >&2
  exit 1
fi

test -f "$archive"
test -d "$releases"
test -w "$releases"
test -f "$root/shared/.env"

# Validate the shared NFS upload filesystem.
nfs_path="$root/uploads"
expected_source="172.31.71.124:/srv/homework-portal/uploads"

actual_source="$(findmnt -rn -M "$nfs_path" -o SOURCE || true)"
actual_type="$(findmnt -rn -M "$nfs_path" -o FSTYPE || true)"

if [[ "$actual_source" != "$expected_source" ||
      "$actual_type" != "nfs4" ]]; then
  echo "ERROR: Expected NFS upload storage is not mounted" >&2
  exit 1
fi

test -d "$nfs_path/resources"
test -d "$nfs_path/submissions"

digest="$(sha256sum "$archive" | awk '{print $1}')"

# Repeated execution must not overwrite an existing release.
if [ -e "$release" ] || [ -L "$release" ]; then
  test "$(cat "$release/DEPLOYED_COMMIT")" = "$sha"
  test "$(cat "$release/SOURCE_ARCHIVE_SHA256")" = "$digest"
  echo "Existing release verified: $sha"
  exit 0
fi

# Extract into a temporary directory before publishing the release.
stage="$(mktemp -d "$releases/.stage.XXXXXXXX")"
trap 'rm -rf -- "$stage"' EXIT

tar -xzf "$archive" -C "$stage"

test -f "$stage/app.py"
test -f "$stage/requirements.txt"

# Never accept credentials or uploaded files inside a source release.
for path in .env uploads DEPLOYED_COMMIT SOURCE_ARCHIVE_SHA256; do
  if [ -e "$stage/$path" ] || [ -L "$stage/$path" ]; then
    echo "Unexpected release content: $path" >&2
    exit 1
  fi
done

printf '%s\n' "$sha" > "$stage/DEPLOYED_COMMIT"
printf '%s\n' "$digest" > "$stage/SOURCE_ARCHIVE_SHA256"

# Persistent data is separate from versioned application code.
ln -s ../../uploads "$stage/uploads"
ln -s /etc/homework-portal/.env "$stage/.env"

chmod 750 "$stage"
mv -- "$stage" "$release"
trap - EXIT

echo "Source release installed: $sha"