FROM nginx:1.25-alpine

# Remove the default config so only our config is loaded
RUN rm /etc/nginx/conf.d/default.conf

# Copy gateway configuration
COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
