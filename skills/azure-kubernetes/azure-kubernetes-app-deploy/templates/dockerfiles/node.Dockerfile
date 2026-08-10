# =============================================================================
# Node.js Production Dockerfile
# =============================================================================
# Customize the following before use:
#   - APP_NAME:    Replace in comments as needed
#   - PORT:        Change EXPOSE port if not 3000
#   - ENTRY_POINT: Change the final CMD to your main file (e.g. dist/main.js)
#   - BUILD_CMD:   Adjust "npm run build --if-present" if your build script differs
#
# Package manager support:
#   - npm:  This file is configured for npm by default
#   - yarn: Replace "npm ci" with "yarn install --frozen-lockfile"
#           Replace "package-lock.json" with "yarn.lock"
#   - pnpm: Replace "npm ci" with "corepack enable && pnpm install --frozen-lockfile"
#           Replace "package-lock.json" with "pnpm-lock.yaml"
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Build
# ---------------------------------------------------------------------------
# Base: current Node LTS, Alpine variant. See references/base-images.md.
FROM node:<LATEST_STABLE_NODE>-alpine AS build

WORKDIR /app

# Layer caching: copy dependency manifests first so the install layer is
# only rebuilt when dependencies change, not on every source edit.
COPY package.json package-lock.json ./

RUN npm ci

# Copy the rest of the source and build
COPY . .

RUN npm run build --if-present

# Guard: verify build output exists at expected location
RUN test -d /app/dist || (echo "ERROR: Build output directory '/app/dist' not found." && echo "Your build script did not produce output in the 'dist/' directory." && echo "Update the 'COPY --from=build /app/dist ./dist' line in the runtime stage" && echo "to match your build script's output directory (e.g., 'build/', 'out/', 'public/')." && exit 1)

# Remove dev dependencies to slim down the production node_modules
RUN npm prune --omit=dev

# ---------------------------------------------------------------------------
# Stage 2: Runtime
# ---------------------------------------------------------------------------
FROM node:<LATEST_STABLE_NODE>-alpine

# Security: install dumb-init so Node runs as PID > 1 and signals propagate
# correctly — avoids zombie processes inside the container.
RUN apk add --no-cache dumb-init

WORKDIR /app

# Copy only production artifacts from the build stage.
# If your build script outputs to a different directory (e.g. build/ or out/),
# update the /app/dist path below to match.
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/dist ./dist
COPY --from=build /app/package.json ./

# AKS Deployment Safeguards DS004: never run as root.
# The "node" user (uid 1000) is built into the node-alpine image.
USER node

EXPOSE 3000

# HEALTHCHECK is omitted — Kubernetes liveness/readiness probes handle health
# checks in AKS. See deployment.yaml for probe configuration.

ENTRYPOINT ["dumb-init", "--"]
CMD ["node", "dist/main.js"]
