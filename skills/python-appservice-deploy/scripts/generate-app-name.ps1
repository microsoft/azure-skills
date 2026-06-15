<#
.SYNOPSIS
    Generates a valid Azure App Service name from a folder name + 8 hex chars.
.DESCRIPTION
    Produces a name suitable for `az webapp create -n <name>` that satisfies
    Azure App Service naming rules:
      - lowercase a-z, 0-9, and hyphens only
      - starts with a letter, ends with letter or digit
      - total length <= 40 chars (slug truncated as needed)
      - regex: ^[a-z][a-z0-9-]{1,38}[a-z0-9]$
.PARAMETER FolderName
    Optional. The base name to derive the slug from. Defaults to the current
    working directory's leaf name.
.EXAMPLE
    .\generate-app-name.ps1
    # Uses current folder name, e.g. "my-flask-app" → "my-flask-app-a3f9c1d2"
.EXAMPLE
    .\generate-app-name.ps1 -FolderName "my-flask-app"
#>
param(
    [string]$FolderName = (Split-Path -Leaf (Get-Location))
)

$ErrorActionPreference = "Stop"

# Lowercase, replace non-[a-z0-9] with '-', collapse repeats, trim hyphens.
$slug = $FolderName.ToLowerInvariant()
$slug = [regex]::Replace($slug, '[^a-z0-9]+', '-')
$slug = [regex]::Replace($slug, '-+', '-')
$slug = $slug.Trim('-')

if ([string]::IsNullOrEmpty($slug)) {
    $slug = "app"
}

# 8 hex chars from a fresh GUID (segment before the first '-').
$suffix = [guid]::NewGuid().ToString().Split('-')[0].Substring(0, 8).ToLowerInvariant()

# Reserve 9 chars for "-XXXXXXXX" so the total stays <= 40.
$maxSlugLen = 31
if ($slug.Length -gt $maxSlugLen) {
    $slug = $slug.Substring(0, $maxSlugLen).TrimEnd('-')
}

$name = "$slug-$suffix"

# Ensure the name starts with a letter (Azure requirement). Prefix 'a' if not.
if ($name -notmatch '^[a-z]') {
    $name = "a$name"
}

# Final length guard.
if ($name.Length -gt 40) {
    $name = $name.Substring(0, 40).TrimEnd('-')
}

Write-Output $name
