FROM node:18-slim

WORKDIR /app

COPY bank-node/fraud-dashboard/package.json ./
RUN npm install

COPY bank-node/fraud-dashboard/ .

EXPOSE 3000

CMD ["npm", "start"]
