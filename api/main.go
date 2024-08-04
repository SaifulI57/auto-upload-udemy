package main

import (
	"context"
	"crypto/rand"
	"fmt"
	"log"
	"math/big"

	"github.com/gofiber/fiber/v2"
	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/mongo"
	"go.mongodb.org/mongo-driver/mongo/options"
)

func generateId() (string, error) {
	const chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
	var id string
	for i := 0; i < 4; i++ {
		n, err := rand.Int(rand.Reader, big.NewInt(int64(len(chars))))
		if err != nil {
			return "", err
		}
		id += string(chars[n.Int64()])
	}
	return id, nil
}

func main() {
	app := fiber.New()

	clientOptions := options.Client().ApplyURI("mongodb://mongodb:27017")

	client, err := mongo.Connect(context.TODO(), clientOptions)
	if err != nil {
		log.Fatal(err)
	}

	err = client.Ping(context.TODO(), nil)
	if err != nil {
		log.Fatal(err)
	}

	fmt.Println("Connected to MongoDB!")
	collection := client.Database("short").Collection("shortcollection")

	app.Post("/short", func(c *fiber.Ctx) error {
		url := c.Query("url")
		if url == "" {
			return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{"error": "URL query parameter is required"})
		}
		id, err := generateId()
		if err != nil {
			return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{"error": "Error generating ID"})
		}
		doc := bson.D{{Key: "id", Value: id}, {Key: "url", Value: url}}
		_, err = collection.InsertOne(context.TODO(), doc)
		if err != nil {
			return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{"error": "Error inserting document into database"})
		}
		return c.Status(fiber.StatusOK).JSON(fiber.Map{"id": id})
	})

	app.Get("/:id", func(c *fiber.Ctx) error {
		id := c.Params("id")
		filter := bson.D{{Key: "id", Value: id}}
		var result bson.M
		err := collection.FindOne(context.TODO(), filter).Decode(&result)
		if err == mongo.ErrNoDocuments {
			return c.Status(fiber.StatusNotFound).JSON(fiber.Map{"error": "Document not found"})
		} else if err != nil {
			return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{"error": "Error finding document in database"})
		}
		url, ok := result["url"].(string)
		if !ok {
			return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{"error": "URL field is missing or invalid"})
		}
		return c.Redirect(url, fiber.StatusMovedPermanently)
	})

	log.Fatal(app.Listen(":3000"))
}
