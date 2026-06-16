FROM node:18-slim AS build

WORKDIR /app

COPY bank-node/fraud-dashboard/package.json ./
RUN npm install

COPY bank-node/fraud-dashboard/ .
RUN npm run build

FROM nginx:1.29-alpine

COPY bank-node/fraud-dashboard/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/build /usr/share/nginx/html

EXPOSE 3001

CMD ["nginx", "-g", "daemon off;"]
