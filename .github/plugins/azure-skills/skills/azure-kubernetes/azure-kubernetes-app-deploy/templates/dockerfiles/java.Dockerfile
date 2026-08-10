# =============================================================================
# Java (Spring Boot / Maven) Production Dockerfile
# =============================================================================
# Customize the following before use:
#   - JAR_FILE:    Adjust the glob pattern if your build output differs
#   - PORT:        Change EXPOSE port if not 8080
#   - JVM_OPTS:    Tune -Xmx, -Xms, GC flags, etc. via JAVA_OPTS env var
#
# Gradle users:
#   Replace the Maven wrapper commands in the build stage with:
#     COPY gradlew build.gradle.kts settings.gradle.kts ./
#     COPY gradle ./gradle
#     RUN ./gradlew dependencies --no-daemon
#     COPY . .
#     RUN ./gradlew bootJar --no-daemon
#   And adjust the JAR_FILE path to "build/libs/*.jar"
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Build
# ---------------------------------------------------------------------------
# Base: current Java LTS (Temurin). See references/base-images.md for the Microsoft OpenJDK alternative.
FROM eclipse-temurin:<LATEST_STABLE_JAVA_JDK>-jdk-alpine AS build

WORKDIR /app

# Layer caching: copy Maven wrapper and POM first so dependency resolution is
# cached independently of source changes.
COPY mvnw pom.xml ./
COPY .mvn .mvn

# Download dependencies (offline-friendly layer)
RUN chmod +x mvnw \
    && ./mvnw dependency:go-offline -B

# Copy source and build the fat JAR
COPY src ./src

# -Dspring-boot.repackage.finalName=app ensures a single predictably named fat JAR,
# avoiding glob ambiguity when Maven produces both thin and fat JARs.
RUN ./mvnw package spring-boot:repackage -DskipTests -B \
    -Dspring-boot.repackage.finalName=app \
    && mv target/app.jar app.jar

# ---------------------------------------------------------------------------
# Stage 2: Runtime
# ---------------------------------------------------------------------------
FROM eclipse-temurin:<LATEST_STABLE_JAVA_JRE>-jre-alpine

WORKDIR /app

# AKS Deployment Safeguards DS004: create and switch to a non-root user
RUN addgroup -S appuser && adduser -S appuser -G appuser

# Copy only the built JAR from the build stage
COPY --from=build --chown=appuser:appuser /app/app.jar ./app.jar

# Spring Boot Layered JARs: if using layered JARs, replace the COPY above
# with the extract + copy approach for even better layer caching:
#   RUN java -Djarmode=layertools -jar app.jar extract
#   COPY --from=build /app/dependencies/ ./
#   COPY --from=build /app/spring-boot-loader/ ./
#   COPY --from=build /app/snapshot-dependencies/ ./
#   COPY --from=build /app/application/ ./

USER appuser

EXPOSE 8080

# MaxRAMPercentage caps heap relative to the container memory limit
# (container-aware by default in JDK 21).
ENV JAVA_OPTS="-XX:MaxRAMPercentage=75.0 -XX:+UseG1GC"

# No HEALTHCHECK: the JRE Alpine image does not include wget or curl.
# Kubernetes liveness/readiness probes (configured in deployment.yaml) handle
# health checking in AKS.

ENTRYPOINT ["sh", "-c", "exec java $JAVA_OPTS -jar app.jar"]
