# =============================================================================
# Go Production Dockerfile
# =============================================================================
# Customize the following before use:
#   - APP_NAME:    Replace "app" in the binary name (go build -o /bin/app)
#                  and in the ENTRYPOINT ["/app"] line
#   - PORT:        Change EXPOSE port if not 8080
#   - MODULE_PATH: Ensure go.mod module path matches your project
#
# Notes:
#   - CGO_ENABLED=0 produces a fully static binary that runs on distroless
#   - The distroless runtime has no shell — use the exec form for ENTRYPOINT
#   - To debug, swap the runtime to gcr.io/distroless/static-debian12:debug
#     which includes busybox
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Build
# ---------------------------------------------------------------------------
# Base: current stable Go. See references/base-images.md.
FROM golang:<LATEST_STABLE_GO>-alpine AS build

WORKDIR /src

# Layer caching: download module dependencies before copying source.
# This layer is only rebuilt when go.mod or go.sum changes.
COPY go.mod go.sum ./

RUN go mod download && go mod verify

# Copy source and compile a static binary
COPY . .

RUN CGO_ENABLED=0 GOOS=linux \
    go build -ldflags="-s -w" -o /bin/app ./cmd/app

# ---------------------------------------------------------------------------
# Stage 2: Runtime
# ---------------------------------------------------------------------------
FROM gcr.io/distroless/static-debian12

# Copy the compiled binary from the build stage
COPY --from=build /bin/app /app

# AKS Deployment Safeguards DS004: run as non-root.
# 65534 is the "nobody" user in distroless images.
USER 65534

EXPOSE 8080

# Distroless has no shell, curl, or wget. Kubernetes liveness/readiness probes
# (configured in deployment.yaml) handle health checking in AKS.
# For local Docker usage, consider adding a /healthz handler and using a
# statically-compiled health check binary, or swap to the :debug variant.

ENTRYPOINT ["/app"]
