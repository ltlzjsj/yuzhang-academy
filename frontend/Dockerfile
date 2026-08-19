# 赣书院·智典 frontend — build with Node, serve static via nginx.
FROM node:20-alpine AS build
WORKDIR /app
RUN npm config set registry http://mirrors.cloud.tencent.com/npm/
COPY package*.json ./
COPY scripts ./scripts
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
