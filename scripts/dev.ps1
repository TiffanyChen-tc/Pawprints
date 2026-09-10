param(
  [Parameter(Mandatory=$true)]
  [ValidateSet("setup","migrate","up","test","smoke","seed","down","start","demo","reset-data")]
  [string]$Command
)

$ErrorActionPreference = "Stop"
if ($PSVersionTable.PSVersion.Major -lt 7) {
  throw "Pawprints dev workflow requires PowerShell 7+. Run this script with pwsh."
}

function Invoke-Checked {
  param(
    [Parameter(Mandatory=$true)][string]$FilePath,
    [Parameter(ValueFromRemainingArguments=$true)][string[]]$Arguments
  )
  & $FilePath @Arguments
  if ($LASTEXITCODE -ne 0) {
    throw "Native command failed with exit code ${LASTEXITCODE}: $FilePath $($Arguments -join ' ')"
  }
}

function New-UrlSafeSecret {
  $bytes = [byte[]]::new(32)
  [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
  return [Convert]::ToBase64String($bytes).TrimEnd("=").Replace("+","-").Replace("/","_")
}

function Set-EnvValueIfPlaceholder {
  param([string]$Path, [string]$Name, [string]$Value)
  $content = Get-Content $Path -Raw
  if ($content -match "(?m)^$Name=(CHANGE_ME|CHANGE_ME_GENERATED)$") {
    $content = $content -replace "(?m)^$Name=.*$", "$Name=$Value"
    Set-Content -Path $Path -Value $content -NoNewline
  }
}

function Get-ComposeProjectName {
  if ($env:COMPOSE_PROJECT_NAME) {
    return $env:COMPOSE_PROJECT_NAME
  }
  return ((Split-Path -Leaf (Get-Location)).ToLowerInvariant() -replace "[^a-z0-9_-]", "")
}

function Get-PersistentPostgresVolumeNames {
  $projectName = Get-ComposeProjectName
  $volumeNames = & docker volume ls --format "{{.Name}}"
  if ($LASTEXITCODE -ne 0) {
    throw "Native command failed with exit code ${LASTEXITCODE}: docker volume ls --format {{.Name}}"
  }

  $composeLabeledVolumes = & docker volume ls --filter "label=com.docker.compose.project=$projectName" --filter "label=com.docker.compose.volume=postgres_data" --format "{{.Name}}"
  if ($LASTEXITCODE -ne 0) {
    throw "Native command failed with exit code ${LASTEXITCODE}: docker volume ls --filter label=com.docker.compose.project=$projectName --filter label=com.docker.compose.volume=postgres_data --format {{.Name}}"
  }

  $candidateNames = @("${projectName}_postgres_data")

  $matchedByName = @($volumeNames | Where-Object { $candidateNames -contains $_ })
  return @($matchedByName + $composeLabeledVolumes | Where-Object { $_ } | Sort-Object -Unique)
}

function Ensure-JwtKeys {
  $privatePath = "secrets/jwt_private.pem"
  $publicPath = "secrets/jwt_public.pem"
  $hasPrivate = Test-Path $privatePath
  $hasPublic = Test-Path $publicPath

  if (!$hasPrivate -and !$hasPublic) {
    $rsa = [System.Security.Cryptography.RSA]::Create(2048)
    Set-Content -Path $privatePath -Value $rsa.ExportPkcs8PrivateKeyPem() -NoNewline
    Set-Content -Path $publicPath -Value $rsa.ExportSubjectPublicKeyInfoPem() -NoNewline
    return
  }

  if ($hasPrivate -and !$hasPublic) {
    $rsa = [System.Security.Cryptography.RSA]::Create()
    $rsa.ImportFromPem((Get-Content -Raw $privatePath))
    Set-Content -Path $publicPath -Value $rsa.ExportSubjectPublicKeyInfoPem() -NoNewline
    return
  }

  if (!$hasPrivate -and $hasPublic) {
    throw "JWT public key exists but private key is missing. Restore secrets/jwt_private.pem or explicitly delete both JWT key files to generate a new development key pair."
  }
}

function Ensure-LocalConfig {
  $postgresVolumes = Get-PersistentPostgresVolumeNames
  if (!(Test-Path ".env") -and $postgresVolumes.Count -gt 0) {
    throw ".env is missing but the PostgreSQL volume exists. Restore .env or run an explicitly destructive reset before generating new DB credentials."
  }
  if (!(Test-Path ".env")) { Copy-Item ".env.example" ".env" }
  New-Item -ItemType Directory -Force "secrets" | Out-Null
  foreach ($name in "POSTGRES_ADMIN_PASSWORD","AUTH_DB_PASSWORD","EVENT_DB_PASSWORD","MEDIA_DB_PASSWORD","ANALYTICS_DB_PASSWORD","EVENT_INTERNAL_TOKEN","MEDIA_INTERNAL_TOKEN","ANALYTICS_INTERNAL_TOKEN") {
    Set-EnvValueIfPlaceholder ".env" $name (New-UrlSafeSecret)
  }
  $envContent = Get-Content ".env" -Raw
  foreach ($name in "AUTH","EVENT","MEDIA","ANALYTICS") {
    $password = [regex]::Match($envContent, "(?m)^${name}_DB_PASSWORD=(.+)$").Groups[1].Value
    $role = "pawprints_" + $name.ToLowerInvariant()
    if ($name -eq "ANALYTICS") { $role = "${role}_ro" } else { $role = "${role}_rw" }
    $urlName = "${name}_DATABASE_URL"
    $url = "postgresql+psycopg://${role}:${password}@postgres:5432/pawprints"
    $envContent = $envContent -replace "(?m)^$urlName=.*$", "$urlName=$url"
  }
  Set-Content -Path ".env" -Value $envContent -NoNewline

  Ensure-JwtKeys
}

function Start-PresentServices {
  param([string[]]$Names)
  $services = & docker compose config --services
  if ($LASTEXITCODE -ne 0) {
    throw "Native command failed with exit code ${LASTEXITCODE}: docker compose config --services"
  }
  $present = @($Names | Where-Object { $services -contains $_ })
  if ($present.Count -gt 0) {
    Invoke-Checked docker compose up --build -d --wait @present
  }
}

function Wait-ForReady {
  Start-PresentServices @("auth","event","nginx","media","analytics","prometheus","grafana")
}

function Invoke-ComposeJobIfPresent {
  param([string]$ServiceName)
  $services = & docker compose --profile jobs config --services
  if ($LASTEXITCODE -ne 0) {
    throw "Native command failed with exit code ${LASTEXITCODE}: docker compose --profile jobs config --services"
  }
  if ($services -contains $ServiceName) {
    Invoke-Checked docker compose --profile jobs run --build --rm $ServiceName
  }
}

function Assert-NoPublicServicePorts {
  $configJson = & docker compose config --format json
  if ($LASTEXITCODE -ne 0) {
    throw "Native command failed with exit code ${LASTEXITCODE}: docker compose config --format json"
  }
  $config = $configJson | ConvertFrom-Json
  foreach ($serviceName in "auth","event","media","analytics") {
    $serviceProperty = $config.services.PSObject.Properties[$serviceName]
    if ($null -ne $serviceProperty) {
      $portsProperty = $serviceProperty.Value.PSObject.Properties["ports"]
      if ($null -ne $portsProperty -and @($portsProperty.Value).Count -gt 0) {
        throw "Service '$serviceName' must not expose host ports."
      }
    }
  }
}

function Invoke-TestSuite {
  $exitCode = 0
  try {
    Invoke-Checked docker compose --profile test up --build -d --wait postgres-test redis-test

    $env:AUTH_DATABASE_URL = "postgresql+psycopg://pawprints_auth_rw:test_auth@127.0.0.1:55432/pawprints_test"
    $env:EVENT_DATABASE_URL = "postgresql+psycopg://pawprints_event_rw:test_event@127.0.0.1:55432/pawprints_test"
    $env:MEDIA_DATABASE_URL = "postgresql+psycopg://pawprints_media_rw:test_media@127.0.0.1:55432/pawprints_test"
    $env:ANALYTICS_DATABASE_URL = "postgresql+psycopg://pawprints_analytics_ro:test_analytics@127.0.0.1:55432/pawprints_test"
    $env:REDIS_URL = "redis://127.0.0.1:56379/0"

    Invoke-Checked python -m alembic -c services/auth/alembic.ini upgrade head
    Invoke-Checked python -m alembic -c services/event/alembic.ini upgrade head
    Invoke-Checked python -m alembic -c services/media/alembic.ini upgrade head

    Invoke-Checked python -m pytest packages/pawprints-common/tests -q
    Invoke-Checked python -m pytest services/auth/tests -q
    Invoke-Checked python -m pytest services/event/tests -q
    Invoke-Checked python -m pytest services/media/tests -q
    Invoke-Checked python -m pytest services/analytics/tests -q
    if (Test-Path "apps/web/package.json") {
      Invoke-Checked npm --prefix apps/web ci
      Invoke-Checked npm --prefix apps/web test -- --run
    }
  } catch {
    Write-Host $_
    $exitCode = 1
  } finally {
    & docker compose --profile test stop postgres-test redis-test
    if ($LASTEXITCODE -ne 0) { $exitCode = 1 }
    & docker compose --profile test rm -f postgres-test redis-test
    if ($LASTEXITCODE -ne 0) { $exitCode = 1 }
  }
  exit $exitCode
}

function Invoke-Migrate {
  foreach ($job in "auth-migrate","event-migrate","media-migrate") {
    Invoke-ComposeJobIfPresent $job
  }
}

function Invoke-Smoke {
  Wait-ForReady
  Assert-NoPublicServicePorts
  Invoke-Checked docker compose --profile jobs run --build --rm smoke
}

function Invoke-Seed {
  Invoke-Checked docker compose --profile jobs run --build --rm seed
}

function Invoke-Start {
  Ensure-LocalConfig
  Invoke-Checked docker compose up --build -d --wait postgres redis
  Invoke-Migrate
  Invoke-Smoke
}

function Invoke-Demo {
  Invoke-Start
  Invoke-Seed
}

switch ($Command) {
  "setup" { Ensure-LocalConfig }
  "migrate" { Invoke-Migrate }
  "up" { Invoke-Checked docker compose up --build -d --wait }
  "test" { Invoke-TestSuite }
  "smoke" { Invoke-Smoke }
  "seed" { Invoke-Seed }
  "down" { Invoke-Checked docker compose down }
  "start" { Invoke-Start }
  "demo" { Invoke-Demo }
  "reset-data" {
    throw "Destructive reset is intentionally not implemented until explicitly requested during implementation."
  }
}
exit 0
