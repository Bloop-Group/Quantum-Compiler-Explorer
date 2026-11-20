# Build stage
FROM node:20-alpine AS builder
WORKDIR /srv/frontend
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build

# Static production serving stage
FROM nginx:1.27-alpine
COPY --from=builder /srv/frontend/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
HEALTHCHECK --interval=15s --timeout=3s --retries=3 CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1
CMD ["nginx", "-g", "daemon off;"]
