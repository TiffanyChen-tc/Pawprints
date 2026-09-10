FROM node:22-alpine AS web-build

WORKDIR /repo

COPY apps/web/package.json apps/web/package-lock.json ./apps/web/
RUN npm ci --prefix apps/web

COPY apps/web ./apps/web
RUN npm --prefix apps/web run build

FROM nginx:1.27-alpine

COPY infra/nginx/nginx.conf /etc/nginx/nginx.conf
COPY --from=web-build /repo/apps/web/dist /usr/share/nginx/html
