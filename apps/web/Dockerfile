# Preflight web.
#
# Built standalone so the runtime image carries only what Next.js actually
# needs to serve, rather than the whole toolchain that produced it.

FROM node:22-slim AS build
WORKDIR /app

RUN corepack enable

COPY apps/web/package.json apps/web/pnpm-lock.yaml* ./

# --ignore-scripts: firebase and protobufjs ship postinstall scripts that are
# only needed for native/node targets. This bundle is browser code, so skipping
# them is both correct and one less piece of unreviewed code running at build
# time. strict-dep-builds is disabled so that skipping is a decision rather
# than a build failure.
RUN pnpm install --no-frozen-lockfile --ignore-scripts       --config.strict-dep-builds=false

COPY apps/web/ ./

# NEXT_PUBLIC_* values are compiled into the client bundle, so they must be
# present at build time rather than injected at run time. Every one of them is
# public by design: the Firebase browser key identifies the project, it does
# not authorise anything on its own.
ARG NEXT_PUBLIC_API_BASE_URL
ARG NEXT_PUBLIC_FIREBASE_API_KEY
ARG NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN
ARG NEXT_PUBLIC_FIREBASE_PROJECT_ID
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL \
    NEXT_PUBLIC_FIREBASE_API_KEY=$NEXT_PUBLIC_FIREBASE_API_KEY \
    NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=$NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN \
    NEXT_PUBLIC_FIREBASE_PROJECT_ID=$NEXT_PUBLIC_FIREBASE_PROJECT_ID \
    NEXT_TELEMETRY_DISABLED=1

# Refuse to build an app nobody can sign in to.
#
# Because these are compiled into the bundle, a missing one is not a runtime
# error that shows up in a log: the build succeeds, the deploy succeeds, the
# page loads, and the only symptom is that authentication silently does not
# exist. That shipped once, from a build invoked without its substitutions.
#
# The guard lives here rather than only in the Cloud Build config so that every
# way of producing this image is covered, including a plain `docker build`.
RUN set -eu; \
    missing=""; \
    for name in NEXT_PUBLIC_API_BASE_URL NEXT_PUBLIC_FIREBASE_API_KEY \
                NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN NEXT_PUBLIC_FIREBASE_PROJECT_ID; do \
      eval "value=\${$name}"; \
      [ -n "$value" ] || missing="$missing $name"; \
    done; \
    if [ -n "$missing" ]; then \
      echo "" >&2; \
      echo "Refusing to build: missing build arguments:$missing" >&2; \
      echo "" >&2; \
      echo "These are compiled into the browser bundle, so an empty one produces" >&2; \
      echo "an application that loads but cannot sign anyone in. Pass them:" >&2; \
      echo "" >&2; \
      echo "  gcloud builds submit --config=infra/cloudbuild-web.yaml \\" >&2; \
      echo "    --substitutions=_TAG=v1,_FIREBASE_API_KEY=...,_FIREBASE_AUTH_DOMAIN=... ." >&2; \
      echo "" >&2; \
      echo "The values are the browser Firebase config in .env, which is public" >&2; \
      echo "by design and is not a credential." >&2; \
      exit 1; \
    fi

RUN pnpm build

FROM node:22-slim AS run
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1

RUN useradd --create-home --uid 10001 preflight

COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public

USER preflight
EXPOSE 8080
ENV PORT=8080 HOSTNAME=0.0.0.0
CMD ["node", "server.js"]
