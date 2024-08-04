FROM s390x/golang:1.22.5-alpine3.20


WORKDIR /app

COPY . .

RUN go mod tidy

CMD ["go", "run", "main.go"]

EXPOSE 3000
