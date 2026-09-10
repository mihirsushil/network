FROM node:20-slim AS build

WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
# react-scripts 5's build-time ESLint plugin can't resolve
# react-hooks/exhaustive-deps in this dependency tree (pre-existing,
# unrelated to this Dockerfile) - disable it so the build isn't blocked.
ENV DISABLE_ESLINT_PLUGIN=true
RUN npm run build

FROM nginx:1.27-alpine

COPY --from=build /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
