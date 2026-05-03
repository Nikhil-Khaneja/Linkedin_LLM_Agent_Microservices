FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .

# Accept ALB URLs at build time for AWS deployments
ARG REACT_APP_AUTH_URL=http://localhost:8001
ARG REACT_APP_MEMBER_URL=http://localhost:8002
ARG REACT_APP_RECRUITER_URL=http://localhost:8003
ARG REACT_APP_JOB_URL=http://localhost:8004
ARG REACT_APP_APP_URL=http://localhost:8005
ARG REACT_APP_MSG_URL=http://localhost:8006
ARG REACT_APP_ANALYTICS_URL=http://localhost:8007
ARG REACT_APP_AI_URL=http://localhost:8008
ENV REACT_APP_AUTH_URL=$REACT_APP_AUTH_URL
ENV REACT_APP_MEMBER_URL=$REACT_APP_MEMBER_URL
ENV REACT_APP_RECRUITER_URL=$REACT_APP_RECRUITER_URL
ENV REACT_APP_JOB_URL=$REACT_APP_JOB_URL
ENV REACT_APP_APP_URL=$REACT_APP_APP_URL
ENV REACT_APP_MSG_URL=$REACT_APP_MSG_URL
ENV REACT_APP_ANALYTICS_URL=$REACT_APP_ANALYTICS_URL
ENV REACT_APP_AI_URL=$REACT_APP_AI_URL

RUN npm run build

FROM nginx:alpine
COPY --from=build /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
