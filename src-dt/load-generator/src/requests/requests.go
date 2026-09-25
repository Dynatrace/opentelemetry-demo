package requests

import (
	"bytes"
	"encoding/json"
	"errors"
	"io"
	"log"
	"net/http"
	"net/url"
	"strings"
)

func GetProducts(client *http.Client, auth string, baseUrl *url.URL) ([]json.RawMessage, error) {
	url, e := url.JoinPath(baseUrl.String(), "/db/product")
	if e != nil {
		log.Println("[Get Products] Error when constructing url:", e)
		return nil, e
	}

	req, e := http.NewRequest(http.MethodGet, url, nil)
	if e != nil {
		log.Println("[Get Products] Error when creating request:", e)
		return nil, e
	}
	req.Header.Set("Authorization", auth)

	log.Printf("[Get Products] Sending request to [%s]", url)
	res, e := client.Do(req)
	if e != nil {
		log.Println("[Get Products] Error when sending request:", e)
		return nil, e
	}

	log.Printf("[Get Products] Received response [%s] from [%s]", res.Status, url)
	defer res.Body.Close()
	b, e := io.ReadAll(res.Body)
	if e != nil {
		log.Println("[Get Products] Error when reading body:", e)
		return nil, e
	}
	var j []json.RawMessage
	e = json.Unmarshal(b, &j)
	if e != nil {
		log.Println("[Get Products] Error when parsing body:", e)
		return nil, e
	}
	log.Printf("[Get Products] Received [%d] products from [%s]", len(j), url)
	return j, nil
}

func GetProduct(client *http.Client, auth string, baseUrl *url.URL, productId string) (json.RawMessage, error) {
	log.Printf("[Get Product] running for product [%s]", productId)

	url, e := url.JoinPath(baseUrl.String(), "db/product", productId)
	if e != nil {
		log.Println("[Get Product] Error when constructing url:", e)
		return nil, e
	}

	req, e := http.NewRequest(http.MethodGet, url, nil)
	if e != nil {
		log.Println("[Get Product] Error when creating request:", e)
		return nil, e
	}
	req.Header.Set("Authorization", auth)

	log.Printf("[Get Product] Sending request to [%s]", url)
	res, e := client.Do(req)
	if e != nil {
		log.Println("[Get Product] Error when sending request:", e)
		return nil, e
	}

	log.Printf("[Get Product] Received response [%s] from [%s]", res.Status, url)
	defer res.Body.Close()
	b, e := io.ReadAll(res.Body)
	if e != nil {
		log.Println("[Get Product] Error when reading body:", e)
		return nil, e
	}
	if res.StatusCode >= 400 {
		log.Println("[Get Product] Error response: ", string(b))
		return nil, errors.New("HTTP error")
	}
	var p json.RawMessage
	e = json.Unmarshal(b, &p)
	if e != nil {
		log.Println("[Get Product] Error parsing response:", e)
	}

	log.Println("[Get Product] Received product: ", string(p))
	return p, nil
}

type Product struct {
	Id   string
	Blob json.RawMessage
}

// TriggerError sends a POST to /db/product with no payload, intentionally causing an HTTP 500.
func TriggerError(client *http.Client, auth string, baseUrl *url.URL) error {
	url, e := url.JoinPath(baseUrl.String(), "db/product")
	if e != nil {
		log.Println("[Trigger Error] Error when constructing url:", e)
		return e
	}

	req, e := http.NewRequest(http.MethodPost, url, nil)
	if e != nil {
		log.Println("[Trigger Error] Error when creating request:", e)
		return e
	}
	req.Header.Set("Authorization", auth)
	req.Header.Set("Content-Type", "application/json")

	log.Printf("[Trigger Error] Sending empty POST to [%s] (expecting HTTP 500)", url)
	res, e := client.Do(req)
	if e != nil {
		log.Println("[Trigger Error] Error when sending request:", e)
		return e
	}
	defer res.Body.Close()

	b, e := io.ReadAll(res.Body)
	if e != nil {
		log.Println("[Trigger Error] Error when reading body:", e)
		return e
	}
	log.Printf("[Trigger Error] Received response [%s] from [%s]: %s", res.Status, url, string(b))
	return nil
}

// TriggerWarning sends a GET to a non-existent endpoint, intentionally causing an HTTP 404.
func TriggerWarning(client *http.Client, auth string, baseUrl *url.URL) error {
	url, e := url.JoinPath(baseUrl.String(), "db/product-404-api/1234")
	if e != nil {
		log.Println("[Trigger Warning] Error when constructing url:", e)
		return e
	}

	req, e := http.NewRequest(http.MethodGet, url, nil)
	if e != nil {
		log.Println("[Trigger Warning] Error when creating request:", e)
		return e
	}
	req.Header.Set("Authorization", auth)

	log.Printf("[Trigger Warning] Sending GET to non-existent endpoint [%s] (expecting HTTP 404)", url)
	res, e := client.Do(req)
	if e != nil {
		log.Println("[Trigger Warning] Error when sending request:", e)
		return e
	}
	defer res.Body.Close()

	b, e := io.ReadAll(res.Body)
	if e != nil {
		log.Println("[Trigger Warning] Error when reading body:", e)
		return e
	}
	body := strings.Join(strings.Fields(string(b)), " ")
	log.Printf("[Trigger Warning] Received response [%s] from [%s]: %s", res.Status, url, body)
	return nil
}

func UpdateProduct(client *http.Client, auth string, baseUrl *url.URL, product Product) error {
	log.Printf("[Update Product] running for product [%s]", product.Id)

	url, e := url.JoinPath(baseUrl.String(), "db/product", product.Id)
	if e != nil {
		log.Println("[Update Product] Error when constructing url:", e)
		return e
	}

	req, e := http.NewRequest(http.MethodPut, url, bytes.NewBuffer(product.Blob))
	if e != nil {
		log.Println("[Update Product] Error when creating request:", e)
		return e
	}
	req.Header.Set("Authorization", auth)
	req.Header.Set("Content-Type", "application/json")

	log.Printf("[Update Product] Sending request to [%s]", url)
	res, e := client.Do(req)
	if e != nil {
		log.Println("[Update Product] Error when sending request:", e)
		return e
	}
	defer res.Body.Close()

	log.Printf("[Update Product] Received response [%s] from [%s]", res.Status, url)
	b, e := io.ReadAll(res.Body)
	if e != nil {
		log.Println("[Update Product] Error when reading body:", e)
		return e
	}
	if res.StatusCode >= 400 {
		log.Println("[Update Product] Error response: ", string(b))
		return errors.New("HTTP error")
	}
	return nil
}
