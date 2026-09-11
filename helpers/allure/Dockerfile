FROM node:24.8.0-alpine3.22

RUN npm install --prefix /opt/allure allure@3.17.0
RUN apk add --no-cache git

WORKDIR /workspace

COPY allurerc.mjs /opt/allure/allurerc.mjs

ENTRYPOINT ["/opt/allure/node_modules/.bin/allure"]
