FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .

# Leave empty by default so frontend can auto-target the current host at runtime
# (frontend/src/config/api.js will use window.location host + service ports).
ARG REACT_APP_AUTH_URL=
ARG REACT_APP_MEMBER_URL=
ARG REACT_APP_RECRUITER_URL=
ARG REACT_APP_JOB_URL=
ARG REACT_APP_APP_URL=
ARG REACT_APP_MSG_URL=
ARG REACT_APP_ANALYTICS_URL=
ARG REACT_APP_AI_URL=
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
