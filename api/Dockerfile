FROM s390x/alpine:latest

RUN apk --no-cache add libc6-compat

WORKDIR /app

COPY short .

RUN chmod +x /app/short

CMD ["./short"]

EXPOSE 3000
