FROM alpine:latest

RUN apk --no-cache add libc6-compat

WORKDIR /root/

COPY short .

CMD ["./short"]

EXPOSE 3000
