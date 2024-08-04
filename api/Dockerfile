FROM s390x/golang:1.21.12-alpine3.19


WORKDIR /app

COPY . .

RUN go mod tidy

CMD ["go", "run", "main.go"]

EXPOSE 3000
