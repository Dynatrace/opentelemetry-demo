package utils

import (
	"errors"
	"log"
	"math/rand"
	"os"
	"strconv"
	"sync"
)

func RandomElement[T any](s []T) (T, error) {
	if len(s) == 0 {
		var z T
		return z, errors.New("the slice is empty")
	}
	return s[rand.Intn(len(s))], nil
}

type Item struct {
	Key   any
	Value any
}

func SyncMapToSlice(m *sync.Map) []Item {
	var s []Item
	m.Range(func(key, value any) bool {
		s = append(s, Item{Key: key, Value: value})
		return true
	})
	return s
}

func Filter[T any](s []T, p func(T) bool) []T {
	r := make([]T, 0, len(s))

	for _, e := range s {
		if p(e) {
			r = append(r, e)
		}
	}

	return r
}

func RequireEnv(name string, defaultValue ...string) string {
	val := os.Getenv(name)
	if val == "" {
		if len(defaultValue) == 0 {
			log.Fatalf("Env var [%s] required", name)
		}
		return defaultValue[0]
	}
	return val
}

func RequireIntEnv(name string, defaultValue ...int) int {
	val := os.Getenv(name)
	if val == "" {
		if len(defaultValue) == 0 {
			log.Fatalf("Env var [%s] required", name)
		}
		return defaultValue[0]
	}
	v, e := strconv.Atoi(val)
	if e != nil {
		log.Fatalf("[%s] value [%s] could not be parsed", name, val)
	}
	return v
}
