package main

import (
	"encoding/base64"
	"encoding/json"
	"load-generator/requests"
	"load-generator/schedule"
	"load-generator/utils"
	"log"
	"net/http"
	"net/url"
	"sync"
	"time"
)

func getAuthHeader(username string, password string) string {
	s := username + ":" + password
	return "Basic " + base64.StdEncoding.EncodeToString([]byte(s))
}

func wrapInLogs(name string, f func() error) func() {
	return func() {
		log.Printf("Starting job [%s]", name)
		e := f()
		if e != nil {
			log.Printf("Job [%s] failed: %s", name, e)
			return
		}
		log.Printf("Job [%s] succeeded", name)
	}
}

type IdItem struct {
	Id string `json:"id"`
}

func storeProducts(p *sync.Map, d []json.RawMessage) {
	p.Clear()

	for _, blob := range d {
		var j IdItem
		e := json.Unmarshal(blob, &j)
		if e != nil {
			log.Println("Failed to parse product:", e)
			continue
		}
		if len(j.Id) == 0 {
			log.Println("Malformed product, no id:", string(blob))
			continue
		}
		p.Store(j.Id, blob)
	}
}

func main() {
	baseUrl, e := url.Parse(utils.RequireEnv("BASE_URL"))
	if e != nil {
		log.Fatalln("Error when parsing [BASE_URL]:", e)
	}

	username := utils.RequireEnv("USERNAME")
	password := utils.RequireEnv("PASSWORD")

	getProductsIntervalS := utils.RequireIntEnv("GET_PRODUCTS_INTERVAL_S", 60)
	getProductIntervalS := utils.RequireIntEnv("GET_PRODUCT_INTERVAL_S", 60)
	updateProductIntervalS := utils.RequireIntEnv("UPDATE_PRODUCT_INTERVAL_S", 5*60)

	// Fault injection intervals. Set to 0 to disable a job entirely.
	triggerErrorIntervalS := utils.RequireIntEnv("TRIGGER_ERROR_INTERVAL_S", 120)
	triggerWarningIntervalS := utils.RequireIntEnv("TRIGGER_WARNING_INTERVAL_S", 60)

	client := &http.Client{}
	auth := getAuthHeader(username, password)

	data, e := requests.GetProducts(client, auth, baseUrl)
	if e != nil {
		log.Fatalln("Error getting products:", e)
	}

	var products sync.Map

	storeProducts(&products, data)

	schedule.Start(time.Duration(getProductsIntervalS)*time.Second, wrapInLogs("GetProducts", func() error {
		d, e := requests.GetProducts(client, auth, baseUrl)
		storeProducts(&products, d)
		return e
	}))

	schedule.Start(time.Duration(getProductIntervalS)*time.Second, wrapInLogs("GetProduct", func() error {
		p, e := utils.RandomElement(utils.SyncMapToSlice(&products))
		if e != nil {
			log.Println("Error getting random product:", p)
			return e
		}
		_, e = requests.GetProduct(client, auth, baseUrl, p.Key.(string))
		return e
	}))

	schedule.Start(time.Duration(updateProductIntervalS)*time.Second, wrapInLogs("UpdateProduct", func() error {
		p, e := utils.RandomElement(utils.SyncMapToSlice(&products))
		if e != nil {
			log.Println("Error getting random product:", p)
			return e
		}
		e = requests.UpdateProduct(client, auth, baseUrl, requests.Product{Id: p.Key.(string), Blob: p.Value.(json.RawMessage)})
		return e
	}))

	if triggerErrorIntervalS > 0 {
		schedule.Start(time.Duration(triggerErrorIntervalS)*time.Second, wrapInLogs("TriggerError", func() error {
			return requests.TriggerError(client, auth, baseUrl)
		}))
	} else {
		log.Println("TriggerError job disabled (TRIGGER_ERROR_INTERVAL_S=0)")
	}

	if triggerWarningIntervalS > 0 {
		schedule.Start(time.Duration(triggerWarningIntervalS)*time.Second, wrapInLogs("TriggerWarning", func() error {
			return requests.TriggerWarning(client, auth, baseUrl)
		}))
	} else {
		log.Println("TriggerWarning job disabled (TRIGGER_WARNING_INTERVAL_S=0)")
	}

	select {}
}
