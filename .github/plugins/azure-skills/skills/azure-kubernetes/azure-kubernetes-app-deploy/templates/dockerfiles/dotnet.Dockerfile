# =============================================================================
# .NET (ASP.NET Core) Production Dockerfile
# =============================================================================
# Customize the following before use:
#   - PROJECT_NAME: Replace "MyApp" with your .csproj name (without extension)
#   - PORT:         Change EXPOSE port if not 8080
#   - ASSEMBLY:     Adjust the DLL name in ENTRYPOINT if it differs from the project
#
# Notes:
#   - .NET 8+ defaults to port 8080 (ASPNETCORE_HTTP_PORTS), not 80
#   - The "app" user is built into the aspnet runtime image since .NET 8
#   - For self-contained deployment, add --self-contained to dotnet publish
#     and switch the runtime image to mcr.microsoft.com/dotnet/runtime-deps:<LATEST_STABLE_DOTNET_ASPNET>
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Build
# ---------------------------------------------------------------------------
# Base: current .NET LTS (Microsoft official). See references/base-images.md.
FROM mcr.microsoft.com/dotnet/sdk:<LATEST_STABLE_DOTNET_SDK> AS build

WORKDIR /src

# Layer caching: restore NuGet packages before copying the full source.
# Copy only project files first so the restore layer is cached independently.
COPY *.sln ./
COPY src/MyApp/*.csproj src/MyApp/

RUN dotnet restore src/MyApp/MyApp.csproj

# Copy everything and publish a Release build
COPY . .

RUN dotnet publish src/MyApp/MyApp.csproj \
    --configuration Release \
    --no-restore \
    --output /app/publish

# ---------------------------------------------------------------------------
# Stage 2: Runtime
# ---------------------------------------------------------------------------
# Base: current .NET LTS (Microsoft official). See references/base-images.md.
FROM mcr.microsoft.com/dotnet/aspnet:<LATEST_STABLE_DOTNET_ASPNET>

WORKDIR /app

# Copy published output from the build stage
COPY --from=build /app/publish ./

# AKS Deployment Safeguards DS004: run as non-root.
# The "app" user is built into the aspnet image since .NET 8.
USER app

EXPOSE 8080

ENV ASPNETCORE_URLS="http://+:8080" \
    DOTNET_RUNNING_IN_CONTAINER=true \
    DOTNET_EnableDiagnostics=0

# No HEALTHCHECK: the aspnet runtime image does not include curl or wget.
# Kubernetes liveness/readiness probes (configured in deployment.yaml) handle
# health checking in AKS. For local Docker usage, install wget or add
# app.MapHealthChecks("/healthz") and use a custom health check binary.

ENTRYPOINT ["dotnet", "MyApp.dll"]
