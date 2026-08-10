# =============================================================================
# Rust Production Dockerfile
# =============================================================================
# Customize the following before use:
#   - APP_NAME:    Replace "app" with your binary name from Cargo.toml
#   - PORT:        Change EXPOSE port if not 8080
#
# Notes:
#   - The dependency-caching trick creates a dummy main.rs, builds
#     dependencies, then replaces it with real source — this avoids
#     rebuilding all deps on every source change
#   - The final image uses distroless/cc which includes libgcc/libstdc++
#     needed by the default Rust allocator; if you use musl
#     (--target x86_64-unknown-linux-musl) switch to distroless/static
#   - For workspace builds, copy the whole workspace in one shot and adjust
#     the binary path in the final COPY
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Build
# ---------------------------------------------------------------------------
# Base: current stable Rust, Debian-slim. See references/base-images.md.
FROM rust:<LATEST_STABLE_RUST>-slim AS build

WORKDIR /app

# Install build dependencies (if any native libs are needed, add them here)
RUN apt-get update \
    && apt-get install -y --no-install-recommends pkg-config libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Layer caching: build dependencies separately from application code.
# 1. Copy only the manifests and create a dummy main to compile deps.
COPY Cargo.toml Cargo.lock ./

RUN mkdir src \
    && echo 'fn main() { println!("placeholder"); }' > src/main.rs \
    && cargo build --release \
    && echo "IMPORTANT: Update 'app' below to match your [[bin]] name in Cargo.toml." \
    && echo "If the name doesn't match, this cache trick will silently fail." \
    && rm -rf src target/release/deps/app* target/release/app*

# 2. Copy real source and build the actual binary.
COPY src ./src

RUN cargo build --release

# Verify binary exists with expected name
RUN test -f /app/target/release/app || (echo "ERROR: Binary 'app' not found at /app/target/release/app"; echo "The binary name in Cargo.toml must be 'app'."; echo "Update [[bin]] section in Cargo.toml to set name = \"app\""; echo "Also verify the COPY step above uses the correct binary name."; exit 1)

# ---------------------------------------------------------------------------
# Stage 2: Runtime
# ---------------------------------------------------------------------------
FROM gcr.io/distroless/cc-debian12

WORKDIR /app

# Update source path if your Cargo.toml binary name differs from "app"
COPY --from=build /app/target/release/app /app/app

# AKS Deployment Safeguards DS004: run as non-root.
# 65534 is the "nobody" user in distroless images.
USER 65534

EXPOSE 8080

# Distroless has no shell, curl, or wget. Kubernetes liveness/readiness probes
# (configured in deployment.yaml) handle health checking in AKS.
# For local Docker usage, consider adding a /healthz handler and using a
# statically-compiled health check binary.

# Update "/app/app" if your binary name differs
ENTRYPOINT ["/app/app"]
