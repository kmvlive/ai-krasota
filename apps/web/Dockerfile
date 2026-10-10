# Сборка фронтенда из корня монорепозитория (нужны pnpm-workspace + packages/ui)
FROM node:20-alpine AS builder
WORKDIR /repo
RUN corepack enable
COPY pnpm-workspace.yaml package.json turbo.json ./
COPY apps/web ./apps/web
COPY packages/ui ./packages/ui
RUN pnpm install --frozen-lockfile || pnpm install
RUN pnpm --filter @ai-krasota/web build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /repo/apps/web/.next ./apps/web/.next
COPY --from=builder /repo/apps/web/public ./apps/web/public
COPY --from=builder /repo/apps/web/next.config.mjs ./apps/web/
COPY --from=builder /repo/node_modules ./node_modules
COPY --from=builder /repo/package.json ./package.json
EXPOSE 3000
CMD ["pnpm", "--filter", "@ai-krasota/web", "start"]
